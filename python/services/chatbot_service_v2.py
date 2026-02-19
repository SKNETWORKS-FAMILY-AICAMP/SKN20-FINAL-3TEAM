"""
chatbot_service_v2.py - RAG 성능 개선 버전

변경사항:
1. [Reranker] Cross-encoder 기반 재정렬 추가
2. [캐싱] 임베딩 LRU 캐시 (500개)
3. [k값] 검색 후보 확대 (k=2 → k=15, Reranker 후 top=3~5)

의존성 추가:
- sentence-transformers (pip install sentence-transformers)
"""

import json
import logging
import os
import re
import time  # [V2 변경] 성능 측정용
from typing import Optional, Dict, Any, List, Tuple
from collections import OrderedDict  # [V2 변경] LRU 캐시용
import psycopg2
from psycopg2.extras import RealDictCursor

from openai import OpenAI

from CV.rag_system.config import RAGConfig
from CV.rag_system.embeddings import EmbeddingManager
from services.pgvector_service import pgvector_service

logger = logging.getLogger("ChatbotService")


# ==========================================
# [V2 변경] 임베딩 LRU 캐시 클래스
# ==========================================
class EmbeddingCache:
    """
    임베딩 벡터 LRU 캐시
    - 같은 질문에 대해 OpenAI API 중복 호출 방지
    - 최대 500개 저장, 초과 시 가장 오래된 항목 제거
    """

    def __init__(self, max_size: int = 500):
        self._cache: OrderedDict[str, List[float]] = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[List[float]]:
        """캐시에서 임베딩 조회 (히트 시 순서 갱신)"""
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, key: str, embedding: List[float]) -> None:
        """캐시에 임베딩 저장 (초과 시 LRU 제거)"""
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)  # 가장 오래된 항목 제거
        self._cache[key] = embedding

    @property
    def hit_rate(self) -> float:
        """캐시 히트율 (%)"""
        total = self._hits + self._misses
        return (self._hits / total * 100) if total > 0 else 0.0

    @property
    def stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self.hit_rate:.1f}%"
        }


# ==========================================
# 용도지역 매핑 사전 (일반 표현 → DB 값)
# 띄어쓰기 버전은 normalize_query()에서 처리
# ==========================================
ZONE_DISTRICT_DICTIONARY = {
    # 카테고리 → 전체 목록
    "주거지역": ["제1종전용주거지역", "제2종전용주거지역", "제1종일반주거지역", "제2종일반주거지역", "제3종일반주거지역", "준주거지역"],
    "전용주거지역": ["제1종전용주거지역", "제2종전용주거지역"],
    "일반주거지역": ["제1종일반주거지역", "제2종일반주거지역", "제3종일반주거지역"],
    "상업지역": ["중심상업지역", "일반상업지역", "근린상업지역", "유통상업지역"],
    "공업지역": ["전용공업지역", "일반공업지역", "준공업지역"],
    "녹지지역": ["보전녹지지역", "생산녹지지역", "자연녹지지역"],
    "관리지역": ["보전관리지역", "생산관리지역", "계획관리지역"],

    # "제N종주거지역" (전용/일반 누락) → 양쪽 모두 포함
    "제1종주거지역": ["제1종전용주거지역", "제1종일반주거지역"],
    "제2종주거지역": ["제2종전용주거지역", "제2종일반주거지역"],
    "제3종주거지역": ["제3종일반주거지역"],

    # 축약어 → 정식명칭
    "1종주거": "제1종일반주거지역",
    "2종주거": "제2종일반주거지역",
    "3종주거": "제3종일반주거지역",
    "중심상업": "중심상업지역",
    "일반상업": "일반상업지역",
    "근린상업": "근린상업지역",
    "유통상업": "유통상업지역",
    "전용공업": "전용공업지역",
    "일반공업": "일반공업지역",
    "준공업": "준공업지역",
    "보전녹지": "보전녹지지역",
    "생산녹지": "생산녹지지역",
    "자연녹지": "자연녹지지역",
    "보전관리": "보전관리지역",
    "생산관리": "생산관리지역",
    "계획관리": "계획관리지역",
    "자연환경보전": "자연환경보전지역",
    "농림지역": "농림지역",
}

# ==========================================
# 토지이용명 매핑 사전 (일반 표현 → DB 값)
# ==========================================
LAND_USE_DICTIONARY = {
    # 미용 관련
    "미용실": "미용원",
    "헤어샵": "미용원",
    "뷰티샵": "미용원",
    "헤어살롱": "미용원",
    "머리방": "미용원",
    "애견미용": "동물미용실",
    "펫미용": "동물미용실",
    "강아지미용": "동물미용실",

    # 음식점 관련
    "카페": ["휴게음식점", "제과점"],
    "커피숍": ["휴게음식점", "제과점"],
    "커피전문점": ["휴게음식점", "제과점"],
    "디저트": ["휴게음식점", "제과점"],
    "디저트카페": ["휴게음식점", "제과점"],
    "빵집": "제과점",
    "베이커리": "제과점",
    "제과": "제과점",
    "음식점": ["일반음식점", "휴게음식점"],
    "식당": "일반음식점",
    "레스토랑": "일반음식점",
    "분식": "일반음식점",
    "치킨집": "일반음식점",
    "고기집": "일반음식점",

    # 상점/소매 관련
    "가게": "상점",
    "마트": ["상점", "대규모점포"],
    "슈퍼": "상점",
    "슈퍼마켓": "상점",
    "편의점": "상점",
    "잡화점": "상점",

    # 교육 관련
    "학원": "학원",
    "입시학원": "학원",
    "보습학원": "학원",
    "공부방": "교습소",
    "과외": "교습소",
    "운전학원": "운전학원",
    "유치원": "유치원",
    "어린이집": "아동복지시설",
    "초등학교": "초등학교",
    "중학교": "중학교",
    "고등학교": "고등학교",
    "대학교": "대학",

    # 의료 관련
    "병원": "병원",
    "종합병원": "병원",
    "의원": "의원",
    "클리닉": "의원",
    "치과": "치과의원",
    "한의원": "한의원",
    "동물병원": "동물병원",
    "수의사": "동물병원",
    "약국": "약국",

    # 숙박 관련
    "숙박시설": ["일반숙박시설", "생활숙박시설", "가족호텔"],
    "숙박": ["일반숙박시설", "생활숙박시설", "가족호텔"],
    "호텔": ["가족호텔", "일반숙박시설"],
    "리조트": "가족호텔",
    "모텔": "일반숙박시설",
    "여관": "여관",
    "민박": "생활숙박시설",
    "펜션": "생활숙박시설",
    "에어비앤비": "생활숙박시설",
    "게스트하우스": "생활숙박시설",

    # 운동/체육 관련
    "헬스장": "체육관",
    "헬스클럽": "체육관",
    "피트니스": "체육관",
    "체육관": "체육관",
    "태권도장": "체육도장",
    "태권도": "체육도장",
    "검도장": "체육도장",
    "유도장": "체육도장",
    "골프연습장": "골프연습장",
    "스크린골프": "골프연습장",
    "골프장": "골프장",
    "수영장": "수영장",
    "요가": "체육관",
    "필라테스": "체육관",

    # 자동차 관련
    "주유소": "주유소",
    "세차장": "세차장",
    "카센터": "정비공장",
    "정비소": "정비공장",
    "자동차정비": "정비공장",
    "주차장": "주차장",
    "전기차충전소": "전기자동차충전소",
    "충전소": "전기자동차충전소",

    # 오락/여가 관련
    "노래방": "노래연습장",
    "코인노래방": "노래연습장",
    "pc방": "인터넷컴퓨터게임시설제공업소",
    "피시방": "인터넷컴퓨터게임시설제공업소",
    "게임방": "복합유통게임제공업소",
    "오락실": "복합유통게임제공업소",
    "당구장": "당구장",
    "볼링장": "볼링장",
    "vr": "가상현실체험제공업소",
    "vr카페": "가상현실체험제공업소",

    # 종교 관련
    "교회": "교회",
    "성당": "종교시설",
    "절": "종교시설",
    "사찰": "종교시설",

    # 사무/업무 관련
    "사무실": "사무소",
    "오피스": "사무소",
    "오피스텔": "오피스텔",

    # 기타
    "세탁소": "세탁소",
    "빨래방": "세탁소",
    "공장": "공장",
    "창고": "창고",

    # 특수 시설
    "건물": "건축물",
    "빌딩": "건축물",
    "건축": "건축물",
    "건축물": "건축물",
    "가축": "가축시장",
    "축사": "가축시장",
    "철도": "철도시설",
    "기차역": "철도시설",
    "화장실": "공중화장실",

    # 근린생활시설
    "근린생활시설": ["제1종근린생활시설", "제2종근린생활시설"],
    "상가": ["상점", "제1종근린생활시설", "제2종근린생활시설"],

    # 주거시설 (DB값: 아파트, 연립주택, 다세대주택, 단독주택)
    "다가구": "단독주택",
    "다가구주택": "단독주택",
    "아파트": "아파트",
    "빌라": "다세대주택",
    "다세대": "다세대주택",
    "다세대주택": "다세대주택",
    "연립": "연립주택",
    "연립주택": "연립주택",
    "단독주택": "단독주택",
    "주택": ["단독주택", "다세대주택", "연립주택", "아파트"],
    "원룸": "다세대주택",
}

# ==========================================
# 특수 쿼리 키워드 (법률 관련 질의)
# ==========================================
SPECIAL_QUERY_KEYWORDS = {
    # 건폐율/용적률 (오타는 normalize_query()에서 처리)
    "건폐율": "coverage_ratio",
    "용적률": "floor_area_ratio",
    # 법률 비교 (띄어쓰기는 normalize_query()에서 처리)
    "조례": "law_comparison",
    "법과조례": "law_comparison",
    "건축법과조례": "law_comparison",
    "법규비교": "law_comparison",
    "조례비교": "law_comparison",
    "조례차이": "law_comparison",
    "법률비교": "law_comparison",
    # 규제 (띄어쓰기는 normalize_query()에서 처리)
    "높이제한": "height_limit",
    "층수제한": "floor_limit",
    "건축가능": "building_permit",
    "신축": "building_permit",
    "규제": "coverage_ratio",
    "제한": "coverage_ratio",
}

# ==========================================
# 용도지역별 건폐율/용적률/높이제한 기준 (간소화)
# 출처: 국토계획법 시행령 제84조(건폐율), 제85조(용적률)
# ==========================================
ZONE_REGULATION_SOURCE = "국토계획법 시행령 제84조, 제85조"

ZONE_REGULATIONS = {
    # 주거지역 (건폐율, 용적률, 높이제한)
    "제1종전용주거지역": {"건폐율": "50%", "용적률": "50~100%", "높이": "없음", "설명": "단독주택 중심"},
    "제2종전용주거지역": {"건폐율": "50%", "용적률": "100~150%", "높이": "없음", "설명": "공동주택 중심"},
    "제1종일반주거지역": {"건폐율": "60%", "용적률": "100~200%", "높이": "4층 이하", "설명": "저층주택 중심"},
    "제2종일반주거지역": {"건폐율": "60%", "용적률": "150~250%", "높이": "없음", "설명": "중층주택 중심"},
    "제3종일반주거지역": {"건폐율": "50%", "용적률": "200~300%", "높이": "없음", "설명": "중고층주택 중심"},
    "준주거지역": {"건폐율": "70%", "용적률": "200~500%", "높이": "없음", "설명": "주거+상업 혼합"},

    # 상업지역
    "중심상업지역": {"건폐율": "90%", "용적률": "400~1500%", "높이": "없음", "설명": "도심 상업·업무"},
    "일반상업지역": {"건폐율": "80%", "용적률": "300~1300%", "높이": "없음", "설명": "일반 상업·업무"},
    "근린상업지역": {"건폐율": "70%", "용적률": "200~900%", "높이": "없음", "설명": "근린 서비스"},
    "유통상업지역": {"건폐율": "80%", "용적률": "200~1100%", "높이": "없음", "설명": "유통기능"},

    # 공업지역
    "전용공업지역": {"건폐율": "70%", "용적률": "150~300%", "높이": "없음", "설명": "중화학공업"},
    "일반공업지역": {"건폐율": "70%", "용적률": "200~350%", "높이": "없음", "설명": "환경저해 없는 공업"},
    "준공업지역": {"건폐율": "70%", "용적률": "200~400%", "높이": "없음", "설명": "경공업, 주거 혼재"},

    # 녹지지역
    "보전녹지지역": {"건폐율": "20%", "용적률": "50~80%", "높이": "4층 이하", "설명": "자연환경 보전"},
    "생산녹지지역": {"건폐율": "20%", "용적률": "50~100%", "높이": "4층 이하", "설명": "농업적 생산"},
    "자연녹지지역": {"건폐율": "20%", "용적률": "50~100%", "높이": "4층 이하", "설명": "녹지공간 확보"},

    # 관리지역
    "보전관리지역": {"건폐율": "20%", "용적률": "50~80%", "높이": "4층 이하", "설명": "자연환경 보호"},
    "생산관리지역": {"건폐율": "20%", "용적률": "50~80%", "높이": "4층 이하", "설명": "농림어업 생산"},
    "계획관리지역": {"건폐율": "40%", "용적률": "50~100%", "높이": "4층 이하", "설명": "계획적 관리"},

    # 기타
    "농림지역": {"건폐율": "20%", "용적률": "50~80%", "높이": "4층 이하", "설명": "농림업 진흥"},
    "자연환경보전지역": {"건폐율": "20%", "용적률": "50~80%", "높이": "4층 이하", "설명": "생태계 보전"},
}


class ChatbotService:
    """RAG 기반 챗봇 서비스 + PostgreSQL 대화 내역 활용 (V2: Reranker + 캐싱)"""

    # PostgreSQL 연결 정보 (application.properties와 동일)
    DB_CONFIG = {
        "host": "localhost",
        "port": 5432,
        "database": "arae",
        "user": "postgres",
        "password": "1234"
    }

    # [V2 변경] Reranker 설정
    RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self):
        self.config: Optional[RAGConfig] = None
        self.embedding_manager: Optional[EmbeddingManager] = None
        self.openai_client: Optional[OpenAI] = None
        self.db_conn = None
        self._reranker = None  # [V2 변경] Cross-encoder reranker
        self._reranker_available = False  # [V2 변경] Reranker 사용 가능 여부
        self._embedding_cache = EmbeddingCache(max_size=500)  # [V2 변경] 임베딩 캐시

    def _get_cursor(self):
        """
        DB 커서 반환 (연결 끊김 시 자동 재연결)
        - SELECT 1 핑 제거: closed 속성 + OperationalError catch로 대체
        """
        try:
            if self.db_conn is None or self.db_conn.closed:
                logger.warning("DB 연결 끊김 감지, 재연결 시도...")
                self.db_conn = psycopg2.connect(**self.DB_CONFIG)
                self.db_conn.autocommit = True
                logger.info("DB 재연결 성공 (autocommit=True)")

            return self.db_conn.cursor(cursor_factory=RealDictCursor)

        except psycopg2.OperationalError:
            logger.warning("DB 연결 유효하지 않음, 재연결 시도...")
            self.db_conn = psycopg2.connect(**self.DB_CONFIG)
            self.db_conn.autocommit = True
            logger.info("DB 재연결 성공 (autocommit=True)")
            return self.db_conn.cursor(cursor_factory=RealDictCursor)

        except Exception as e:
            logger.error(f"DB 연결/재연결 실패: {e}")
            raise
    
    def _get_facility_definitions(self, question: str, extracted_activities: List[str]) -> List[Dict[str, str]]:
        """
        질문 및 추출된 활동명에서 건축물 용도를 찾아 usebuilding 테이블에서 설명 조회
        
        Args:
            question: 사용자 질문
            extracted_activities: extract_with_llm()에서 추출된 토지이용 행위 목록
        
        Returns:
            [{'facility_name': '휴게음식점', 'description': '...', 'category_name': '...', 'url': '...'}, ...]
        """
        try:
            cursor = self._get_cursor()
            
            # extracted_activities를 기본으로 사용하되, 1-2글자는 제외 (너무 짧아서 오매칭 발생)
            search_keywords = set()
            if extracted_activities:
                search_keywords = {kw for kw in extracted_activities if len(kw) >= 3}
            
            # 질문에 건축물 시설 키워드가 있는지 확인
            facility_keywords = [
                    # 주거시설
                    "단독주택", "다중주택", "다가구주택", "공관", "아파트", "연립주택", "다세대주택", 
                    "기숙사", "오피스텔", "숙박", "호텔", "여관", "민박", "게스트하우스",
                    
                    # 근린생활시설
                    "소매점", "휴게음식점", "일반음식점", "제과점", "카페", "커피숍", "식당", "레스토랑",
                    "이용원", "미용원", "이발소", "미용실", "목욕장", "세탁소", "빨래방",
                    "의원", "치과의원", "한의원", "침술원", "조산원", "안마원", "산후조리원", "병원",
                    "탁구장", "체육도장", "당구장", "볼링장", "헬스장", "체력단련장", "골프연습장",
                    "지역자치센터", "파출소", "지구대", "소방서", "우체국", "방송국", "보건소",
                    "공공도서관", "도서관", "독서실", "마을회관", "공중화장실", "대피소",
                    "변전소", "통신용시설", "정수장", "양수장", "주유소", "충전소",
                    "금융업소", "은행", "사무소", "부동산중개사무소", "결혼상담소", "출판사",
                    "동물병원", "동물미용실", "펫샵",
                    
                    # 문화집회시설
                    "극장", "영화관", "연예장", "음악당", "서커스장", "공연장",
                    "비디오물감상실", "비디오물소극장", "DVD방",
                    "교회", "성당", "사찰", "기도원", "수도원", "수녀원", "제실", "사당", "예배당",
                    "서점", "사진관", "표구점", "화랑", "갤러리",
                    "게임장", "PC방", "노래방", "노래연습장", "오락실",
                    
                    # 판매시설
                    "상가", "쇼핑몰", "백화점", "마트", "슈퍼마켓", "편의점", "대형마트",
                    "시장", "도매시장", "공판장", "면세점",
                    
                    # 운수시설
                    "터미널", "여객터미널", "버스터미널", "역", "공항", "항만", "정류장",
                    
                    # 의료시설
                    "종합병원", "병원", "치과병원", "한방병원", "요양병원", "정신병원",
                    "마약진료소", "보건소", "보건지소",
                    
                    # 교육연구시설
                    "유치원", "어린이집", "초등학교", "중학교", "고등학교", "학교",
                    "전문대학", "대학", "대학교", "대학원",
                    "학원", "교습소", "독서실", "스터디카페", "직업훈련소", "연수원",
                    "연구소", "실험실",
                    
                    # 노유자시설
                    "아동복지시설", "어린이집", "유치원", "지역아동센터",
                    "노인복지시설", "요양원", "양로원", "노인요양시설",
                    "사회복지시설", "장애인복지시설",
                    
                    # 수련시설
                    "청소년수련관", "청소년수련원", "청소년문화의집", "유스호스텔", "야영장",
                    
                    # 운동시설
                    "체육관", "육상장", "구기장", "수영장", "스케이트장", "롤러스케이트장",
                    "승마장", "사격장", "궁도장", "골프장", "스키장", "테니스장", "배드민턴장",
                    
                    # 업무시설
                    "청사", "오피스텔", "사무소", "사무실", "콜센터",
                    
                    # 숙박시설
                    "관광호텔", "호텔", "모텔", "여관", "콘도미니엄", "휴양콘도",
                    
                    # 위락시설
                    "단란주점", "유흥주점", "주점", "술집", "바", "클럽",
                    "유원시설", "놀이공원", "워터파크", "테마파크",
                    "무도장", "무도학원", "댄스홀", "카지노",
                    
                    # 공장
                    "공장", "제조업소", "작업장", "생산시설",
                    
                    # 창고시설
                    "창고", "하역장", "물류터미널", "물류창고", "냉동창고",
                    
                    # 위험물저장 및 처리시설
                    "주유소", "석유판매소", "가스충전소", "LPG충전소",
                    "위험물제조소", "위험물저장소", "위험물취급소",
                    
                    # 자동차관련시설
                    "주차장", "세차장", "폐차장", "정비공장", "카센터",
                    "운전학원", "차고", "주기장",
                    
                    # 동물 및 식물관련시설
                    "축사", "돈사", "계사", "우사", "가축시장", "도축장", "도계장",
                    "비닐하우스", "온실", "농막", "작물재배사", "화초온실",
                    "동물원", "식물원", "수족관",
                    
                    # 자원순환 관련시설
                    "고물상", "폐기물처리시설", "재활용센터", "소각장", "매립장",
                    
                    # 교정 및 군사시설
                    "교도소", "구치소", "보호감호소", "소년원",
                    "군부대", "훈련소", "막사", "탄약고",
                    
                    # 방송통신시설
                    "방송국", "송신소", "중계소", "데이터센터", "통신국",
                    
                    # 발전시설
                    "발전소", "변전소", "태양광발전소", "풍력발전소",
                    
                    # 묘지관련시설
                    "화장장", "화장시설", "봉안당", "납골당", "묘지",
                    
                    # 관광휴게시설
                    "야외음악당", "야외극장", "어린이회관", "휴게소", "전망대",
                    "공원시설", "유원지", "관광지",
                    
                    # 장례시설
                    "장례식장", "장례식장", "빈소",
                ]
            
            # 질문에서 매칭되는 시설 키워드 추출 (3글자 이상만)
            question_lower = question.lower()
            for keyword in facility_keywords:
                if len(keyword) >= 3 and (keyword in question or keyword in question_lower):
                    search_keywords.add(keyword)
            
            if not search_keywords:
                return []
            
            logger.info(f"[건축물 용도 검색] 키워드: {search_keywords}")
            
            # usebuilding 테이블에서 관련 시설 조회
            results = []
            seen_facilities = set()  # 중복 방지
            
            for keyword in search_keywords:
                # 짧은 키워드(1-2글자)는 정확 매칭, 긴 키워드는 부분 매칭
                if len(keyword) <= 2:
                    query = """
                        SELECT category_name, facility_name, description, url
                        FROM use_building
                        WHERE facility_name = %s
                        LIMIT 3
                    """
                    cursor.execute(query, (keyword,))
                else:
                    query = """
                        SELECT category_name, facility_name, description, url
                        FROM use_building
                        WHERE facility_name ILIKE %s
                        LIMIT 3
                    """
                    cursor.execute(query, (f"%{keyword}%",))
                
                rows = cursor.fetchall()
                
                for row in rows:
                    facility_name = row['facility_name']
                    # 중복 제거
                    if facility_name not in seen_facilities:
                        results.append(dict(row))
                        seen_facilities.add(facility_name)
                
                if len(results) >= 5:  # 최대 5개까지만
                    break
            
            cursor.close()
            
            if results:
                logger.info(f"[건축물 용도 검색] {len(results)}건 발견: {[r['facility_name'] for r in results]}")
            
            return results
            
        except Exception as e:
            logger.error(f"건축물 용도 조회 실패: {e}")
            return []

    def load_components(self):
        """RAG 컴포넌트를 lazy loading 방식으로 로드"""
        if self.openai_client is not None:
            return

        logger.info("챗봇 컴포넌트 로딩 중...")

        try:
            self.config = RAGConfig()
            self.embedding_manager = EmbeddingManager(
                api_key=self.config.OPENAI_API_KEY,
                model="text-embedding-3-small"
            )
            self.openai_client = OpenAI(api_key=self.config.OPENAI_API_KEY)

            # PostgreSQL 연결 (autocommit으로 트랜잭션 꼬임 방지)
            self.db_conn = psycopg2.connect(**self.DB_CONFIG)
            self.db_conn.autocommit = True
            logger.info("PostgreSQL 연결 완료 (autocommit=True)")

            # [V2 변경] Reranker 로드 (실패해도 서비스 계속)
            self._load_reranker()

            logger.info("챗봇 컴포넌트 로딩 완료!")
        except Exception as e:
            logger.error(f"챗봇 컴포넌트 로딩 실패: {e}")
            raise

    # ==========================================
    # [V2 변경] Reranker 관련 메서드
    # ==========================================

    def _load_reranker(self) -> None:
        """
        Cross-encoder Reranker 모델 로드 (lazy loading)
        - 실패 시 fallback으로 기존 유사도 순서 사용
        """
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Reranker 로딩 중: {self.RERANKER_MODEL_NAME}")
            start = time.time()
            self._reranker = CrossEncoder(self.RERANKER_MODEL_NAME)
            elapsed = time.time() - start
            self._reranker_available = True
            logger.info(f"Reranker 로딩 완료 ({elapsed:.1f}초)")
        except ImportError:
            logger.warning("sentence-transformers 미설치. Reranker 비활성화 (pip install sentence-transformers)")
            self._reranker_available = False
        except Exception as e:
            logger.warning(f"Reranker 로딩 실패, fallback 사용: {e}")
            self._reranker_available = False

    def _rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Cross-encoder로 검색 결과 재정렬

        Args:
            query: 사용자 질문 (정규화 후)
            results: pgvector 검색 결과 리스트 [{'document': ..., 'distance': ...}, ...]
            top_n: 최종 반환할 결과 수

        Returns:
            재정렬된 상위 top_n개 결과 (rerank_score 필드 추가)
        """
        if not results:
            return []

        # [V2 버그픽스] 빈/쓰레기 document 필터링
        # - 빈 문자열 제거
        # - 너무 짧은 document 제거 (빈 템플릿: "[필지 44 정보]\n- 주소:\n- 용도지역: -")
        # - "판정: ?" 같은 빈 필드만 있는 document 제거
        def _is_meaningful_doc(doc_text: str) -> bool:
            if not doc_text or not doc_text.strip():
                return False
            if len(doc_text.strip()) < 50:  # 50자 미만은 의미 없음
                return False
            if doc_text.count("판정: ?") > 0:  # 빈 템플릿
                return False
            if doc_text.count("용도지역: -") > 2:  # 빈 필지 데이터 반복
                return False
            return True

        results = [r for r in results if _is_meaningful_doc(r.get("document", ""))]
        if not results:
            logger.warning("[Reranker] 유효한 document가 없음")
            return []

        # Reranker 사용 불가 시 기존 순서 그대로 반환 (fallback)
        if not self._reranker_available or self._reranker is None:
            logger.info(f"[Reranker] fallback - 기존 순서 유지 (top {top_n})")
            return results[:top_n]

        try:
            start = time.time()

            # Cross-encoder 입력: [(query, document), ...] 쌍 생성
            pairs = [(query, r.get("document", "")) for r in results]

            # Cross-encoder 점수 계산
            scores = self._reranker.predict(pairs)

            # 결과에 rerank_score 추가
            for i, result in enumerate(results):
                result["rerank_score"] = float(scores[i])

            # rerank_score 기준 내림차순 정렬
            reranked = sorted(results, key=lambda x: x.get("rerank_score", 0), reverse=True)

            elapsed = time.time() - start
            logger.info(
                f"[Reranker] {len(results)}개 → top {top_n} 재정렬 완료 "
                f"({elapsed:.3f}초, 최고점: {reranked[0]['rerank_score']:.3f})"
            )

            return reranked[:top_n]

        except Exception as e:
            logger.warning(f"[Reranker] 재정렬 실패, fallback 사용: {e}")
            return results[:top_n]

    # ==========================================
    # [V2 변경] 임베딩 캐싱 메서드
    # ==========================================

    def get_embedding_cached(self, text: str) -> List[float]:
        """
        임베딩 벡터 조회 (캐시 우선, 미스 시 API 호출)

        Args:
            text: 임베딩할 텍스트 (normalize_query 적용 후)

        Returns:
            임베딩 벡터 (List[float], 512차원)
        """
        # 캐시 키: 정규화된 텍스트 (공백 제거)
        cache_key = text.strip()

        # 캐시 히트 확인
        cached = self._embedding_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"[캐시] HIT - '{cache_key[:30]}...' (히트율: {self._embedding_cache.hit_rate:.1f}%)")
            return cached

        # 캐시 미스: OpenAI API 호출
        start = time.time()
        embedding = self.embedding_manager.embed_text(text)
        elapsed = time.time() - start

        # 캐시 저장
        self._embedding_cache.put(cache_key, embedding)
        logger.debug(
            f"[캐시] MISS - '{cache_key[:30]}...' API 호출 ({elapsed:.3f}초, "
            f"캐시 크기: {self._embedding_cache.stats['size']})"
        )

        return embedding

    def get_recent_chat_history(self, email: str, limit: int = 5) -> List[Dict[str, str]]:
        """
        PostgreSQL에서 사용자의 최근 대화 내역 조회

        Args:
            email: 사용자 이메일
            limit: 가져올 대화 개수

        Returns:
            [{"question": str, "answer": str, "created_at": str}, ...]
        """
        if self.db_conn is None:
            logger.warning("PostgreSQL 연결 안됨. 이전 대화 내역 없이 진행")
            return []

        if email == "anonymous":
            return []

        try:
            query = """
            SELECT ch.question, ch.answer, ch.created_at
            FROM "chat_history" ch
            JOIN "chatroom" cr ON ch.chatroom_id = cr.id
            JOIN "users" u ON cr.user_id = u.id
            WHERE u.email = %s
            ORDER BY ch.created_at DESC
            LIMIT %s
            """

            with self._get_cursor() as cursor:
                cursor.execute(query, (email, limit))
                results = cursor.fetchall()

                history = [
                    {
                        "question": row["question"],
                        "answer": row["answer"],
                        "created_at": str(row["created_at"])
                    }
                    for row in reversed(results)
                ]

                logger.info(f"{email}의 이전 대화 {len(history)}개 조회 완료")
                return history

        except Exception as e:
            logger.error(f"대화 내역 조회 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []

    def normalize_query(self, text: str) -> str:
        """
        질문 텍스트 정규화 (오타/띄어쓰기 보정)
        - ask()에서 1번만 호출하여 전체 추출 로직에 적용
        """
        # 1. 오타 보정
        text = text.replace("건페율", "건폐율")
        text = text.replace("용적율", "용적률")

        # 2. 핵심 키워드 공백 축약 (정규식 - "건 폐 율" → "건폐율")
        text = re.sub(r'건\s*폐\s*율', '건폐율', text)
        text = re.sub(r'용\s*적\s*률', '용적률', text)
        text = re.sub(r'법\s*규\s*비\s*교', '법규비교', text)

        # 3. "제" 누락 보정 ("2종" → "제2종")
        text = re.sub(r'(?<![제])(\d)\s*종', r'제\1종', text)

        # 4. 띄어쓰기 정규화 (용도지역)
        text = re.sub(r'제\s*(\d)\s*종\s*일\s*반', r'제\1종일반', text)
        text = re.sub(r'제\s*(\d)\s*종\s*전\s*용', r'제\1종전용', text)
        text = re.sub(r'일\s*반\s*주\s*거\s*지\s*역', '일반주거지역', text)
        text = re.sub(r'전\s*용\s*주\s*거\s*지\s*역', '전용주거지역', text)
        text = re.sub(r'주\s*거\s*지\s*역', '주거지역', text)
        text = re.sub(r'상\s*업\s*지\s*역', '상업지역', text)
        text = re.sub(r'공\s*업\s*지\s*역', '공업지역', text)
        text = re.sub(r'녹\s*지\s*지\s*역', '녹지지역', text)
        text = re.sub(r'준\s*주\s*거', '준주거', text)
        text = re.sub(r'준\s*공\s*업', '준공업', text)

        # 4. 띄어쓰기 정규화 (특수 키워드)
        text = text.replace("높이 제한", "높이제한")
        text = text.replace("층수 제한", "층수제한")
        text = text.replace("건축 가능", "건축가능")
        text = text.replace("법과 조례", "법과조례")
        text = text.replace("법규 비교", "법규비교")
        text = text.replace("조례 비교", "조례비교")
        text = text.replace("조례 차이", "조례차이")

        return text

    def parse_address(self, text: str) -> Dict[str, str]:
        """
        질문에서 주소 정보 추출

        Returns:
            dict with keys: legal_dong_name, lot_number, region_code, address_depth
            address_depth:
                0 = 주소 없음
                1 = 시/도만 (서울시)
                2 = 시/도 + 구/군 (서울시 노원구)
                3 = 시/도 + 구/군 + 동/읍/면 (서울시 노원구 중계동)
                4 = 시/도 + 구/군 + 동/읍/면 + 지번 (서울시 노원구 중계동 1-1)
        """
        result = {"legal_dong_name": "", "lot_number": "", "region_code": "", "address_depth": 0}

        # 법정동명 추출 (광역시/도 + 시군구 + 동)
        dong_parts = []

        # 광역시/도 목록 (중복 방지용)
        sido_keywords = [
            '서울특별시', '서울시', '부산광역시', '대구광역시', '인천광역시',
            '광주광역시', '대전광역시', '울산광역시', '세종특별자치시',
            '경기도', '강원도', '충청북도', '충청남도', '전라북도', '전라남도',
            '경상북도', '경상남도', '제주특별자치도'
        ]

        # 1. 광역시/도 추출 (서울특별시, 경기도, 부산광역시 등)
        sido_match = re.search(r'(서울특별시|서울시|서울|부산광역시|부산|대구광역시|대구|인천광역시|인천|광주광역시|광주|대전광역시|대전|울산광역시|울산|세종특별자치시|세종|경기도|경기|강원도|강원|충청북도|충북|충청남도|충남|전라북도|전북|전라남도|전남|경상북도|경북|경상남도|경남|제주특별자치도|제주도|제주)', text)
        if sido_match:
            # 약칭을 정식 명칭으로 정규화 (DB 매칭용)
            sido_normalize = {
                '서울': '서울특별시', '서울시': '서울특별시',
                '부산': '부산광역시', '대구': '대구광역시',
                '인천': '인천광역시', '광주': '광주광역시',
                '대전': '대전광역시', '울산': '울산광역시',
                '세종': '세종특별자치시',
                '경기': '경기도', '강원': '강원도',
                '충북': '충청북도', '충남': '충청남도',
                '전북': '전라북도', '전남': '전라남도',
                '경북': '경상북도', '경남': '경상남도',
                '제주': '제주특별자치도', '제주도': '제주특별자치도',
            }
            sido_raw = sido_match.group(1)
            sido_full = sido_normalize.get(sido_raw, sido_raw)
            dong_parts.append(sido_full)

        # 2. 시군구 추출 (광역시/도 부분을 제외하고 검색)
        # [V2 버그픽스] 비주소 키워드가 시/군/구 패턴에 오탐되는 것 방지
        # "개발제한구역"→"제한구", "용도지역지구"→"지역지구", "근린생활시설"→"생활시" 등
        sigungu_non_address_keywords = [
            '지역', '구역', '제한', '시설', '생활', '공업', '상업', '주거', '녹지',
            '보전', '관리', '환경', '다가구', '건축', '도시', '계획',
        ]
        sigungu_pattern = r'(?:서울특별시|서울시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시|경기도|강원도|충청북도|충청남도|전라북도|전라남도|경상북도|경상남도|제주특별자치도)?\s*([\w]{2,4}(?:시|군|구))'
        sigungu_match = re.search(sigungu_pattern, text)
        if sigungu_match:
            sigungu = sigungu_match.group(1)
            # 광역시명과 중복 방지
            if sigungu not in ['서울시', '부산시', '대구시', '인천시', '광주시', '대전시', '울산시', '세종시']:
                # [V2 버그픽스] 비주소 키워드 포함 시 오탐 무효화
                if any(kw in sigungu for kw in sigungu_non_address_keywords):
                    sigungu_match = None  # 오탐이면 무효화
                elif sigungu not in dong_parts:
                    dong_parts.append(sigungu)

        # 3. 읍면동 추출 (동 뒤에 조사/숫자/공백이 올 수 있음)
        # 비주소 오탐 방지: 면/읍/리는 substring, 동은 exact match
        # (이유: "청운동"이 "운동" substring 매칭에 걸리는 문제 방지)
        dong_false_exact = {'활동', '운동', '행동', '변동', '감동'}  # 동: 정확히 일치할 때만
        dong_false_substring = ['도로', '접면', '노면', '표면', '단면', '측면', '후면',
                                '건축', '시설', '제한', '처리']  # 면/읍/리: 포함 시
        dong_match = re.search(r'([\w]{1,10}(?:동|읍|면|리))(?:\s|\d|에|을|의|로|은|는|이|가|$)', text)
        if dong_match:
            dong = dong_match.group(1)
            is_false = False
            if dong in dong_false_exact:
                is_false = True  # "운동" 정확히 매칭 (but "청운동"은 통과)
            elif dong[-1] in ('면', '읍', '리') and any(kw in dong for kw in dong_false_substring):
                is_false = True  # "도로접면" → "도로" 포함 → 필터
            if is_false:
                dong_match = None
            elif dong not in dong_parts:
                dong_parts.append(dong)

        # "가" 주소 별도 처리 (숫자+가 형태: 종로1가, 명동2가 등)
        ga_match = re.search(r'([\w]{1,8}\d가)(?:\s|\d|에|을|의|로|은|는|$)', text)
        if ga_match:
            ga_dong = ga_match.group(1)
            if ga_dong not in dong_parts:
                dong_parts.append(ga_dong)

        if dong_parts:
            result["legal_dong_name"] = ' '.join(dong_parts)

        # 지번 추출 (오탐 방지: 층수/퍼센트 숫자 제외)
        lot_match = re.search(r'(\d+-\d+)(?:번지)?(?:\s|에|의|은|는|이|가|로|을|$)', text)
        if not lot_match:
            lot_match = re.search(r'(\d+)번지', text)
        if not lot_match:
            lot_match = re.search(r'지번\s*(\d+)', text)
        if not lot_match:
            lot_match = re.search(r'(?:동|읍|면|리|가)\s+(\d+-?\d*)(?:\s|에|의|은|는|이|가|로|을|$)', text)
        if lot_match:
            lot_num = lot_match.group(1).replace('번지', '')
            lot_pos = lot_match.start()
            after_text = text[lot_match.end():lot_match.end()+5] if lot_match.end() < len(text) else ""
            if not re.search(r'(층|%|퍼센트|제곱)', after_text):
                result["lot_number"] = lot_num

        # 지역코드 추출 (시도별)
        region_code_map = {
            '서울': '11', '부산': '26', '대구': '27', '인천': '28',
            '광주': '29', '대전': '30', '울산': '31', '세종': '36',
            '경기': '41', '강원': '42', '충북': '43', '충남': '44',
            '전북': '45', '전남': '46', '경북': '47', '경남': '48', '제주': '50'
        }
        for sido, code in region_code_map.items():
            if sido in text:
                result["region_code"] = code
                break

        # 주소 상세도(depth) 계산
        has_sido = bool(sido_match) if 'sido_match' in dir() else False
        has_sigungu = bool(sigungu_match) if 'sigungu_match' in dir() else False
        has_dong = bool(dong_match) if 'dong_match' in dir() else False
        has_lot = bool(result["lot_number"])

        if has_lot:
            result["address_depth"] = 4
        elif has_dong:
            result["address_depth"] = 3
        elif has_sigungu:
            result["address_depth"] = 2
        elif has_sido:
            result["address_depth"] = 1
        else:
            result["address_depth"] = 0

        return result

    def extract_zone_district_name(self, text: str) -> List[str]:
        """질문에서 지역지구명 추출 (정확한 용도지역명 우선, 사전 매핑은 보조)"""
        exact_matches = []
        regex_matches = []

        # 1. ZONE_REGULATIONS에서 정확한 용도지역명 매칭
        for zone_name in ZONE_REGULATIONS.keys():
            if zone_name in text:
                exact_matches.append(zone_name)

        # 2. 정규식으로 직접 추출
        zone_patterns = [
            r'(제\d종[가-힣]{2,10}지역)',
            r'([가-힣]{2,6}경관지구)',
            r'([가-힣]{2,6}미관지구)',
            r'([가-힣]{2,4}녹지지역)',
            r'([가-힣]{2,4}주거지역)',
            r'([가-힣]{2,4}상업지역)',
            r'([가-힣]{2,4}공업지역)',
            r'([가-힣]{2,6}보호지구)',
            r'([가-힣]{2,6}관리지역)',
        ]

        for pattern in zone_patterns:
            matches = re.findall(pattern, text)
            regex_matches.extend(matches)

        if exact_matches:
            return list(dict.fromkeys(exact_matches))

        if regex_matches:
            filtered = []
            for z in regex_matches:
                is_substring = any(z != other and z in other for other in regex_matches)
                if not is_substring:
                    filtered.append(z)
            return list(dict.fromkeys(filtered))

        # 3. 사전 매핑 사용
        dict_matches = []
        matching_keywords = [kw for kw in ZONE_DISTRICT_DICTIONARY.keys() if kw in text]

        filtered_keywords = []
        for kw in matching_keywords:
            has_longer_match = False
            for other_kw in matching_keywords:
                if kw != other_kw and kw in other_kw:
                    has_longer_match = True
                    break
            if not has_longer_match:
                filtered_keywords.append(kw)

        for keyword in filtered_keywords:
            db_values = ZONE_DISTRICT_DICTIONARY[keyword]
            if isinstance(db_values, list):
                dict_matches.extend(db_values)
            else:
                dict_matches.append(db_values)

        return list(dict.fromkeys(dict_matches))

    def extract_land_use_activity(self, text: str) -> List[str]:
        """질문에서 토지이용행위 추출 (사전 매핑 적용)"""
        activities = []
        text_lower = text.lower()

        # [V2 버그픽스] "건축법", "건축가능" 등 법률 용어 안의 "건축"이 오탐되는 것 방지
        legal_suffixes = ['법', '가능', '금지', '불가', '조례', '선', '허가', '신고', '법시행령']

        # [V2 버그픽스] 1단계: 매칭되는 키워드 수집
        matched_keywords = []
        for keyword in LAND_USE_DICTIONARY.keys():
            if keyword in text or keyword in text_lower:
                if keyword == '건축':
                    is_legal_term = any(f"건축{suffix}" in text for suffix in legal_suffixes)
                    if is_legal_term:
                        continue
                matched_keywords.append(keyword)

        # [V2 버그픽스] 2단계: 긴 키워드의 부분문자열인 짧은 키워드 제거
        # "다가구주택"이 매칭되면 "주택", "다가구"는 부분문자열이므로 제거
        matched_keywords.sort(key=len, reverse=True)
        filtered_keywords = []
        for kw in matched_keywords:
            is_substring = any(kw in longer_kw and kw != longer_kw for longer_kw in filtered_keywords)
            if not is_substring:
                filtered_keywords.append(kw)

        # 3단계: 필터링된 키워드만 DB 값으로 매핑
        for keyword in filtered_keywords:
            db_values = LAND_USE_DICTIONARY[keyword]
            if isinstance(db_values, list):
                activities.extend(db_values)
            else:
                activities.append(db_values)

        floor_match = re.search(r'(\d+)층', text)
        if floor_match:
            activities.append(f"{floor_match.group(1)}층 건축물")

        return list(set(activities))

    def extract_region_codes(self, text: str) -> List[str]:
        """질문에서 구분코드 추출"""
        codes = re.findall(r'\b\d{5}\b', text)
        return codes

    def extract_special_queries(self, text: str) -> List[str]:
        """질문에서 특수 쿼리 유형 추출 (건폐율, 용적률, 법률 비교 등)"""
        queries = []
        text_lower = text.lower()

        for keyword, query_type in SPECIAL_QUERY_KEYWORDS.items():
            if keyword in text or keyword in text_lower:
                if query_type not in queries:
                    queries.append(query_type)

        return queries

    # ==========================================
    # LLM 기반 구조화 추출 (regex 대체)
    # ==========================================

    _LLM_EXTRACTION_SYSTEM_PROMPT = """당신은 한국 토지/건축 규제 질문을 분석하여 구조화된 JSON을 반환하는 파서입니다.
반드시 아래 JSON 스키마에 맞게 응답하세요.

{
  "address": {
    "sido": "시/도 정식명칭 또는 빈 문자열",
    "sigungu": "시/군/구 또는 빈 문자열",
    "dong": "읍/면/동/리/가 또는 빈 문자열",
    "lot_number": "지번(예: 1-1040) 또는 빈 문자열",
    "region_code": "시도코드 2자리 또는 빈 문자열"
  },
  "zones": ["용도지역명 정확히"],
  "activities": ["토지이용행위 DB값"],
  "law_reference": "법조문 참조 (예: 건축법제2조제1항제2호) 또는 빈 문자열",
  "special": ["coverage_ratio", "floor_area_ratio", "law_comparison", "height_limit", "floor_limit", "building_permit"],
  "query_fields": ["road_access", "land_area", "terrain", "land_price", "land_shape", "zone_info", "building_info", "coverage_ratio_info", "floor_area_ratio_info"],
  "intent": "CASE1 또는 CASE2 또는 CASE3"
}

## 필드 규칙

### address
- 주소 구성요소만 추출. 법조문 번호(제2조제1항), 용도지역명, 법률 키워드는 주소가 아님
- sido 약칭 → 정식명칭: 서울→서울특별시, 부산→부산광역시, 경기→경기도 등
- region_code: 서울=11, 부산=26, 대구=27, 인천=28, 광주=29, 대전=30, 울산=31, 세종=36, 경기=41, 강원=42, 충북=43, 충남=44, 전북=45, 전남=46, 경북=47, 경남=48, 제주=50

### zones (용도지역 21종)
- 정확한 DB값만 사용: 제1종전용주거지역, 제2종전용주거지역, 제1종일반주거지역, 제2종일반주거지역, 제3종일반주거지역, 준주거지역, 중심상업지역, 일반상업지역, 근린상업지역, 유통상업지역, 전용공업지역, 일반공업지역, 준공업지역, 보전녹지지역, 생산녹지지역, 자연녹지지역, 보전관리지역, 생산관리지역, 계획관리지역, 농림지역, 자연환경보전지역
- 약칭 자동 확장: "제1종주거지역"→["제1종전용주거지역","제1종일반주거지역"], "주거지역"→6종 전부, "상업지역"→4종 전부
- "개발제한구역"은 용도지역이 아님 → zones에 넣지 말 것

### activities (토지이용행위)
- 일상어를 DB값으로 매핑: 카페→휴게음식점, 커피숍→휴게음식점, 식당→일반음식점, 헬스장→체육관, 미용실→미용원 등
- ⚠️ "건축", "건축물", "건축물 종류", "건축 가능한" 등은 activity가 아님. 구체적인 시설(카페, 병원, 학원 등)이 언급되지 않으면 activities는 반드시 빈 배열 []
- "건축법", "건축가능", "건축허가", "건축신고" 등 법률 맥락도 activity 아님
- 예시: "건축 가능한 건축물 종류가 뭐야?" → activities=[] (특정 시설 없음)
- 예시: "카페 건축 가능해?" → activities=["휴게음식점"] (카페가 특정 시설)

### law_reference (법조문 참조)
- 질문에 특정 법조문이 언급되면 해당 법률명을 추출
- 예시: "건축법제2조제1항제2호가 적용되는 곳" → "건축법제2조제1항제2호"
- 예시: "국토계획법 시행령 별표에 나오는" → "국토계획법 시행령"
- 법조문 언급이 없으면 빈 문자열 ""

### special
- 건폐율 → coverage_ratio, 용적률 → floor_area_ratio, 조례/법규비교 → law_comparison, 높이제한 → height_limit, 층수제한 → floor_limit, 건축가능/신축 → building_permit

### query_fields (사용자가 알고 싶은 정보 종류)
- 도로접면/접도 → road_access, 토지면적/대지면적 → land_area, 지형/경사 → terrain, 공시지가/토지가격 → land_price, 토지형상 → land_shape, 용도지역 정보 → zone_info, 건축물 정보 → building_info, 건폐율 → coverage_ratio_info, 용적률 → floor_area_ratio_info

### intent
- CASE1: 주소가 있고 용도지역 없음
- CASE2: 주소와 용도지역 모두 있음
- CASE3: 주소 없이 용도지역이나 행위 또는 법조문 참조가 있음
- 주소도 용도지역도 법조문도 없으면 CASE1
- ⚠️ 용도지역 2개 이상을 비교/차이 질문 → intent="CASE3", zones에 비교 대상 모두 포함"""

    def extract_with_llm(self, question: str) -> Dict[str, Any]:
        """
        gpt-4o-mini 1회 호출로 질문에서 주소/용도지역/행위/특수쿼리를 구조화 추출.
        실패 시 기존 regex fallback.
        """
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self._LLM_EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": question}
                ],
                temperature=0,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content
            parsed = json.loads(raw)
            result = self._transform_llm_extraction(parsed, question)
            logger.info(f"[LLM추출] 성공: zones={result['zone_names']}, activities={result['activities']}, intent={result['intent']['case']}")
            return result

        except Exception as e:
            logger.warning(f"[LLM추출] 실패 ({e}), regex fallback 사용")
            return self._extract_with_regex_fallback(question)

    def _is_comparison_query(self, question: str) -> bool:
        """질문이 용도지역 비교 의도인지 판단"""
        comparison_keywords = ["차이", "비교", "다른점", "다른 점", "뭐가 달라", "뭐가 다른", "어떻게 달라", "어떻게 다른", "vs", "VS", "차이점"]
        return any(kw in question for kw in comparison_keywords)

    def _transform_llm_extraction(self, parsed: Dict, question: str) -> Dict[str, Any]:
        """LLM JSON 응답을 기존 downstream 타입으로 변환"""
        # --- address_info ---
        addr = parsed.get("address", {})
        dong_parts = []
        if addr.get("sido"):
            dong_parts.append(addr["sido"])
        if addr.get("sigungu"):
            dong_parts.append(addr["sigungu"])
        if addr.get("dong"):
            dong_parts.append(addr["dong"])

        address_info = {
            "legal_dong_name": " ".join(dong_parts) if dong_parts else "",
            "lot_number": addr.get("lot_number", ""),
            "region_code": addr.get("region_code", ""),
            "address_depth": 0,
        }
        # address_depth 계산
        if address_info["lot_number"]:
            address_info["address_depth"] = 4
        elif addr.get("dong"):
            address_info["address_depth"] = 3
        elif addr.get("sigungu"):
            address_info["address_depth"] = 2
        elif addr.get("sido"):
            address_info["address_depth"] = 1

        # --- zone_names (ZONE_REGULATIONS 교차 검증) ---
        valid_zones = set(ZONE_REGULATIONS.keys())
        raw_zones = parsed.get("zones", [])
        zone_names = [z for z in raw_zones if z in valid_zones]

        # --- activities (유효값만 필터 + 비특정 "건축물" 제거) ---
        valid_activities = set()
        for v in LAND_USE_DICTIONARY.values():
            if isinstance(v, list):
                valid_activities.update(v)
            else:
                valid_activities.add(v)
        raw_activities = parsed.get("activities", [])
        activities = [a for a in raw_activities if a in valid_activities]
        # "건축물"은 구체적 시설이 아니므로, 단독이면 제거 (카페+건축물처럼 다른 게 있으면 유지)
        if activities == ["건축물"]:
            activities = []

        # --- region_codes ---
        region_codes = []
        if address_info["region_code"]:
            region_codes.append(address_info["region_code"])
        # 5자리 코드도 질문에서 추출
        codes_in_text = re.findall(r'\b\d{5}\b', question)
        region_codes.extend(codes_in_text)
        region_codes = list(set(region_codes))

        # --- special_queries ---
        valid_specials = set(SPECIAL_QUERY_KEYWORDS.values())
        raw_specials = parsed.get("special", [])
        special_queries = [s for s in raw_specials if s in valid_specials]

        # --- query_fields ---
        valid_fields = {
            "road_access", "land_area", "terrain", "land_price",
            "land_shape", "zone_info", "building_info",
            "coverage_ratio_info", "floor_area_ratio_info",
        }
        raw_fields = parsed.get("query_fields", [])
        query_fields = [f for f in raw_fields if f in valid_fields]

        # --- law_reference (LLM 결과 + regex 보완) ---
        law_reference = parsed.get("law_reference", "")
        if not law_reference:
            law_match = re.search(r'((?:건축법|국토계획법|도시계획법|주택법|농지법|산지관리법|도로법)[^\s,?]*(?:제\d+조[^\s,?]*)?)', question)
            if law_match:
                law_reference = law_match.group(1)

        # --- intent ---
        intent_case = parsed.get("intent", "CASE1")
        # classify_intent로 재검증 (LLM intent가 필드와 불일치할 수 있음)
        is_comparison = len(zone_names) >= 2 and self._is_comparison_query(question)
        intent = self.classify_intent(address_info, zone_names, activities, law_reference, is_comparison=is_comparison)

        return {
            "address_info": address_info,
            "zone_names": zone_names,
            "activities": activities,
            "region_codes": region_codes,
            "special_queries": special_queries,
            "query_fields": query_fields,
            "law_reference": law_reference,
            "intent": intent,
            "is_comparison": is_comparison,
        }

    def _extract_with_regex_fallback(self, question: str) -> Dict[str, Any]:
        """기존 regex 메서드 6개를 감싸는 fallback wrapper"""
        question_normalized = self.normalize_query(question)
        address_info = self.parse_address(question_normalized)
        zone_names = self.extract_zone_district_name(question_normalized)
        activities = self.extract_land_use_activity(question_normalized)
        region_codes = self.extract_region_codes(question_normalized)
        special_queries = self.extract_special_queries(question_normalized)

        # law_reference regex 감지
        law_reference = ""
        law_match = re.search(r'((?:건축법|국토계획법|도시계획법|주택법|농지법|산지관리법|도로법)[^\s,?]*(?:제\d+조[^\s,?]*)?)', question)
        if law_match:
            law_reference = law_match.group(1)

        is_comparison = len(zone_names) >= 2 and self._is_comparison_query(question)
        intent = self.classify_intent(address_info, zone_names, activities, law_reference, is_comparison=is_comparison)

        return {
            "address_info": address_info,
            "zone_names": zone_names,
            "activities": activities,
            "region_codes": region_codes,
            "special_queries": special_queries,
            "query_fields": [],
            "law_reference": law_reference,
            "intent": intent,
            "is_comparison": is_comparison,
        }

    def get_zone_regulations(self, zone_name: str) -> Dict[str, Any]:
        """
        특정 용도지역의 건폐율/용적률 등 규제 정보 조회
        1. 먼저 정적 사전(ZONE_REGULATIONS)에서 법정 기준값 조회
        2. DB에서 추가 조건/예외사항 검색
        """
        regulations = {
            "zone_name": zone_name,
            "coverage_ratio": None,
            "coverage_ratio_source": ZONE_REGULATION_SOURCE,
            "floor_area_ratio": None,
            "floor_area_ratio_source": ZONE_REGULATION_SOURCE,
            "height_limit": None,
            "floor_limit": None,
            "total_floor_area_limit": None,
            "front_length_limit": None,
            "setback_distance": None,
            "description": None,
            "raw_data": []
        }

        # 1. 정적 사전에서 기본값 조회
        static_reg = None
        if zone_name in ZONE_REGULATIONS:
            static_reg = ZONE_REGULATIONS[zone_name]
        else:
            for zone_key, reg in ZONE_REGULATIONS.items():
                if zone_key in zone_name or zone_name in zone_key:
                    static_reg = reg
                    break

        if static_reg:
            regulations["coverage_ratio"] = static_reg.get("건폐율")
            regulations["floor_area_ratio"] = static_reg.get("용적률")
            regulations["height_limit"] = static_reg.get("높이")
            regulations["description"] = static_reg.get("설명")

        # 2. DB에서 추가 정보 조회
        if self.db_conn is not None:
            try:
                query = """
                SELECT DISTINCT
                    zone_district_name, law_name,
                    land_use_activity, condition_exception
                FROM law
                WHERE zone_district_name LIKE %s
                  AND (condition_exception LIKE '%%건폐율%%'
                       OR condition_exception LIKE '%%용적률%%'
                       OR condition_exception LIKE '%%높이%%'
                       OR condition_exception LIKE '%%층%%'
                       OR condition_exception LIKE '%%연면적%%'
                       OR condition_exception LIKE '%%제곱미터%%'
                       OR condition_exception LIKE '%%미터%%')
                LIMIT 30
                """

                with self._get_cursor() as cursor:
                    cursor.execute(query, (f"%{zone_name}%",))
                    results = [dict(row) for row in cursor.fetchall()]
                    regulations["raw_data"] = results

                    for r in results:
                        condition = r.get("condition_exception", "") or ""

                        if not regulations["coverage_ratio"]:
                            coverage_match = re.search(r'건폐율\s*(\d+)\s*(%|퍼센트)', condition)
                            if coverage_match:
                                regulations["coverage_ratio"] = f"{coverage_match.group(1)}%"
                                regulations["source"] = "조례"

                        if not regulations["floor_area_ratio"]:
                            far_match = re.search(r'용적률\s*(\d+)\s*(%|퍼센트)', condition)
                            if far_match:
                                regulations["floor_area_ratio"] = f"{far_match.group(1)}%"
                                regulations["source"] = "조례"

                        if not regulations["height_limit"]:
                            height_match = re.search(r'높이\s*(가|는|를|이)?\s*(\d+)\s*(m|미터)\s*(이하|까지|미만)?', condition)
                            if height_match:
                                suffix = height_match.group(4) or "이하"
                                regulations["height_limit"] = f"{height_match.group(2)}m {suffix}"

                        if not regulations["floor_limit"]:
                            floor_match = re.search(r'(\d+)층\s*(이하|까지|미만)?', condition)
                            if floor_match:
                                suffix = floor_match.group(2) or "이하"
                                regulations["floor_limit"] = f"{floor_match.group(1)}층 {suffix}"

                        if not regulations["total_floor_area_limit"]:
                            area_match = re.search(r'연면적\s*([\d,]+)\s*제곱미터\s*(이하|까지|미만)?', condition)
                            if area_match:
                                area_val = area_match.group(1).replace(',', '')
                                suffix = area_match.group(2) or "이하"
                                regulations["total_floor_area_limit"] = f"{int(area_val):,}㎡ {suffix}"
                            else:
                                area_match2 = re.search(r'연면적\s*(\d+)(천|백)\s*제곱미터\s*(이하|까지)?', condition)
                                if area_match2:
                                    num = int(area_match2.group(1))
                                    unit = area_match2.group(2)
                                    if unit == '천':
                                        num *= 1000
                                    elif unit == '백':
                                        num *= 100
                                    suffix = area_match2.group(3) or "이하"
                                    regulations["total_floor_area_limit"] = f"{num:,}㎡ {suffix}"

                        if not regulations["front_length_limit"]:
                            front_match = re.search(r'정면부\s*길이\s*(가|가\s*)?\s*(\d+)\s*(m|미터)\s*(미만|이하)?', condition)
                            if front_match:
                                suffix = front_match.group(4) or "미만"
                                regulations["front_length_limit"] = f"{front_match.group(2)}m {suffix}"

                        if not regulations["setback_distance"]:
                            setback_match = re.search(r'건축선.*?(\d+)\s*(m|미터)\s*(이상)?.*?후퇴', condition)
                            if setback_match:
                                regulations["setback_distance"] = f"{setback_match.group(1)}m 이상 후퇴"

            except Exception as e:
                logger.error(f"DB 규제 정보 조회 실패: {e}")
                if self.db_conn:
                    self.db_conn.rollback()

        return regulations

    def compare_laws(self, zone_name: str) -> Dict[str, Any]:
        """법률과 조례 비교 (건축법 vs 지자체 조례 명확히 구분)"""
        if self.db_conn is None:
            return {}

        try:
            query = """
            SELECT
                zone_district_name, law_name,
                land_use_activity, permission_category, condition_exception
            FROM law
            WHERE zone_district_name LIKE %s
            ORDER BY land_use_activity, law_name
            LIMIT 200
            """

            with self._get_cursor() as cursor:
                cursor.execute(query, (f"%{zone_name}%",))
                results = [dict(row) for row in cursor.fetchall()]

                def classify_law_type(law_name: str) -> str:
                    if not law_name:
                        return "기타"
                    if '건축법' in law_name or '시행령' in law_name or '시행규칙' in law_name:
                        return "건축법"
                    elif '조례' in law_name:
                        return "조례"
                    elif '국토계획' in law_name or '토지이용' in law_name:
                        return "국토계획법"
                    else:
                        return "기타법령"

                building_laws = []
                ordinances = []
                other_laws = []

                for r in results:
                    law_name = r.get("law_name", "")
                    law_type = classify_law_type(law_name)

                    item = {
                        "law_name": law_name,
                        "law_type": law_type,
                        "activity": r.get("land_use_activity", ""),
                        "permission_category": r.get("permission_category", ""),
                        "condition": r.get("condition_exception", "") or "조건 없음"
                    }

                    if law_type == "건축법":
                        building_laws.append(item)
                    elif law_type == "조례":
                        ordinances.append(item)
                    else:
                        other_laws.append(item)

                ordinance_by_region = {}
                for o in ordinances:
                    law_name = o["law_name"]
                    region = law_name.split("조례")[0].replace("도시계획", "").replace("군계획", "")
                    if not region:
                        region = law_name[:4]

                    if region not in ordinance_by_region:
                        ordinance_by_region[region] = []
                    ordinance_by_region[region].append(o)

                activity_comparison = {}
                all_items = building_laws + ordinances + other_laws

                for item in all_items:
                    activity = item["activity"]
                    if activity not in activity_comparison:
                        activity_comparison[activity] = {
                            "건축법": [],
                            "조례": [],
                            "기타": []
                        }

                    if item["law_type"] == "건축법":
                        activity_comparison[activity]["건축법"].append(item)
                    elif item["law_type"] == "조례":
                        activity_comparison[activity]["조례"].append(item)
                    else:
                        activity_comparison[activity]["기타"].append(item)

                valuable_comparisons = []
                for activity, laws in activity_comparison.items():
                    if laws["건축법"] and laws["조례"]:
                        valuable_comparisons.append({
                            "activity": activity,
                            "building_law": laws["건축법"][0],
                            "ordinances": laws["조례"][:5],
                            "has_difference": True
                        })
                    elif laws["건축법"]:
                        valuable_comparisons.append({
                            "activity": activity,
                            "building_law": laws["건축법"][0],
                            "ordinances": [],
                            "has_difference": False
                        })

                return {
                    "zone_name": zone_name,
                    "total_items": len(results),
                    "building_law_count": len(building_laws),
                    "ordinance_count": len(ordinances),
                    "ordinance_regions": list(ordinance_by_region.keys())[:10],
                    "comparisons": valuable_comparisons[:15],
                    "sample_ordinances": ordinances[:10],
                }

        except Exception as e:
            logger.error(f"법률 비교 조회 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return {}

    def search_by_address(self, address_info: Dict[str, str], zone_filter: List[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        주소 정보로 land_char 테이블에서 필지 검색

        [V2 변경] address_depth <= 2 (구 단위)일 때 동별 샘플링
        - 기존: ORDER BY lot_number LIMIT 6 → 한 동만 나옴
        - 변경: 각 동에서 1~2개씩 골고루 샘플링
        """
        try:
            conditions = []
            params = []

            if address_info.get("legal_dong_name"):
                dong_parts = address_info["legal_dong_name"].split()
                for part in dong_parts:
                    conditions.append("legal_dong_name LIKE %s")
                    params.append(f"%{part}%")

            if address_info.get("lot_number"):
                lot_num = address_info['lot_number']
                if '-' in lot_num:
                    conditions.append("lot_number = %s")
                    params.append(lot_num)
                else:
                    conditions.append("(lot_number = %s OR lot_number LIKE %s)")
                    params.append(lot_num)
                    params.append(f"{lot_num}-%")

            if address_info.get("region_code"):
                conditions.append("region_code LIKE %s")
                params.append(f"{address_info['region_code']}%")

            if zone_filter:
                zone_conds = []
                for zone in zone_filter:
                    zone_conds.append("zone1 LIKE %s")
                    params.append(f"%{zone}%")
                conditions.append(f"({' OR '.join(zone_conds)})")

            if not conditions:
                return []

            depth = address_info.get("address_depth", 0)

            # [V2 변경] depth <= 2 (구 단위): 동별 샘플링으로 골고루 가져오기
            if depth <= 2 and not address_info.get("lot_number"):
                return self._search_by_dong_sampling(conditions, params, zone_filter, limit)

            # depth 3~4 (동/지번까지): 기존 방식
            query = f"""
            SELECT DISTINCT
                legal_dong_name, lot_number, region_code,
                zone1, zone2, land_category, land_use,
                land_area, terrain_height, terrain_shape, road_access
            FROM land_char
            WHERE {' AND '.join(conditions)}
            ORDER BY lot_number
            LIMIT {limit}
            """

            with self._get_cursor() as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()

                land_infos = [dict(row) for row in results]
                logger.info(f"주소 검색 결과: {len(land_infos)}개")
                return land_infos

        except Exception as e:
            logger.error(f"주소 검색 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []

    def _search_by_dong_sampling(
        self,
        conditions: List[str],
        params: List[Any],
        zone_filter: List[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        [V2 변경] 동별 샘플링 검색 (단일 윈도우 함수 쿼리)
        - ROW_NUMBER() OVER(PARTITION BY legal_dong_name)로 동별 N개씩 추출
        - 기존 N+1 쿼리 → 1회 쿼리로 개선
        """
        try:
            where_clause = ' AND '.join(conditions)
            per_dong = 2  # 동별 최대 2개

            query = f"""
            SELECT legal_dong_name, lot_number, region_code,
                   zone1, zone2, land_category, land_use,
                   land_area, terrain_height, terrain_shape, road_access
            FROM (
                SELECT DISTINCT
                    legal_dong_name, lot_number, region_code,
                    zone1, zone2, land_category, land_use,
                    land_area, terrain_height, terrain_shape, road_access,
                    ROW_NUMBER() OVER(PARTITION BY legal_dong_name ORDER BY lot_number) AS rn
                FROM land_char
                WHERE {where_clause}
            ) sub
            WHERE rn <= {per_dong}
            ORDER BY legal_dong_name, lot_number
            LIMIT {limit}
            """

            with self._get_cursor() as cursor:
                cursor.execute(query, params)
                all_results = [dict(row) for row in cursor.fetchall()]

            logger.info(f"[동별 샘플링] 단일 쿼리로 {len(all_results)}개 필지 검색")
            return all_results

        except Exception as e:
            logger.error(f"동별 샘플링 검색 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []

    def search_by_zone_district(self, zone_names: List[str], region_filter: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """지역지구명으로 law 테이블에서 검색"""
        if self.db_conn is None or not zone_names:
            return []

        try:
            params = []
            zone_conditions = []
            for zone in zone_names:
                zone_conditions.append("zone_district_name LIKE %s")
                params.append(f"%{zone}%")

            where_clause = f"({' OR '.join(zone_conditions)})"

            if region_filter and region_filter.get("region_code"):
                where_clause += " AND region_code LIKE %s"
                params.append(f"{region_filter['region_code']}%")

            query = f"""
            SELECT DISTINCT
                region_code, zone_district_name, law_name,
                land_use_activity, permission_category, condition_exception
            FROM law
            WHERE {where_clause}
            ORDER BY zone_district_name
            LIMIT 50
            """

            with self._get_cursor() as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()

                law_infos = [dict(row) for row in results]
                logger.info(f"지역지구명 검색 결과: {len(law_infos)}개")
                return law_infos

        except Exception as e:
            logger.error(f"지역지구명 검색 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []

    def search_by_land_use(self, activities: List[str], zone_name: str = None, region_filter: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """토지이용행위로 law 테이블에서 검색"""
        if self.db_conn is None or not activities:
            return []

        try:
            params = []
            conditions = []

            activity_conditions = []
            for activity in activities:
                activity_conditions.append("land_use_activity LIKE %s")
                params.append(f"%{activity}%")
            conditions.append(f"({' OR '.join(activity_conditions)})")

            if zone_name:
                conditions.append("zone_district_name LIKE %s")
                params.append(f"%{zone_name}%")

            if region_filter and region_filter.get("region_code"):
                conditions.append("region_code LIKE %s")
                params.append(f"{region_filter['region_code']}%")

            query = f"""
            SELECT DISTINCT
                region_code, zone_district_name, law_name,
                land_use_activity, permission_category, condition_exception
            FROM law
            WHERE {' AND '.join(conditions)}
            LIMIT 50
            """

            with self._get_cursor() as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()

                law_infos = [dict(row) for row in results]
                logger.info(f"토지이용행위 검색 결과: {len(law_infos)}개")
                return law_infos

        except Exception as e:
            logger.error(f"토지이용행위 검색 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []

    def get_zones_by_region(self, region_filter: Dict[str, str]) -> List[str]:
        """특정 지역의 지역지구명 목록 조회"""
        if self.db_conn is None:
            return []

        try:
            if not region_filter.get("region_code"):
                return []

            query = """
            SELECT DISTINCT zone_district_name
            FROM law
            WHERE region_code LIKE %s
            ORDER BY zone_district_name
            """

            with self._get_cursor() as cursor:
                cursor.execute(query, (f"{region_filter['region_code']}%",))
                results = cursor.fetchall()

                zones = [row['zone_district_name'] for row in results]
                logger.info(f"지역 내 지역지구명 {len(zones)}개 조회")
                return zones

        except Exception as e:
            logger.error(f"지역지구명 목록 조회 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []

    # ==========================================
    # 2단계: 케이스 분기 로직
    # ==========================================

    def classify_intent(self, address_info: Dict[str, str], zone_names: List[str], activities: List[str], law_reference: str = "", is_comparison: bool = False) -> Dict[str, Any]:
        """질문 의도 분류 (Case1/Case2/Case3 판단)"""
        has_address = bool(address_info.get("legal_dong_name"))
        has_lot_number = bool(address_info.get("lot_number"))
        has_zone = bool(zone_names)
        has_activity = bool(activities)
        has_law_ref = bool(law_reference)

        if has_address and has_zone:
            return {
                "case": "CASE2",
                "sub_case": "2-1",
                "description": "주소와 용도지역이 함께 입력됨"
            }

        if not has_address and (has_zone or has_activity or has_law_ref):
            if has_law_ref and not has_zone and not has_activity:
                return {
                    "case": "CASE3",
                    "sub_case": "3-4",
                    "description": "법조문 기반 검색 (주소 없음)"
                }

            # CASE3-5: 용도지역 비교 (2개 이상 + 비교 키워드)
            if is_comparison and len(zone_names) >= 2:
                return {
                    "case": "CASE3",
                    "sub_case": "3-5",
                    "description": "용도지역 비교 질문"
                }

            elif has_zone and has_activity:
                return {
                    "case": "CASE3",
                    "sub_case": "3-1",
                    "description": "용도지역 + 토지이용행위 질문 (주소 없음)"
                }
            elif has_zone:
                return {
                    "case": "CASE3",
                    "sub_case": "3-2",
                    "description": "용도지역만 질문 (주소 없음)"
                }
            else:
                return {
                    "case": "CASE3",
                    "sub_case": "3-3",
                    "description": "토지이용행위만 질문 (주소 없음)"
                }

        if has_lot_number:
            return {
                "case": "CASE1",
                "sub_case": "1-1",
                "description": "지번까지 상세 입력됨"
            }
        elif has_address:
            return {
                "case": "CASE1",
                "sub_case": "1-3",
                "description": "법정동까지만 입력됨"
            }
        else:
            return {
                "case": "CASE1",
                "sub_case": "1-0",
                "description": "주소 정보 불충분"
            }

    # ==========================================
    # 4단계: 법규 검토 및 계산
    # ==========================================

    def match_land_to_law(self, land_info: Dict[str, Any], activities: List[str] = None) -> Dict[str, Any]:
        """단일 필지와 법규 1:1 매칭"""
        if self.db_conn is None:
            return {"land": land_info, "laws": [], "feasibility": "판정불가"}

        try:
            zones = []
            if land_info.get("zone1"):
                zones.append(land_info["zone1"])
            if land_info.get("zone2") and land_info.get("zone2") != "지정되지않음":
                zones.append(land_info["zone2"])

            if not zones:
                return {"land": land_info, "laws": [], "feasibility": "용도지역 정보 없음"}

            params = []
            conditions = []

            zone_conditions = []
            for zone in zones:
                zone_conditions.append("zone_district_name LIKE %s")
                params.append(f"%{zone}%")
            conditions.append(f"({' OR '.join(zone_conditions)})")

            if activities:
                activity_conditions = []
                for activity in activities:
                    activity_conditions.append("land_use_activity LIKE %s")
                    params.append(f"%{activity}%")
                conditions.append(f"({' OR '.join(activity_conditions)})")

            where_clause = " AND ".join(conditions)

            query = f"""
            SELECT
                region_code, zone_district_name, law_name,
                land_use_activity, permission_category, condition_exception
            FROM law
            WHERE {where_clause}
            LIMIT 20
            """

            with self._get_cursor() as cursor:
                cursor.execute(query, params)
                laws = [dict(row) for row in cursor.fetchall()]

            feasibility = self.analyze_feasibility(laws)

            return {
                "land": land_info,
                "laws": laws,
                "feasibility": feasibility
            }

        except Exception as e:
            logger.error(f"필지-법규 매칭 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return {"land": land_info, "laws": [], "feasibility": "판정 오류"}

    def analyze_feasibility(self, laws: List[Dict[str, Any]]) -> Dict[str, Any]:
        """법규 기반 개발가능성 분석 (개발성적표)"""
        if not laws:
            return {
                "status": "정보부족",
                "allowed": [],
                "conditional": [],
                "prohibited": [],
                "summary": "해당 조건에 맞는 법규 정보를 찾을 수 없습니다."
            }

        allowed = []
        conditional = []
        prohibited = []

        for law in laws:
            activity = law.get("land_use_activity", "")
            permission = law.get("permission_category", "")
            condition = law.get("condition_exception", "")

            permission_lower = permission.lower() if permission else ""

            if "불가" in permission_lower or "금지" in permission_lower or "불허" in permission_lower:
                prohibited.append({
                    "activity": activity,
                    "reason": condition if condition else "법규상 금지"
                })
            elif "가능" in permission_lower or "허용" in permission_lower:
                if condition and len(condition) > 5:
                    conditional.append({
                        "activity": activity,
                        "condition": condition
                    })
                else:
                    allowed.append(activity)
            elif condition and len(condition) > 5:
                conditional.append({
                    "activity": activity,
                    "condition": condition
                })

        if prohibited and not allowed and not conditional:
            status = "불가"
            summary = f"해당 행위는 법규상 금지되어 있습니다. (금지 항목: {len(prohibited)}건)"
        elif allowed and not prohibited:
            status = "가능"
            summary = f"해당 행위는 가능합니다. (허용 항목: {len(allowed)}건)"
        elif allowed and prohibited:
            # [V2 버그픽스] 같은 행위가 법률/지자체별로 가능·금지 혼재 시
            # "검토필요" 대신 비율 기반 판정
            if len(allowed) >= len(prohibited):
                status = "조건부가능"
                summary = (f"대부분 가능하나 일부 법규에서 제한됩니다. "
                           f"(허용: {len(allowed)}건, 금지: {len(prohibited)}건, 조건부: {len(conditional)}건)")
            else:
                status = "조건부가능"
                summary = (f"일부 법규에서 허용하나 제한이 많습니다. "
                           f"(허용: {len(allowed)}건, 금지: {len(prohibited)}건, 조건부: {len(conditional)}건)")
        elif conditional:
            status = "조건부가능"
            summary = f"조건 충족 시 가능합니다. (조건부: {len(conditional)}건, 허용: {len(allowed)}건)"
        else:
            status = "검토필요"
            summary = "상세 검토가 필요합니다."

        return {
            "status": status,
            "allowed": allowed[:5],
            "conditional": conditional[:5],
            "prohibited": prohibited[:5],
            "summary": summary
        }

    def check_zone_match(self, land_info: Dict[str, Any], user_zones: List[str]) -> Dict[str, Any]:
        """사용자 입력 용도지역과 실제 데이터 일치 여부 확인"""
        land_zones = []
        if land_info.get("zone1"):
            land_zones.append(land_info["zone1"])
        if land_info.get("zone2"):
            land_zones.append(land_info["zone2"])

        if not land_zones:
            return {
                "match_type": "정보없음",
                "land_zones": [],
                "user_zones": user_zones,
                "message": "해당 필지의 용도지역 정보가 없습니다."
            }

        if not user_zones:
            return {
                "match_type": "일치",
                "land_zones": land_zones,
                "user_zones": [],
                "message": "사용자가 용도지역을 지정하지 않았습니다."
            }

        matched = []
        unmatched_user = []

        for user_zone in user_zones:
            found = False
            for land_zone in land_zones:
                if user_zone in land_zone or land_zone in user_zone:
                    matched.append((user_zone, land_zone))
                    found = True
                    break
            if not found:
                unmatched_user.append(user_zone)

        if len(matched) == len(user_zones):
            return {
                "match_type": "일치",
                "land_zones": land_zones,
                "user_zones": user_zones,
                "message": f"입력한 용도지역({', '.join(user_zones)})이 실제 필지와 일치합니다."
            }
        elif matched:
            return {
                "match_type": "부분일치",
                "land_zones": land_zones,
                "user_zones": user_zones,
                "matched": matched,
                "unmatched": unmatched_user,
                "message": f"일부 용도지역만 일치합니다. 실제: {', '.join(land_zones)}, 불일치: {', '.join(unmatched_user)}"
            }
        else:
            return {
                "match_type": "불일치",
                "land_zones": land_zones,
                "user_zones": user_zones,
                "message": f"입력한 용도지역({', '.join(user_zones)})이 실제({', '.join(land_zones)})와 다릅니다."
            }

    def _get_allowed_zones_for_activity(self, activities: List[str]) -> List[str]:
        """
        [V2 변경] 토지이용행위가 가능한 용도지역 역추적
        - law 테이블에서 해당 행위가 '건축가능'인 용도지역 목록 조회
        - "노원구에서 아파트 가능한 곳" → 아파트 가능 용도지역 → zone_filter로 활용
        """
        if self.db_conn is None or not activities:
            return []

        try:
            # 표준 용도지역만 필터 (특수지역 제외)
            standard_zones = list(ZONE_REGULATIONS.keys())
            zone_placeholders = ','.join(['%s'] * len(standard_zones))

            activity_conditions = []
            params = []
            for activity in activities[:3]:  # 최대 3개 행위
                activity_conditions.append("land_use_activity LIKE %s")
                params.append(f"%{activity}%")

            params.extend(standard_zones)

            query = f"""
            SELECT DISTINCT zone_district_name
            FROM law
            WHERE ({' OR '.join(activity_conditions)})
              AND permission_category LIKE '%%가능%%'
              AND zone_district_name IN ({zone_placeholders})
            ORDER BY zone_district_name
            """

            with self._get_cursor() as cursor:
                cursor.execute(query, params)
                zones = [row['zone_district_name'] for row in cursor.fetchall()]

            logger.info(f"[역추적] {activities} → 가능 용도지역 {len(zones)}개: {zones[:5]}")
            return zones

        except Exception as e:
            logger.error(f"용도지역 역추적 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []

    def process_case1(self, address_info: Dict[str, str], activities: List[str]) -> Dict[str, Any]:
        """
        Case 1 처리: 주소만 입력된 경우
        [V2 변경] 행위가 있고 depth <= 2면, 가능한 용도지역으로 zone_filter 적용
        """
        depth = address_info.get("address_depth", 0)

        # [V2 변경] "노원구에서 아파트 가능한 곳" → 아파트 가능 용도지역으로 필터
        zone_filter = None
        if activities and depth <= 2:
            zone_filter = self._get_allowed_zones_for_activity(activities)

        if zone_filter:
            lands = self.search_by_address(address_info, zone_filter=zone_filter, limit=10)
        else:
            lands = self.search_by_address(address_info, limit=6)

        # [V2 변경] zone_filter로 못 찾으면 필터 없이 재시도
        if not lands and zone_filter:
            lands = self.search_by_address(address_info, limit=6)

        if not lands:
            return {
                "case": "CASE1",
                "sub_case": "1-0",
                "message": "해당 주소의 필지를 찾을 수 없습니다.",
                "lands": [],
                "analysis": []
            }

        if len(lands) == 1:
            sub_case = "1-1"
            message = "지번 정확히 매칭됨 (1필지)"
        else:
            sub_case = "1-2"
            message = f"복수 필지 검색됨 ({len(lands)}필지)"

        analysis_results = []
        for land in lands:
            result = self.match_land_to_law(land, activities)
            analysis_results.append(result)

        comparison = None
        if sub_case == "1-2":
            comparison = self.compare_lands(analysis_results)

        return {
            "case": "CASE1",
            "sub_case": sub_case,
            "message": message,
            "lands": lands,
            "analysis": analysis_results,
            "comparison": comparison
        }

    def process_case2(self, address_info: Dict[str, str], zone_names: List[str], activities: List[str]) -> Dict[str, Any]:
        """
        Case 2 처리: 주소 + 용도지역 입력된 경우
        address_depth에 따라 검색 전략 변경
        """
        depth = address_info.get("address_depth", 0)

        if depth >= 4:
            lands = self.search_by_address(address_info, limit=6)
        else:
            lands = self.search_by_address(address_info, zone_filter=zone_names, limit=6)

            if not lands:
                lands = self.search_by_address(address_info, limit=6)

        if not lands:
            return {
                "case": "CASE2",
                "sub_case": "2-0",
                "message": "해당 주소의 필지를 찾을 수 없어 용도지역 기준으로만 검색합니다.",
                "zone_match": None,
                "analysis": self.search_by_zone_district(zone_names)
            }

        zone_match = self.check_zone_match(lands[0], zone_names)

        if zone_match["match_type"] == "일치":
            sub_case = "2-1"
        elif zone_match["match_type"] == "부분일치":
            sub_case = "2-3"
        else:
            sub_case = "2-2"

        analysis_results = []
        for land in lands:
            result = self.match_land_to_law(land, activities)
            result["zone_match"] = self.check_zone_match(land, zone_names)
            analysis_results.append(result)

        return {
            "case": "CASE2",
            "sub_case": sub_case,
            "message": zone_match["message"],
            "zone_match": zone_match,
            "lands": lands,
            "analysis": analysis_results
        }

    def process_case3(self, zone_names: List[str], activities: List[str], law_reference: str = "", is_comparison: bool = False) -> Dict[str, Any]:
        """Case 3 처리: 주소 없이 용도지역/토지이용행위/법조문 질문"""
        results = []

        # CASE3-4: 법조문 기반 검색
        if law_reference and not zone_names and not activities:
            law_results = self.search_by_law_name(law_reference)

            return {
                "case": "CASE3",
                "sub_case": "3-4",
                "message": f"'{law_reference}' 관련 법규 검색 결과",
                "laws": law_results,
                "analysis": [{"law_reference": law_reference, "laws": law_results}]
            }

        # CASE3-5: 용도지역 비교
        if is_comparison and len(zone_names) >= 2:
            comparison_data = []
            for zone in zone_names[:4]:  # 최대 4개 비교
                reg = ZONE_REGULATIONS.get(zone, {})
                # DB에서 해당 용도지역의 허용행위 조회
                zone_laws = self.search_by_zone_district([zone])
                # 허용/조건부/불허 카운트
                allowed = [l for l in zone_laws if l.get("permission_category") == "허용"]
                conditional = [l for l in zone_laws if l.get("permission_category") == "조건부허용"]
                prohibited = [l for l in zone_laws if l.get("permission_category") == "불허"]

                comparison_data.append({
                    "zone": zone,
                    "건폐율": reg.get("건폐율", "정보없음"),
                    "용적률": reg.get("용적률", "정보없음"),
                    "높이": reg.get("높이", "정보없음"),
                    "설명": reg.get("설명", ""),
                    "허용_수": len(allowed),
                    "조건부_수": len(conditional),
                    "불허_수": len(prohibited),
                    "허용_예시": [l.get("land_use_activity", "") for l in allowed[:5]],
                    "조건부_예시": [l.get("land_use_activity", "") for l in conditional[:5]],
                })

            return {
                "case": "CASE3",
                "sub_case": "3-5",
                "message": f"용도지역 비교: {', '.join(zone_names[:4])}",
                "comparison": comparison_data,
                "analysis": comparison_data,
            }

        if zone_names and activities:
            for zone in zone_names[:3]:
                zone_results = self.search_by_land_use(activities, zone_name=zone)
                if zone_results:
                    feasibility = self.analyze_feasibility(zone_results)
                    results.append({
                        "zone": zone,
                        "activities": activities,
                        "laws": zone_results,
                        "feasibility": feasibility
                    })

            return {
                "case": "CASE3",
                "sub_case": "3-1",
                "message": f"용도지역({', '.join(zone_names)})에서 {', '.join(activities)} 검색 결과",
                "results": results,
                "analysis": results
            }

        elif zone_names:
            zone_results = self.search_by_zone_district(zone_names)
            feasibility = self.analyze_feasibility(zone_results) if zone_results else None

            return {
                "case": "CASE3",
                "sub_case": "3-2",
                "message": f"용도지역({', '.join(zone_names)}) 관련 법규 검색 결과",
                "laws": zone_results,
                "feasibility": feasibility,
                "analysis": [{"zone": zone_names, "laws": zone_results, "feasibility": feasibility}]
            }

        elif activities:
            activity_results = self.search_by_land_use(activities)
            feasibility = self.analyze_feasibility(activity_results) if activity_results else None

            return {
                "case": "CASE3",
                "sub_case": "3-3",
                "message": f"{', '.join(activities)} 관련 법규 검색 결과",
                "laws": activity_results,
                "feasibility": feasibility,
                "analysis": [{"activities": activities, "laws": activity_results, "feasibility": feasibility}]
            }

        return {
            "case": "CASE3",
            "sub_case": "3-0",
            "message": "검색 조건 없음",
            "analysis": []
        }

    def search_by_law_name(self, law_reference: str, limit: int = 30) -> List[Dict[str, Any]]:
        """법률명으로 law 테이블 검색 (CASE3-4용, 공백 무시 매칭)"""
        if self.db_conn is None:
            return []

        try:
            # 공백 제거 후 비교 (DB: "별표 1  제10호" vs 입력: "별표1 제10호")
            normalized = re.sub(r'\s+', '', law_reference)
            query = """
            SELECT DISTINCT
                zone_district_name, law_name,
                land_use_activity, permission_category, condition_exception
            FROM law
            WHERE REPLACE(REPLACE(law_name, ' ', ''), '　', '') LIKE %s
            ORDER BY zone_district_name, land_use_activity
            LIMIT %s
            """

            with self._get_cursor() as cursor:
                cursor.execute(query, (f"%{normalized}%", limit))
                results = [dict(row) for row in cursor.fetchall()]
                logger.info(f"[CASE3-4] 법률명 검색 '{law_reference}' (normalized: '{normalized}'): {len(results)}건")
                return results

        except Exception as e:
            logger.error(f"법률명 검색 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []

    def compare_lands(self, analysis_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """복수 필지 비교 분석 (개발성적표)"""
        comparison = {
            "total_count": len(analysis_results),
            "developable": [],
            "conditional": [],
            "not_developable": [],
            "summary": ""
        }

        for i, result in enumerate(analysis_results):
            land = result.get("land", {})
            feasibility = result.get("feasibility", {})
            status = feasibility.get("status", "정보부족") if isinstance(feasibility, dict) else feasibility

            lot_info = f"{land.get('lot_number', '?')} ({land.get('zone1', '?')})"

            if status == "가능":
                comparison["developable"].append(lot_info)
            elif status == "조건부가능":
                comparison["conditional"].append(lot_info)
            elif status == "불가":
                comparison["not_developable"].append(lot_info)

        parts = []
        if comparison["developable"]:
            parts.append(f"개발가능: {', '.join(comparison['developable'])}")
        if comparison["conditional"]:
            parts.append(f"조건부: {', '.join(comparison['conditional'])}")
        if comparison["not_developable"]:
            parts.append(f"불가: {', '.join(comparison['not_developable'])}")

        comparison["summary"] = " | ".join(parts) if parts else "분석 결과 없음"

        return comparison

    def _get_keyword_mapping_notes(self, text: str) -> str:
        """사용자 키워드 → DB 법적 분류 매핑 설명 생성
        GPT가 '다가구주택 = 단독주택(법적 분류)' 등을 이해할 수 있도록 컨텍스트에 추가
        """
        # 법률 용어 안의 "건축" 오탐 방지 (extract_land_use_activity와 동일 로직)
        legal_suffixes = ['법', '가능', '금지', '불가', '조례', '선', '허가', '신고', '법시행령']

        # 매칭 키워드 수집 (extract_land_use_activity와 동일한 부분문자열 필터링)
        matched_keywords = []
        for keyword in LAND_USE_DICTIONARY.keys():
            if keyword in text:
                if keyword == '건축':
                    if any(f"건축{suffix}" in text for suffix in legal_suffixes):
                        continue
                matched_keywords.append(keyword)

        matched_keywords.sort(key=len, reverse=True)
        filtered = []
        for kw in matched_keywords:
            if not any(kw in longer and kw != longer for longer in filtered):
                filtered.append(kw)

        # 매핑 노트 생성 (키워드 ≠ DB값인 경우만)
        notes = []
        seen = set()
        for kw in filtered:
            db_vals = LAND_USE_DICTIONARY[kw]
            vals = db_vals if isinstance(db_vals, list) else [db_vals]
            for val in vals:
                if val != kw and (kw, val) not in seen:
                    notes.append(f"- '{kw}'은(는) 건축법상 '{val}'으로 분류됩니다. 동일한 항목입니다.")
                    seen.add((kw, val))

        return "\n".join(notes) if notes else ""

    # ==========================================
    # [V2 변경] _build_context - Reranker + 캐싱 + k값 최적화
    # ==========================================

    def _build_context(
        self,
        case_result: Dict[str, Any],
        special_data: Dict[str, Any],
        email: str,
        question_normalized: str,
        query_fields: List[str] = None
    ) -> str:
        """
        LLM에 전달할 컨텍스트 구성

        [V2 변경사항]
        - 임베딩 캐싱 (get_embedding_cached)
        - k=2 → k=15 확대 후 Reranker로 top 3~5 선택
        - 질문 유형별 k값 차등 적용
        - query_fields: LLM 추출에서 얻은 사용자 관심 정보 종류
        """
        context_parts = []

        # [사용자 질문 핵심] — query_fields가 있으면 상단에 삽입
        if query_fields:
            field_labels = {
                "road_access": "도로접면 정보",
                "land_area": "토지면적/대지면적",
                "terrain": "지형/경사 정보",
                "land_price": "공시지가/토지가격",
                "land_shape": "토지형상",
                "zone_info": "용도지역 정보",
                "building_info": "건축물 정보",
                "coverage_ratio_info": "건폐율",
                "floor_area_ratio_info": "용적률",
            }
            labels = [field_labels.get(f, f) for f in query_fields]
            context_parts.append(
                f"[사용자 질문 핵심]\n"
                f"사용자가 알고 싶어하는 정보: {', '.join(labels)}\n"
                f"→ 이 정보를 중심으로 답변하세요.\n"
            )

        # 케이스 정보
        context_parts.append(
            f"[분석 케이스]\n{case_result['case']}-{case_result['sub_case']}: {case_result['message']}\n"
        )

        # [V2 버그픽스] 키워드 매핑 정보 (GPT가 사용자 키워드 ↔ DB 법적 분류 관계를 이해하도록)
        mapping_notes = self._get_keyword_mapping_notes(question_normalized)
        if mapping_notes:
            context_parts.append(f"[키워드 매핑 (법적 분류)]\n{mapping_notes}\n")

        # 용도지역 일치 여부 (Case2)
        if case_result.get("zone_match"):
            zm = case_result["zone_match"]
            context_parts.append(
                f"[용도지역 검증]\n"
                f"- 판정: {zm['match_type']}\n"
                f"- 실제 용도지역: {', '.join(zm.get('land_zones', []))}\n"
                f"- 입력 용도지역: {', '.join(zm.get('user_zones', []))}\n"
                f"- 설명: {zm['message']}\n"
                f"※ 불일치여도 아래 데이터는 실제 용도지역 기준으로 정확합니다. 반드시 활용하세요.\n"
            )

        # 필지별 분석 결과 (Case 1, 2)
        if case_result.get("analysis") and case_result["case"] != "CASE3":
            context_parts.extend(self._build_land_analysis_context(case_result["analysis"]))

        # CASE3-5: 용도지역 비교
        elif case_result.get("sub_case") == "3-5" and case_result.get("comparison"):
            comp_data = case_result["comparison"]
            context_parts.append("[용도지역 비교 데이터]")
            context_parts.append(f"비교 대상: {', '.join(c['zone'] for c in comp_data)}\n")

            # 비교표 형식
            header = "| 항목 | " + " | ".join(c["zone"] for c in comp_data) + " |"
            sep = "|---" * (len(comp_data) + 1) + "|"
            rows = [
                "| 건폐율 | " + " | ".join(c["건폐율"] for c in comp_data) + " |",
                "| 용적률 | " + " | ".join(c["용적률"] for c in comp_data) + " |",
                "| 높이제한 | " + " | ".join(c["높이"] for c in comp_data) + " |",
                "| 특성 | " + " | ".join(c["설명"] for c in comp_data) + " |",
                "| 허용행위 수 | " + " | ".join(str(c["허용_수"]) for c in comp_data) + " |",
                "| 조건부허용 수 | " + " | ".join(str(c["조건부_수"]) for c in comp_data) + " |",
                "| 불허 수 | " + " | ".join(str(c["불허_수"]) for c in comp_data) + " |",
            ]
            context_parts.append(header)
            context_parts.append(sep)
            context_parts.extend(rows)
            context_parts.append("")

            # 허용 행위 예시
            for c in comp_data:
                if c["허용_예시"]:
                    context_parts.append(f"[{c['zone']} 허용 행위 예시] {', '.join(c['허용_예시'])}")
                if c["조건부_예시"]:
                    context_parts.append(f"[{c['zone']} 조건부 행위 예시] {', '.join(c['조건부_예시'])}")

        # Case 3 분석 결과
        elif case_result.get("analysis") and case_result["case"] == "CASE3":
            context_parts.extend(self._build_case3_context(case_result["analysis"]))

        # 비교 분석 (Case1-2: 복수 필지)
        if case_result.get("comparison") and case_result.get("sub_case") != "3-5":
            comp = case_result["comparison"]
            context_parts.append(
                f"[복수 필지 비교 분석]\n"
                f"- 총 {comp['total_count']}개 필지 분석\n"
                f"- {comp['summary']}\n"
            )

        # 특수 쿼리 결과
        context_parts.extend(self._build_special_query_context(special_data))

        # 이전 대화
        chat_history = self.get_recent_chat_history(email, limit=3)
        if chat_history:
            history_text = "\n".join([
                f"Q: {h['question']}\nA: {h['answer']}"
                for h in chat_history[:2]
            ])
            context_parts.append(f"[이전 대화]\n{history_text}\n")

        # [V2 변경] RAG 검색 (캐싱 + k값 확대 + Reranker)
        try:
            # [V2 변경] 질문 유형별 k값 차등 적용
            case_type = case_result.get("case", "CASE1")
            if case_type == "CASE3":
                # 단순 질문: 후보 적게, 최종도 적게
                initial_k = 10
                final_top_n = 3
            else:
                # 복합 질문 (CASE1/2: 주소+행위): 후보 넓게
                initial_k = 15  # [V2 변경] 기존 k=2 → k=15
                final_top_n = 5

            # [V2 변경] 캐시된 임베딩 사용
            question_embedding = self.get_embedding_cached(question_normalized)

            # [V2 변경] 넓은 후보군 검색
            rag_results = pgvector_service.search_internal_eval(
                query_embedding=question_embedding,
                k=initial_k  # [V2 변경] k=2 → k=10~15
            )

            if rag_results:
                # [V2 변경] Reranker로 재정렬
                reranked = self._rerank_results(
                    query=question_normalized,
                    results=rag_results,
                    top_n=final_top_n
                )

                for i, result in enumerate(reranked, 1):
                    # [V2 변경] rerank_score가 있으면 표시
                    score_info = ""
                    if result.get("rerank_score") is not None:
                        score_info = f" (관련도: {result['rerank_score']:.3f})"
                    context_parts.append(f"[참고 평면도 {i}]{score_info}\n{result['document']}\n")

                logger.info(
                    f"[V2 RAG] 검색 k={initial_k} → Rerank top={final_top_n}, "
                    f"최종 {len(reranked)}개 사용"
                )

        except Exception as e:
            logger.warning(f"RAG 검색 실패: {e}")

        return "\n".join(context_parts) if context_parts else "참고할 데이터가 없습니다."

    def _build_land_analysis_context(self, analysis_list: List[Dict[str, Any]]) -> List[str]:
        """필지별 분석 결과 컨텍스트 (Case 1, 2)"""
        context_parts = []

        # [V2 버그픽스] 유의미한 필지만 필터링 (빈 필지 제거)
        valid_index = 0
        for i, analysis in enumerate(analysis_list, 1):
            land = analysis.get("land", {})
            feasibility = analysis.get("feasibility", {})

            # 빈 필지 스킵: 주소/용도지역 없는 항목
            if not land.get("legal_dong_name") and not land.get("zone1"):
                continue
            if land.get("zone1", "-") == "-" and not land.get("lot_number"):
                continue
            valid_index += 1

            zone1 = land.get('zone1', '-')
            zone2 = land.get('zone2', '')
            if zone2 in ['지정되지않음', '', None]:
                zone_display = zone1
            else:
                zone_display = f"{zone1} / {zone2}"

            land_text = (
                f"[필지 {valid_index} 정보]\n"
                f"- 주소: {land.get('legal_dong_name', '')} {land.get('lot_number', '')}\n"
                f"- 용도지역: {zone_display}\n"
                f"- 지목: {land.get('land_category', '')}\n"
                f"- 이용상황: {land.get('land_use', '')}\n"
                f"- 토지면적: {land.get('land_area', '')}㎡\n"
                f"- 지형높이: {land.get('terrain_height', '')}\n"
                f"- 지형형상: {land.get('terrain_shape', '')}\n"
                f"- 도로접면: {land.get('road_access', '')}\n"
            )
            context_parts.append(land_text)

            if isinstance(feasibility, dict):
                feasibility_text = (
                    f"[필지 {valid_index} 개발성적표]\n"
                    f"- 판정: {feasibility.get('status', '?')}\n"
                    f"- 요약: {feasibility.get('summary', '')}\n"
                )
                if feasibility.get("allowed"):
                    feasibility_text += f"- 가능 행위: {', '.join(feasibility['allowed'][:3])}\n"
                if feasibility.get("conditional"):
                    cond_list = [c['activity'] for c in feasibility['conditional'][:3]]
                    feasibility_text += f"- 조건부 행위: {', '.join(cond_list)}\n"
                if feasibility.get("prohibited"):
                    prohib_list = [p['activity'] for p in feasibility['prohibited'][:3]]
                    feasibility_text += f"- 금지 행위: {', '.join(prohib_list)}\n"
                context_parts.append(feasibility_text)

            laws = analysis.get("laws", [])
            if laws:
                law_texts = []
                for law in laws[:5]:
                    law_texts.append(
                        f"  · {law.get('zone_district_name', '')} | "
                        f"{law.get('land_use_activity', '')} | "
                        f"{law.get('permission_category', '')} | "
                        f"{law.get('condition_exception', '')[:50] if law.get('condition_exception') else ''}"
                    )
                context_parts.append(f"[필지 {valid_index} 관련 법규]\n" + "\n".join(law_texts) + "\n")

        return context_parts

    def _build_case3_context(self, analysis_list: List[Dict[str, Any]]) -> List[str]:
        """Case 3 분석 결과 컨텍스트 (주소 없이 용도지역/행위/법조문)"""
        context_parts = []

        for i, analysis in enumerate(analysis_list, 1):
            # CASE3-4: 법조문 기반 검색 결과
            if analysis.get("law_reference"):
                law_ref = analysis["law_reference"]
                laws = analysis.get("laws", [])
                context_parts.append(f"[법조문 검색: {law_ref}]\n")

                if laws:
                    # 용도지역별로 그룹핑
                    zone_groups = {}
                    for law in laws:
                        zd = law.get("zone_district_name", "기타")
                        if zd not in zone_groups:
                            zone_groups[zd] = []
                        zone_groups[zd].append(law)

                    for zd, group_laws in zone_groups.items():
                        law_texts = []
                        for law in group_laws[:3]:
                            condition = law.get('condition_exception', '')
                            condition_short = condition[:80] + "..." if condition and len(condition) > 80 else (condition or "")
                            law_texts.append(
                                f"  · {law.get('land_use_activity', '')} | "
                                f"{law.get('permission_category', '')} | "
                                f"{condition_short}"
                            )
                        context_parts.append(f"[적용 지역: {zd}]\n" + "\n".join(law_texts) + "\n")
                else:
                    context_parts.append(f"해당 법조문({law_ref})에 대한 검색 결과가 없습니다.\n")
                continue

            zone = analysis.get("zone", "")
            if isinstance(zone, list):
                zone = ", ".join(zone)
            act = analysis.get("activities", [])
            feasibility = analysis.get("feasibility", {})
            laws = analysis.get("laws", [])

            context_parts.append(
                f"[검색 {i} 조건]\n"
                f"- 용도지역: {zone}\n"
                f"- 토지이용행위: {', '.join(act) if act else '-'}\n"
            )

            if isinstance(feasibility, dict):
                feasibility_text = (
                    f"[검색 {i} 판정 결과]\n"
                    f"- 판정: {feasibility.get('status', '?')}\n"
                    f"- 요약: {feasibility.get('summary', '')}\n"
                )
                if feasibility.get("allowed"):
                    feasibility_text += f"- 가능 행위: {', '.join(feasibility['allowed'][:5])}\n"
                if feasibility.get("conditional"):
                    cond_list = [c['activity'] if isinstance(c, dict) else str(c) for c in feasibility['conditional'][:5]]
                    feasibility_text += f"- 조건부 행위: {', '.join(cond_list)}\n"
                if feasibility.get("prohibited"):
                    prohib_list = [p['activity'] if isinstance(p, dict) else str(p) for p in feasibility['prohibited'][:3]]
                    feasibility_text += f"- 금지 행위: {', '.join(prohib_list)}\n"
                context_parts.append(feasibility_text)

            if laws:
                law_texts = []
                for law in laws[:8]:
                    condition = law.get('condition_exception', '')
                    condition_short = condition[:50] + "..." if condition and len(condition) > 50 else (condition or "")
                    law_texts.append(
                        f"  · {law.get('zone_district_name', '')} | "
                        f"{law.get('land_use_activity', '')} | "
                        f"{law.get('permission_category', '')} | "
                        f"{condition_short}"
                    )
                context_parts.append(f"[검색 {i} 관련 법규]\n" + "\n".join(law_texts) + "\n")

        return context_parts

    def _build_special_query_context(self, special_data: Dict[str, Any]) -> List[str]:
        """특수 쿼리 결과 컨텍스트 (건폐율/용적률, 법률 비교)"""
        context_parts = []

        # 건폐율/용적률 규제 정보
        if special_data.get("regulations"):
            reg = special_data["regulations"]
            reg_text = f"[건축 규제 정보 - {reg.get('zone_name', '')}]\n"

            if reg.get("description"):
                reg_text += f"- 특성: {reg['description']}\n"

            source = reg.get("coverage_ratio_source", ZONE_REGULATION_SOURCE)
            if reg.get("coverage_ratio"):
                reg_text += f"- 건폐율: {reg['coverage_ratio']}\n"
            if reg.get("floor_area_ratio"):
                reg_text += f"- 용적률: {reg['floor_area_ratio']}\n"
            if reg.get("height_limit") and reg.get("height_limit") != "없음":
                reg_text += f"- 높이제한: {reg['height_limit']}\n"
            reg_text += f"  └ 출처: {source}\n"

            has_extra = any([
                reg.get("floor_limit"), reg.get("total_floor_area_limit"),
                reg.get("front_length_limit"), reg.get("setback_distance")
            ])
            if has_extra:
                reg_text += "\n[추가 규제 (조례/지구단위계획)]\n"
                if reg.get("floor_limit"):
                    reg_text += f"- 층수: {reg['floor_limit']}\n"
                if reg.get("total_floor_area_limit"):
                    reg_text += f"- 연면적: {reg['total_floor_area_limit']}\n"
                if reg.get("front_length_limit"):
                    reg_text += f"- 정면부 길이: {reg['front_length_limit']}\n"
                if reg.get("setback_distance"):
                    reg_text += f"- 건축선 후퇴: {reg['setback_distance']}\n"

            if reg.get("raw_data"):
                reg_text += "\n[관련 조문]\n"
                for item in reg["raw_data"][:3]:
                    condition = item.get("condition_exception", "")
                    if condition and len(condition) > 10:
                        reg_text += f"  · {condition[:120]}...\n"

            context_parts.append(reg_text)

        # 법률/조례 비교
        if special_data.get("law_comparison"):
            lc = special_data["law_comparison"]

            lc_text = f"[건축법 vs 조례 비교 - {lc.get('zone_name', '')}]\n"
            lc_text += f"※ 건축법(전국 공통)과 각 지자체 조례의 차이를 구체적으로 비교합니다.\n\n"

            lc_text += f"[조회 통계]\n"
            lc_text += f"- 건축법 계열: {lc.get('building_law_count', 0)}건\n"
            lc_text += f"- 조례 계열: {lc.get('ordinance_count', 0)}건\n"

            ordinance_regions = lc.get('ordinance_regions', [])
            if ordinance_regions:
                lc_text += f"- 조례 보유 지역: {', '.join(ordinance_regions[:8])}"
                if len(ordinance_regions) > 8:
                    lc_text += f" 외 {len(ordinance_regions) - 8}개 지역"
                lc_text += "\n"
            lc_text += "\n"

            comparisons = lc.get("comparisons", [])
            if comparisons:
                lc_text += "[건축법 ↔ 조례 구체적 비교]\n"
                lc_text += "※ 같은 토지이용행위에 대해 건축법과 각 지역 조례가 어떻게 다른지 보여줍니다.\n\n"

                for comp in comparisons[:8]:
                    activity = comp.get("activity", "")
                    building_law = comp.get("building_law", {})
                    ordinance_list = comp.get("ordinances", [])

                    lc_text += f"▶ 토지이용행위: {activity}\n"

                    if building_law:
                        bl_name = building_law.get("law_name", "건축법")[:40]
                        bl_status = building_law.get("permission_category", "")
                        bl_condition = building_law.get("condition", "") or building_law.get("condition_exception", "")
                        bl_cond_short = bl_condition[:80] + "..." if bl_condition and len(bl_condition) > 80 else (bl_condition or "조건 없음")

                        lc_text += f"  [건축법] {bl_name}\n"
                        lc_text += f"    · 판정: {bl_status}\n"
                        lc_text += f"    · 조건: {bl_cond_short}\n"

                    if ordinance_list:
                        lc_text += f"  [조례 - {len(ordinance_list)}개 지역]\n"
                        for ord_item in ordinance_list[:3]:
                            ord_name = ord_item.get("law_name", "")[:35]
                            ord_status = ord_item.get("permission_category", "")
                            ord_condition = ord_item.get("condition", "") or ord_item.get("condition_exception", "")
                            ord_cond_short = ord_condition[:80] + "..." if ord_condition and len(ord_condition) > 80 else (ord_condition or "조건 없음")

                            lc_text += f"    · {ord_name}\n"
                            lc_text += f"      판정: {ord_status} / 조건: {ord_cond_short}\n"

                    lc_text += "\n"

            sample_ordinances = lc.get("sample_ordinances", [])
            if sample_ordinances:
                lc_text += "[주요 조례 상세 내용]\n"
                lc_text += "※ 실제 적용되는 조례의 구체적 조건입니다.\n\n"

                for ord_item in sample_ordinances[:5]:
                    ord_name = ord_item.get("law_name", "")
                    ord_activity = ord_item.get("activity", "") or ord_item.get("land_use_activity", "")
                    ord_status = ord_item.get("permission_category", "")
                    ord_condition = ord_item.get("condition", "") or ord_item.get("condition_exception", "")
                    ord_cond_text = ord_condition[:120] + "..." if ord_condition and len(ord_condition) > 120 else (ord_condition or "")

                    lc_text += f"  ▸ {ord_name}\n"
                    lc_text += f"    행위: {ord_activity}\n"
                    lc_text += f"    판정: {ord_status}\n"
                    if ord_cond_text:
                        lc_text += f"    조건: {ord_cond_text}\n"
                    lc_text += "\n"

            context_parts.append(lc_text)

        return context_parts

    def get_law_info(self, region_codes: List[str]) -> List[Dict[str, Any]]:
        """Law 테이블에서 구분코드로 법률 정보 조회"""
        if self.db_conn is None:
            logger.warning("PostgreSQL 연결 안됨")
            return []

        if not region_codes:
            return []

        try:
            query = """
            SELECT
                region_code, zone_district_name, law_name,
                land_use_activity, permission_category, condition_exception
            FROM law
            WHERE region_code = ANY(%s)
            """

            with self._get_cursor() as cursor:
                cursor.execute(query, (region_codes,))
                results = cursor.fetchall()

                law_infos = [dict(row) for row in results]
                logger.info(f"법률 정보 {len(law_infos)}개 조회 완료")
                return law_infos

        except Exception as e:
            logger.error(f"법률 정보 조회 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return []

    def ask(self, email: str, question: str) -> Dict[str, str]:
        """사용자 질문에 RAG 기반으로 답변 (케이스 분기 적용)"""
        self.load_components()

        try:
            logger.info(f"질문 받음: {email} - {question}")

            # 질문 정규화 (오타/띄어쓰기 보정) — _build_context 등에서 사용
            question_normalized = self.normalize_query(question)

            # ========================================
            # 1단계: LLM 기반 구조화 추출 (regex fallback 내장)
            # ========================================
            extraction = self.extract_with_llm(question)
            address_info = extraction["address_info"]
            zone_names = extraction["zone_names"]
            activities = extraction["activities"]
            region_codes = extraction["region_codes"]
            special_queries = extraction["special_queries"]
            query_fields = extraction["query_fields"]
            law_reference = extraction["law_reference"]
            intent = extraction["intent"]
            is_comparison = extraction.get("is_comparison", False)

            logger.info(f"[1단계] 분석 - 주소: {address_info}, 지역지구: {zone_names}, 행위: {activities}, 특수쿼리: {special_queries}, query_fields: {query_fields}, law_ref: {law_reference}")
            logger.info(f"[2단계] 의도 분류: {intent['case']} - {intent['sub_case']}")

            # ========================================
            # 3단계: 데이터 검색 + 4단계: 법규 검토
            # ========================================
            case_result = None

            if intent["case"] == "CASE3":
                case_result = self.process_case3(zone_names, activities, law_reference=law_reference, is_comparison=is_comparison)
            elif intent["case"] == "CASE2":
                case_result = self.process_case2(address_info, zone_names, activities)
            else:
                case_result = self.process_case1(address_info, activities)

            logger.info(f"[3-4단계] {case_result['case']}-{case_result['sub_case']}: {case_result['message']}")

            # ========================================
            # 특수 쿼리 처리 (건폐율/용적률, 법률 비교 등)
            # ========================================
            special_data = {}
            if special_queries:
                target_zone = None
                if case_result.get("lands") and len(case_result["lands"]) > 0:
                    target_zone = case_result["lands"][0].get("zone1")
                elif zone_names:
                    target_zone = zone_names[0]

                if target_zone:
                    if "coverage_ratio" in special_queries or "floor_area_ratio" in special_queries:
                        regulations = self.get_zone_regulations(target_zone)
                        if regulations:
                            special_data["regulations"] = regulations
                            logger.info(f"[특수쿼리] 규제 정보 조회: {target_zone}")

                    if "law_comparison" in special_queries:
                        comparison = self.compare_laws(target_zone)
                        if comparison:
                            special_data["law_comparison"] = comparison
                            logger.info(f"[특수쿼리] 법률 비교 조회: {target_zone}")

            # ========================================
            # 컨텍스트 구성 (분리된 메서드 호출)
            # ========================================
            context = self._build_context(case_result, special_data, email, question_normalized, query_fields=query_fields)

            logger.info(f"[컨텍스트 길이] {len(context)} 글자")

            # [V2 변경] 임베딩 캐시 통계 로깅
            cache_stats = self._embedding_cache.stats
            logger.info(f"[V2 캐시] {cache_stats}")

            # ========================================
            # 5단계: LLM 리포트 생성
            # ========================================

            system_prompt = (
                "You are a Korean land/building regulation expert. "
                "You help users understand if specific business activities are permitted on their land.\n\n"

                "## TASK\n"
                "Analyze the user's question about land development and provide a clear, actionable answer "
                "based ONLY on the [ANALYSIS DATA] provided below.\n\n"

                "## THINKING PROCESS (Follow these steps internally)\n"
                "1. Identify: What land/address is the user asking about?\n"
                "2. Classify question type:\n"
                "   a) 필지 물리정보 (면적, 지형, 도로접면 등) → [필지 N 정보] 섹션에서 직접 답변\n"
                "   b) 건축/개발 가능 여부 → [필지 N 개발성적표] + [관련 법규] 참조\n"
                "   c) 규제 정보 (건폐율, 용적률) → [건축 규제 정보] 참조\n"
                "   d) 법률 비교 → [건축법 vs 조례 비교] 참조\n"
                "   e) 법조문 검색 → [법조문 검색] + [적용 지역] 섹션에서 해당 법조문 내용 설명\n"
                "   f) 용도지역 비교 → [용도지역 비교 데이터] 비교표를 활용하여 차이점 설명\n"
                "   g) 용도지역/행위 검색 → [검색 N 조건] + [검색 N 관련 법규] 섹션에서 답변\n"
                "3. Find the answer in [ANALYSIS DATA] - it is ALWAYS there if the section exists\n"
                "4. Explain clearly in Korean\n\n"

                "## STRICT RULES\n"
                "1. Use ONLY information from [ANALYSIS DATA]. NEVER make up laws or conditions.\n"
                "2. IMPORTANT: If ANY relevant data exists in [ANALYSIS DATA], you MUST use it to answer.\n"
                "   - '건축법' includes: 건축법, 건축법시행령, 건축법시행규칙\n"
                "   - '조례' includes: 도시계획조례, 건축조례, 지구단위계획\n"
                "   - Match partial law names (e.g., '건축법시행령 별표1' is part of 건축법)\n"
                "3. CRITICAL: Say '해당 정보가 제공되지 않았습니다' ONLY when [ANALYSIS DATA] contains NO data sections at all.\n"
                "   Valid data sections include: [필지 N 정보], [법조문 검색], [적용 지역], [검색 N 조건], [검색 N 관련 법규], [용도지역 비교 데이터].\n"
                "   If ANY of these sections exist, the answer IS there - read it carefully and respond.\n"
                "   For 면적/지형/도로접면 questions: the answer is in [필지 N 정보] fields directly.\n"
                "4. CRITICAL: DO NOT mention other facilities or buildings that are not asked in the question.\n"
                "   ❌ Bad: '철도시설은 불가능합니다. 고등학교, 대학, 유치원은 조건부로 가능합니다.'\n"
                "   ✅ Good: '철도시설은 자연녹지지역에서 건축할 수 없습니다.'\n"
                "   Only answer what was specifically asked. Do not add examples of other allowed/forbidden facilities.\n"
                "5. Always cite the exact law name when mentioning regulations.\n"
                "6. Keep answer concise (800-1200 characters in Korean, 약 800~1200자).\n"
                "7. For law comparison questions: Look for [법률/조례 비교] section and explain the differences.\n\n"

                "## OUTPUT FORMAT (Must respond in Korean)\n\n"
                "IMPORTANT: Write in a friendly, conversational tone like a helpful expert consultant.\n"
                "- Avoid overly formal markdown headers (##, ###)\n"
                "- Use simple formatting: bold for key points, bullet points sparingly\n"
                "- Start with a direct answer, then explain\n"
                "- Be concise but warm\n\n"
                "### Style Examples:\n"
                "❌ Bad: '## 1. 결론\\n해당 필지에서...'\n"
                "✅ Good: '네, 카페 운영 가능합니다! 다만 몇 가지 조건이 있어요.'\n\n"
                "❌ Bad: '### 3. 관련 법규\\n- 건축법시행령 별표1...'\n"
                "✅ Good: '관련 법규를 보면, 건축법시행령 별표1에서 휴게음식점을 허용하고 있어요.'\n\n"
                "### Answer Structure (flexible, not rigid):\n"
                "1. 핵심 답변 - 질문에 대한 직접적인 대답 (1-2문장)\n"
                "2. 상세 설명 - 근거 법률, 조건, 제한사항 등\n"
                "3. 참고/주의사항 - 추가 확인 필요사항 (선택)\n\n"

                "## EXAMPLE ANSWERS\n\n"
                "### Example 1 (건축 가능 여부)\n"
                "```\n"
                "네, 해당 필지에서 카페 운영이 가능합니다! 🏠\n\n"
                "필지 정보\n"
                "서울시 종로구 청운동 1-2 (제1종일반주거지역, 지목: 대)\n\n"
                "관련 법규\n"
                "건축법시행령 별표1 제3호나목에 따라 휴게음식점이 허용돼요.\n"
                "다만 4층 이하 건물에서만 가능하고, 조례에 따라 추가 제한이 있을 수 있어요.\n\n"
                "💡 실제 창업 전에 관할 구청 건축과에서 사전상담 받아보시는 걸 추천드려요!\n"
                "```\n\n"
                "### Example 2 (필지 물리정보 - 면적, 지형, 도로접면)\n"
                "```\n"
                "종로구 청운동 1-2의 지형 정보를 알려드릴게요.\n\n"
                "- 지형높이: 급경사\n"
                "- 지형형상: 부정형\n"
                "- 도로접면: 맹지 (도로에 접하지 않음)\n"
                "- 토지면적: 20.7㎡\n"
                "- 용도지역: 제1종일반주거지역\n\n"
                "맹지이기 때문에 건축 시 도로개설이나 통행권 확보가 필요할 수 있어요. "
                "관할 구청에서 확인해보시는 걸 추천드려요!\n"
                "```\n\n"
                "### Example 3 (법률 비교)\n"
                "```\n"
                "건축법과 도시계획조례의 주요 차이점을 설명드릴게요.\n\n"
                "건축법 (국가법)\n"
                "전국에 공통 적용되는 기본 규정이에요. 건축물 용도별 허용 여부의 큰 틀을 정합니다.\n\n"
                "도시계획조례 (지자체법)\n"
                "각 지자체가 지역 특성에 맞게 추가로 정한 규정이에요. 건축법보다 더 엄격하거나 세부적인 조건을 붙이는 경우가 많아요.\n\n"
                "예를 들어, 건축법에서 '가능'이어도 조례에서 면적이나 층수 제한을 둘 수 있어요.\n"
                "```\n\n"
                "### Example 4 (불가능한 건축물 - 다른 시설 언급 금지)\n"
                "질문: 자연녹지지역에서 철도시설을 지어도 돼?\n"
                "```\n"
                "❌ Bad: 자연녹지지역에서는 철도시설을 지을 수 없습니다. 다만 고등학교, 대학, 유치원 등 교육시설은 조건부로 가능해요.\n"
                "✅ Good: 자연녹지지역에서는 철도시설을 지을 수 없어요. 관련 법규에 따라 대규모 인프라 시설은 허용되지 않습니다.\n"
                "```\n\n"

                f"## [ANALYSIS DATA]\n{context}"
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ]

            response = self.openai_client.chat.completions.create(
                model=self.config.OPENAI_MODEL,
                messages=messages,
                temperature=0.3
            )

            answer = response.choices[0].message.content
            summary_title = question[:30] + "..." if len(question) > 30 else question

            logger.info(f"[5단계] 답변 생성 완료: {summary_title}")
            
            # ========================================
            # [추가 기능] 건축물 용도 설명 추가
            # ========================================
            facility_defs = self._get_facility_definitions(question, activities)
            
            if facility_defs:
                answer += "\n\n" + "─" * 40 + "\n"
                answer += "\n📖 건축물 용도 설명\n\n"
                
                for i, facility in enumerate(facility_defs, 1):
                    answer += f"{i}. {facility['facility_name']} ({facility['category_name']})\n"
                    
                    # description이 너무 길면 요약 (첫 400자까지)
                    desc = facility.get('description', '설명 없음')
                    if desc and len(desc) > 400:
                        desc = desc[:400] + "..."
                    
                    answer += f"{desc}\n"
                    
                    # URL이 있으면 추가 (Markdown 링크 형식)
                    if facility.get('url'):
                        answer += f"🔗 [상세정보]({facility['url']})\n"
                    
                    answer += "\n"
                
                logger.info(f"[건축물 용도 설명] {len(facility_defs)}개 추가됨")

            return {
                "summaryTitle": summary_title,
                "answer": answer,
                "_debug_context": context,
                "_extraction": extraction
            }

        except Exception as e:
            logger.error(f"챗봇 답변 생성 실패: {e}")
            import traceback
            traceback.print_exc()
            return {
                "summaryTitle": "오류 발생",
                "answer": f"답변 생성 중 오류가 발생했습니다: {str(e)}"
            }

    def is_loaded(self) -> bool:
        """컴포넌트 로드 여부 확인"""
        return self.openai_client is not None


# 싱글톤 인스턴스
chatbot_service = ChatbotService()


# ==========================================
# 필요한 의존성 설치
# ==========================================
# pip install sentence-transformers
# (이미 설치된 패키지: psycopg2-binary, openai, pgvector, pydantic-settings)
