"""
챗봇 서비스
RAG 기반 평면도 관련 질의응답 + PostgreSQL 이전 대화 내역 활용
"""

import logging
import os
import re
from typing import Optional, Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor

from openai import OpenAI

from CV.rag_system.config import RAGConfig
from CV.rag_system.embeddings import EmbeddingManager
from services.pgvector_service import pgvector_service

logger = logging.getLogger("ChatbotService")


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
    """RAG 기반 챗봇 서비스 + PostgreSQL 대화 내역 활용"""
    
    # PostgreSQL 연결 정보 (application.properties와 동일)
    DB_CONFIG = {
        "host": "localhost",
        "port": 5432,
        "database": "arae",
        "user": "postgres",
        "password": "1234"
    }
    
    def __init__(self):
        self.config: Optional[RAGConfig] = None
        self.embedding_manager: Optional[EmbeddingManager] = None
        self.openai_client: Optional[OpenAI] = None
        self.db_conn = None

    def _get_cursor(self):
        """
        DB 커서 반환 (연결 끊김 시 자동 재연결)

        Returns:
            RealDictCursor: DB 커서

        Raises:
            Exception: 재연결 실패 시
        """
        try:
            # 연결 상태 확인 및 재연결
            if self.db_conn is None or self.db_conn.closed:
                logger.warning("DB 연결 끊김 감지, 재연결 시도...")
                self.db_conn = psycopg2.connect(**self.DB_CONFIG)
                self.db_conn.autocommit = True
                logger.info("DB 재연결 성공 (autocommit=True)")

            # 연결 유효성 테스트
            try:
                with self.db_conn.cursor() as test_cursor:
                    test_cursor.execute("SELECT 1")
            except Exception:
                logger.warning("DB 연결 유효하지 않음, 재연결 시도...")
                self.db_conn = psycopg2.connect(**self.DB_CONFIG)
                self.db_conn.autocommit = True
                logger.info("DB 재연결 성공 (autocommit=True)")

            return self.db_conn.cursor(cursor_factory=RealDictCursor)

        except Exception as e:
            logger.error(f"DB 연결/재연결 실패: {e}")
            raise

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
            
            logger.info("챗봇 컴포넌트 로딩 완료!")
        except Exception as e:
            logger.error(f"챗봇 컴포넌트 로딩 실패: {e}")
            raise
    
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

        # 3. 띄어쓰기 정규화 (용도지역)
        text = re.sub(r'제\s*(\d)\s*종\s*일반', r'제\1종일반', text)
        text = re.sub(r'제\s*(\d)\s*종\s*전용', r'제\1종전용', text)
        text = re.sub(r'주\s*거\s*지\s*역', '주거지역', text)
        text = re.sub(r'상\s*업\s*지\s*역', '상업지역', text)
        text = re.sub(r'공\s*업\s*지\s*역', '공업지역', text)

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
        """질문에서 주소 정보 추출"""
        result = {"legal_dong_name": "", "lot_number": "", "region_code": ""}

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
        # "종로구", "강남구", "수원시", "성남시" 등
        sigungu_pattern = r'(?:서울특별시|서울시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시|경기도|강원도|충청북도|충청남도|전라북도|전라남도|경상북도|경상남도|제주특별자치도)?\s*([\w]{2,4}(?:시|군|구))'
        sigungu_match = re.search(sigungu_pattern, text)
        if sigungu_match:
            sigungu = sigungu_match.group(1)
            # 광역시명과 중복 방지
            if sigungu not in ['서울시', '부산시', '대구시', '인천시', '광주시', '대전시', '울산시', '세종시']:
                # 이미 추가된 것과 중복되지 않으면 추가
                if sigungu not in dong_parts:
                    dong_parts.append(sigungu)

        # 3. 읍면동 추출 (동 뒤에 조사/숫자/공백이 올 수 있음)
        # "가"는 숫자+가 형태만 매칭 (종로1가, 을지로2가 등) - "뭐가" 같은 오탐 방지
        dong_match = re.search(r'([\w]{1,10}(?:동|읍|면|리))(?:\s|\d|에|을|의|로|은|는|이|가|$)', text)
        if dong_match:
            dong = dong_match.group(1)
            # 이미 추가된 것과 중복되지 않으면 추가
            if dong not in dong_parts:
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
        # 1순위: 명시적 지번 표현 (1-2, 123번지, 지번 123)
        lot_match = re.search(r'(\d+-\d+)(?:번지)?(?:\s|에|$)', text)  # 본번-부번
        if not lot_match:
            lot_match = re.search(r'(\d+)번지', text)  # N번지
        if not lot_match:
            lot_match = re.search(r'지번\s*(\d+)', text)  # 지번 N
        # 2순위: 동/읍/면/리 바로 뒤의 숫자 (주소 문맥)
        if not lot_match:
            lot_match = re.search(r'(?:동|읍|면|리|가)\s+(\d+)(?:\s|에|$)', text)
        # 층수/퍼센트/연면적 숫자는 제외 (3층, 200%, 1500제곱미터 등)
        if lot_match:
            lot_num = lot_match.group(1).replace('번지', '')
            # 층수/퍼센트 문맥 체크
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

        return result
    
    def extract_zone_district_name(self, text: str) -> List[str]:
        """질문에서 지역지구명 추출 (정확한 용도지역명 우선, 사전 매핑은 보조)"""
        # 우선순위별 분리 (순서 유지를 위해)
        exact_matches = []   # 1순위: ZONE_REGULATIONS exact match
        regex_matches = []   # 2순위: 정규식 매칭

        # 1. 먼저 ZONE_REGULATIONS에서 정확한 용도지역명 매칭 (가장 우선)
        for zone_name in ZONE_REGULATIONS.keys():
            if zone_name in text:
                exact_matches.append(zone_name)

        # 2. 정규식으로 직접 추출 (더 다양한 패턴 대응)
        zone_patterns = [
            r'(제\d종[가-힣]{2,10}지역)',      # 제1종일반주거지역
            r'([가-힣]{2,6}경관지구)',          # 자연경관지구
            r'([가-힣]{2,6}미관지구)',          # 일반미관지구
            r'([가-힣]{2,4}녹지지역)',          # 자연녹지지역
            r'([가-힣]{2,4}주거지역)',          # 준주거지역
            r'([가-힣]{2,4}상업지역)',          # 일반상업지역
            r'([가-힣]{2,4}공업지역)',          # 준공업지역
            r'([가-힣]{2,6}보호지구)',          # 문화자원보호지구
            r'([가-힣]{2,6}관리지역)',          # 계획관리지역
        ]

        for pattern in zone_patterns:
            matches = re.findall(pattern, text)
            regex_matches.extend(matches)

        # 정확한 매칭이 있으면 우선 반환 (regex 오탐 방지)
        if exact_matches:
            return list(dict.fromkeys(exact_matches))

        # exact 매칭 없을 때만 regex 결과 사용 (부분 문자열 오탐 제거)
        if regex_matches:
            # 다른 매칭의 부분 문자열인 것 제거 (예: "종일반주거지역" ⊂ "제2종일반주거지역")
            filtered = []
            for z in regex_matches:
                is_substring = any(z != other and z in other for other in regex_matches)
                if not is_substring:
                    filtered.append(z)
            return list(dict.fromkeys(filtered))

        # 3. 정확한 매칭이 없을 때만 사전 매핑 사용 (부분 키워드 매칭)
        dict_matches = []  # 사전 매핑 결과

        # 매칭된 모든 키워드 수집
        matching_keywords = [kw for kw in ZONE_DISTRICT_DICTIONARY.keys() if kw in text]

        # 더 긴 키워드에 포함된 짧은 키워드 제외
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

        # 순서 유지하며 중복 제거
        return list(dict.fromkeys(dict_matches))
    
    def extract_land_use_activity(self, text: str) -> List[str]:
        """질문에서 토지이용행위 추출 (사전 매핑 적용)"""
        activities = []
        text_lower = text.lower()

        # 사전에서 매핑 검색
        for keyword, db_values in LAND_USE_DICTIONARY.items():
            if keyword in text or keyword in text_lower:
                if isinstance(db_values, list):
                    activities.extend(db_values)
                else:
                    activities.append(db_values)

        # 층수 관련 추출
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

    def get_zone_regulations(self, zone_name: str) -> Dict[str, Any]:
        """
        특정 용도지역의 건폐율/용적률 등 규제 정보 조회
        1. 먼저 정적 사전(ZONE_REGULATIONS)에서 법정 기준값 조회
        2. DB에서 추가 조건/예외사항 검색
        """
        # 결과 구조
        regulations = {
            "zone_name": zone_name,
            "coverage_ratio": None,           # 건폐율
            "coverage_ratio_source": ZONE_REGULATION_SOURCE,
            "floor_area_ratio": None,         # 용적률
            "floor_area_ratio_source": ZONE_REGULATION_SOURCE,
            "height_limit": None,             # 높이제한
            "floor_limit": None,              # 층수 제한
            "total_floor_area_limit": None,   # 연면적 제한
            "front_length_limit": None,       # 정면부 길이 제한
            "setback_distance": None,         # 건축선 후퇴
            "description": None,
            "raw_data": []
        }

        # 1. 정적 사전에서 기본값 조회
        static_reg = None
        if zone_name in ZONE_REGULATIONS:
            static_reg = ZONE_REGULATIONS[zone_name]
        else:
            # 부분 매칭 시도
            for zone_key, reg in ZONE_REGULATIONS.items():
                if zone_key in zone_name or zone_name in zone_key:
                    static_reg = reg
                    break

        # 간소화된 사전 구조에서 값 추출
        if static_reg:
            regulations["coverage_ratio"] = static_reg.get("건폐율")
            regulations["floor_area_ratio"] = static_reg.get("용적률")
            regulations["height_limit"] = static_reg.get("높이")
            regulations["description"] = static_reg.get("설명")

        # 2. DB에서 추가 정보 조회 (조건/예외사항 - 절대값 제한 포함)
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

                    # DB에서 추가 정보 추출
                    for r in results:
                        condition = r.get("condition_exception", "") or ""

                        # === 비율 기반 규제 ===
                        # 건폐율 추출 (정적 사전에 없는 경우만)
                        if not regulations["coverage_ratio"]:
                            coverage_match = re.search(r'건폐율\s*(\d+)\s*(%|퍼센트)', condition)
                            if coverage_match:
                                regulations["coverage_ratio"] = f"{coverage_match.group(1)}%"
                                regulations["source"] = "조례"

                        # 용적률 추출
                        if not regulations["floor_area_ratio"]:
                            far_match = re.search(r'용적률\s*(\d+)\s*(%|퍼센트)', condition)
                            if far_match:
                                regulations["floor_area_ratio"] = f"{far_match.group(1)}%"
                                regulations["source"] = "조례"

                        # === 절대값 기반 규제 (키워드 근처에서만 매칭하여 오탐 방지) ===
                        # 높이 제한 (예: "높이 20미터이하", "높이가 12m 이하")
                        # "높이" 키워드 근처에서만 매칭 (정면부 길이 등 오탐 방지)
                        if not regulations["height_limit"]:
                            height_match = re.search(r'높이\s*(가|는|를|이)?\s*(\d+)\s*(m|미터)\s*(이하|까지|미만)?', condition)
                            if height_match:
                                suffix = height_match.group(4) or "이하"
                                regulations["height_limit"] = f"{height_match.group(2)}m {suffix}"

                        # 층수 제한 (예: "5층이하", "3층 이하")
                        if not regulations["floor_limit"]:
                            floor_match = re.search(r'(\d+)층\s*(이하|까지|미만)?', condition)
                            if floor_match:
                                suffix = floor_match.group(2) or "이하"
                                regulations["floor_limit"] = f"{floor_match.group(1)}층 {suffix}"

                        # 연면적 제한 (예: "연면적 1,500제곱미터이하", "연면적 3천제곱미터")
                        if not regulations["total_floor_area_limit"]:
                            # 숫자+제곱미터 패턴
                            area_match = re.search(r'연면적\s*([\d,]+)\s*제곱미터\s*(이하|까지|미만)?', condition)
                            if area_match:
                                area_val = area_match.group(1).replace(',', '')
                                suffix = area_match.group(2) or "이하"
                                regulations["total_floor_area_limit"] = f"{int(area_val):,}㎡ {suffix}"
                            else:
                                # "3천제곱미터" 같은 패턴
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

                        # 정면부 길이 제한 (예: "정면부길이가 30미터미만")
                        if not regulations["front_length_limit"]:
                            front_match = re.search(r'정면부\s*길이\s*(가|가\s*)?\s*(\d+)\s*(m|미터)\s*(미만|이하)?', condition)
                            if front_match:
                                suffix = front_match.group(4) or "미만"
                                regulations["front_length_limit"] = f"{front_match.group(2)}m {suffix}"

                        # 건축선 후퇴 (예: "건축선으로부터 3미터이상을후퇴")
                        if not regulations["setback_distance"]:
                            setback_match = re.search(r'건축선.*?(\d+)\s*(m|미터)\s*(이상)?.*?후퇴', condition)
                            if setback_match:
                                regulations["setback_distance"] = f"{setback_match.group(1)}m 이상 후퇴"

            except Exception as e:
                import traceback
                print(f"[ERROR] DB 규제 정보 조회 실패: {e}")
                traceback.print_exc()
                logger.error(f"DB 규제 정보 조회 실패: {e}")
                if self.db_conn:
                    self.db_conn.rollback()

        return regulations

    def compare_laws(self, zone_name: str) -> Dict[str, Any]:
        """
        법률과 조례 비교 (건축법 vs 지자체 조례 명확히 구분)
        """
        if self.db_conn is None:
            return {}

        try:
            query = """
            SELECT
                zone_district_name, law_name,
                land_use_activity, permission_status, condition_exception
            FROM law
            WHERE zone_district_name LIKE %s
            ORDER BY land_use_activity, law_name
            LIMIT 200
            """

            with self._get_cursor() as cursor:
                cursor.execute(query, (f"%{zone_name}%",))
                results = [dict(row) for row in cursor.fetchall()]

                # 법률 유형 분류 함수
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

                # 건축법 vs 조례 분리
                building_laws = []  # 건축법 계열
                ordinances = []     # 조례 계열
                other_laws = []     # 기타

                for r in results:
                    law_name = r.get("law_name", "")
                    law_type = classify_law_type(law_name)

                    item = {
                        "law_name": law_name,
                        "law_type": law_type,
                        "activity": r.get("land_use_activity", ""),
                        "permission_status": r.get("permission_status", ""),
                        "condition": r.get("condition_exception", "") or "조건 없음"
                    }

                    if law_type == "건축법":
                        building_laws.append(item)
                    elif law_type == "조례":
                        ordinances.append(item)
                    else:
                        other_laws.append(item)

                # 조례를 지역별로 그룹화
                ordinance_by_region = {}
                for o in ordinances:
                    law_name = o["law_name"]
                    # 지역명 추출 (예: "김포시도시계획조례" → "김포시")
                    region = law_name.split("조례")[0].replace("도시계획", "").replace("군계획", "")
                    if not region:
                        region = law_name[:4]  # 앞 4글자

                    if region not in ordinance_by_region:
                        ordinance_by_region[region] = []
                    ordinance_by_region[region].append(o)

                # 토지이용행위별 비교 (건축법 vs 조례)
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

                # 비교 가치 있는 항목 (건축법과 조례 둘 다 있는 것)
                valuable_comparisons = []
                for activity, laws in activity_comparison.items():
                    if laws["건축법"] and laws["조례"]:  # 둘 다 있는 경우
                        valuable_comparisons.append({
                            "activity": activity,
                            "building_law": laws["건축법"][0],  # 대표 1개
                            "ordinances": laws["조례"][:5],  # 조례 최대 5개
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
                    "sample_ordinances": ordinances[:10],  # 조례 샘플 10개
                }

        except Exception as e:
            logger.error(f"법률 비교 조회 실패: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            return {}
    
    def search_by_address(self, address_info: Dict[str, str], limit: int = 20) -> List[Dict[str, Any]]:
        """
        주소 정보로 land_char 테이블에서 필지 검색

        Args:
            address_info: 주소 정보 (legal_dong_name, lot_number, region_code)
            limit: 최대 결과 수 (기본 20, 케이스 분석용은 6 권장)

        Returns:
            필지 정보 리스트
        """
        try:
            conditions = []
            params = []

            # 법정동명 검색 (각 단어별 AND 조건으로 유연하게)
            # "서울 종로구 청운동" → "서울특별시 종로구 청운동" 매칭 가능하도록
            if address_info.get("legal_dong_name"):
                dong_parts = address_info["legal_dong_name"].split()
                for part in dong_parts:
                    conditions.append("legal_dong_name LIKE %s")
                    params.append(f"%{part}%")

            # 지번 검색
            if address_info.get("lot_number"):
                lot_num = address_info['lot_number']
                if '-' in lot_num:
                    # 정확한 지번 (1-2)
                    conditions.append("lot_number = %s")
                    params.append(lot_num)
                else:
                    # 본번만 있는 경우 (1 → 1, 1-1, 1-2 등)
                    conditions.append("(lot_number = %s OR lot_number LIKE %s)")
                    params.append(lot_num)
                    params.append(f"{lot_num}-%")

            # 지역코드 검색
            if address_info.get("region_code"):
                conditions.append("region_code LIKE %s")
                params.append(f"{address_info['region_code']}%")

            if not conditions:
                return []

            query = f"""
            SELECT DISTINCT
                legal_dong_name, lot_number, region_code,
                zone1, zone2, land_category, land_use
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
    
    def search_by_zone_district(self, zone_names: List[str], region_filter: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """지역지구명으로 law 테이블에서 검색"""
        if self.db_conn is None or not zone_names:
            return []

        try:
            # 파라미터 바인딩으로 SQL Injection 방지
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
                land_use_activity, permission_status, condition_exception
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
            # 파라미터 바인딩으로 SQL Injection 방지
            params = []
            conditions = []

            # 토지이용행위 조건
            activity_conditions = []
            for activity in activities:
                activity_conditions.append("land_use_activity LIKE %s")
                params.append(f"%{activity}%")
            conditions.append(f"({' OR '.join(activity_conditions)})")

            # 용도지역 조건
            if zone_name:
                conditions.append("zone_district_name LIKE %s")
                params.append(f"%{zone_name}%")

            # 지역코드 조건
            if region_filter and region_filter.get("region_code"):
                conditions.append("region_code LIKE %s")
                params.append(f"{region_filter['region_code']}%")

            query = f"""
            SELECT DISTINCT
                region_code, zone_district_name, law_name,
                land_use_activity, permission_status, condition_exception
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

    def classify_intent(self, address_info: Dict[str, str], zone_names: List[str], activities: List[str]) -> Dict[str, Any]:
        """
        질문 의도 분류 (Case1/Case2/Case3 판단)

        Returns:
            {
                "case": "CASE1" or "CASE2" or "CASE3",
                "sub_case": "1-1", "1-2", "1-3", "2-1", "2-2", "2-3", "3-1", "3-2",
                "description": str
            }
        """
        has_address = bool(address_info.get("legal_dong_name"))
        has_lot_number = bool(address_info.get("lot_number"))
        has_zone = bool(zone_names)
        has_activity = bool(activities)

        # Case 2: 주소(법정동) + 용도지역이 둘 다 있을 때만 CASE2
        # (주소 오탐 상태에서 zone만 있으면 CASE3로 가는 게 더 안전)
        if has_address and has_zone:
            return {
                "case": "CASE2",
                "sub_case": "2-1",
                "description": "주소와 용도지역이 함께 입력됨"
            }

        # Case 3: 주소 없이 용도지역/토지이용행위만 질문
        if not has_address and (has_zone or has_activity):
            if has_zone and has_activity:
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

        # Case 1: 주소만
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
        """
        단일 필지와 법규 1:1 매칭

        Args:
            land_info: 필지 정보 (zone1, zone2 등 포함)
            activities: 질문에서 추출한 토지이용행위 목록

        Returns:
            {
                "land": 필지정보,
                "laws": 매칭된 법규 목록,
                "feasibility": 개발가능성 판정
            }
        """
        if self.db_conn is None:
            return {"land": land_info, "laws": [], "feasibility": "판정불가"}

        try:
            # 필지의 용도지역으로 법규 검색
            zones = []
            if land_info.get("zone1"):
                zones.append(land_info["zone1"])
            if land_info.get("zone2") and land_info.get("zone2") != "지정되지않음":
                zones.append(land_info["zone2"])

            if not zones:
                return {"land": land_info, "laws": [], "feasibility": "용도지역 정보 없음"}

            # 파라미터 바인딩으로 SQL Injection 방지
            params = []
            conditions = []

            # 용도지역 조건
            zone_conditions = []
            for zone in zones:
                zone_conditions.append("zone_district_name LIKE %s")
                params.append(f"%{zone}%")
            conditions.append(f"({' OR '.join(zone_conditions)})")

            # 토지이용행위 조건
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
                land_use_activity, permission_status, condition_exception
            FROM law
            WHERE {where_clause}
            LIMIT 20
            """

            with self._get_cursor() as cursor:
                cursor.execute(query, params)
                laws = [dict(row) for row in cursor.fetchall()]

            # 개발가능성 판정
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
        """
        법규 기반 개발가능성 분석 (개발성적표)

        Returns:
            {
                "status": "가능" | "조건부가능" | "불가" | "정보부족",
                "allowed": [가능한 행위 목록],
                "conditional": [조건부 행위 목록],
                "prohibited": [불가능한 행위 목록],
                "summary": 요약 문자열
            }
        """
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
            permission = law.get("permission_status", "")
            condition = law.get("condition_exception", "")

            # 허가 상태 판정 (불가/금지를 먼저 체크 - "불가능"에 "가능" 포함 문제 방지)
            permission_lower = permission.lower() if permission else ""

            # 1순위: 불가/금지/불허 (먼저 체크해야 "불가능" 오분류 방지)
            if "불가" in permission_lower or "금지" in permission_lower or "불허" in permission_lower:
                prohibited.append({
                    "activity": activity,
                    "reason": condition if condition else "법규상 금지"
                })
            # 2순위: 가능/허용
            elif "가능" in permission_lower or "허용" in permission_lower:
                if condition and len(condition) > 5:
                    conditional.append({
                        "activity": activity,
                        "condition": condition
                    })
                else:
                    allowed.append(activity)
            # 3순위: 조건만 있는 경우
            elif condition and len(condition) > 5:
                conditional.append({
                    "activity": activity,
                    "condition": condition
                })

        # 최종 판정
        if prohibited and not allowed and not conditional:
            status = "불가"
            summary = f"해당 행위는 법규상 금지되어 있습니다. (금지 항목: {len(prohibited)}건)"
        elif allowed and not prohibited:
            status = "가능"
            summary = f"해당 행위는 가능합니다. (허용 항목: {len(allowed)}건)"
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
        """
        사용자 입력 용도지역과 실제 데이터 일치 여부 확인

        Returns:
            {
                "match_type": "일치" | "불일치" | "부분일치",
                "land_zones": 실제 필지의 용도지역,
                "user_zones": 사용자 입력 용도지역,
                "message": 설명
            }
        """
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

        # 일치 여부 확인
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

    def process_case1(self, address_info: Dict[str, str], activities: List[str]) -> Dict[str, Any]:
        """
        Case 1 처리: 주소만 입력된 경우
        """
        # 필지 검색 (케이스 분석용 limit=6)
        lands = self.search_by_address(address_info, limit=6)

        if not lands:
            return {
                "case": "CASE1",
                "sub_case": "1-0",
                "message": "해당 주소의 필지를 찾을 수 없습니다.",
                "lands": [],
                "analysis": []
            }

        # Sub-case 결정
        if len(lands) == 1:
            sub_case = "1-1"
            message = "지번 정확히 매칭됨 (1필지)"
        else:
            sub_case = "1-2"
            message = f"복수 필지 검색됨 ({len(lands)}필지)"

        # 각 필지별 분석
        analysis_results = []
        for land in lands:
            result = self.match_land_to_law(land, activities)
            analysis_results.append(result)

        # 비교 분석 (1-2인 경우)
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
        """
        # 필지 검색 (케이스 분석용 limit=6)
        lands = self.search_by_address(address_info, limit=6)

        if not lands:
            # 필지 못 찾으면 용도지역으로만 검색
            return {
                "case": "CASE2",
                "sub_case": "2-0",
                "message": "해당 주소의 필지를 찾을 수 없어 용도지역 기준으로만 검색합니다.",
                "zone_match": None,
                "analysis": self.search_by_zone_district(zone_names)
            }

        # 용도지역 일치 확인
        zone_match = self.check_zone_match(lands[0], zone_names)

        # Sub-case 결정
        if zone_match["match_type"] == "일치":
            sub_case = "2-1"
        elif zone_match["match_type"] == "부분일치":
            sub_case = "2-3"
        else:
            sub_case = "2-2"

        # 분석 수행
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

    def process_case3(self, zone_names: List[str], activities: List[str]) -> Dict[str, Any]:
        """
        Case 3 처리: 주소 없이 용도지역/토지이용행위만 질문
        예: "제2종일반주거지역에서 다세대주택 가능해?"
        """
        results = []

        # 용도지역 + 토지이용행위로 법규 검색
        if zone_names and activities:
            # 각 용도지역별로 검색
            for zone in zone_names[:3]:  # 최대 3개
                zone_results = self.search_by_land_use(activities, zone_name=zone)
                if zone_results:
                    # 개발가능성 판정
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
                "analysis": results  # 호환성을 위해 analysis도 추가
            }

        # 용도지역만으로 검색
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

        # 토지이용행위만으로 검색
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

    def compare_lands(self, analysis_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        복수 필지 비교 분석 (개발성적표)
        """
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

        # 요약
        parts = []
        if comparison["developable"]:
            parts.append(f"개발가능: {', '.join(comparison['developable'])}")
        if comparison["conditional"]:
            parts.append(f"조건부: {', '.join(comparison['conditional'])}")
        if comparison["not_developable"]:
            parts.append(f"불가: {', '.join(comparison['not_developable'])}")

        comparison["summary"] = " | ".join(parts) if parts else "분석 결과 없음"

        return comparison

    def _build_context(
        self,
        case_result: Dict[str, Any],
        special_data: Dict[str, Any],
        email: str,
        question_normalized: str
    ) -> str:
        """
        LLM에 전달할 컨텍스트 구성 (ask()에서 분리)

        Args:
            case_result: 케이스 처리 결과
            special_data: 특수 쿼리 결과 (건폐율/용적률, 법률 비교)
            email: 사용자 이메일 (이전 대화 조회용)
            question_normalized: 정규화된 질문 (RAG 검색용)

        Returns:
            str: 구성된 컨텍스트 문자열
        """
        context_parts = []

        # 케이스 정보
        context_parts.append(
            f"[분석 케이스]\n{case_result['case']}-{case_result['sub_case']}: {case_result['message']}\n"
        )

        # 용도지역 일치 여부 (Case2)
        if case_result.get("zone_match"):
            zm = case_result["zone_match"]
            context_parts.append(
                f"[용도지역 검증]\n"
                f"- 판정: {zm['match_type']}\n"
                f"- 실제 용도지역: {', '.join(zm.get('land_zones', []))}\n"
                f"- 입력 용도지역: {', '.join(zm.get('user_zones', []))}\n"
                f"- 설명: {zm['message']}\n"
            )

        # 필지별 분석 결과 (Case 1, 2)
        if case_result.get("analysis") and case_result["case"] != "CASE3":
            context_parts.extend(self._build_land_analysis_context(case_result["analysis"]))

        # Case 3 분석 결과 (주소 없이 용도지역/행위만)
        elif case_result.get("analysis") and case_result["case"] == "CASE3":
            context_parts.extend(self._build_case3_context(case_result["analysis"]))

        # 비교 분석 (Case1-2: 복수 필지)
        if case_result.get("comparison"):
            comp = case_result["comparison"]
            context_parts.append(
                f"[복수 필지 비교 분석]\n"
                f"- 총 {comp['total_count']}개 필지 분석\n"
                f"- {comp['summary']}\n"
            )

        # 특수 쿼리 결과 (건폐율/용적률, 법률 비교)
        context_parts.extend(self._build_special_query_context(special_data))

        # 이전 대화
        chat_history = self.get_recent_chat_history(email, limit=3)
        if chat_history:
            history_text = "\n".join([
                f"Q: {h['question']}\nA: {h['answer']}"
                for h in chat_history[:2]
            ])
            context_parts.append(f"[이전 대화]\n{history_text}\n")

        # RAG 검색 (평면도 관련)
        try:
            question_embedding = self.embedding_manager.embed_text(question_normalized)
            rag_results = pgvector_service.search_internal_eval(
                query_embedding=question_embedding,
                k=2
            )
            if rag_results:
                for i, result in enumerate(rag_results, 1):
                    context_parts.append(f"[참고 평면도 {i}]\n{result['document']}\n")
        except Exception as e:
            logger.warning(f"RAG 검색 실패: {e}")

        return "\n".join(context_parts) if context_parts else "참고할 데이터가 없습니다."

    def _build_land_analysis_context(self, analysis_list: List[Dict[str, Any]]) -> List[str]:
        """필지별 분석 결과 컨텍스트 (Case 1, 2)"""
        context_parts = []

        for i, analysis in enumerate(analysis_list, 1):
            land = analysis.get("land", {})
            feasibility = analysis.get("feasibility", {})

            # 용도지역 표시 (미지정 처리)
            zone1 = land.get('zone1', '-')
            zone2 = land.get('zone2', '')
            if zone2 in ['지정되지않음', '', None]:
                zone_display = zone1
            else:
                zone_display = f"{zone1} / {zone2}"

            land_text = (
                f"[필지 {i} 정보]\n"
                f"- 주소: {land.get('legal_dong_name', '')} {land.get('lot_number', '')}\n"
                f"- 용도지역: {zone_display}\n"
                f"- 지목: {land.get('land_category', '')}\n"
                f"- 이용상황: {land.get('land_use', '')}\n"
            )
            context_parts.append(land_text)

            # 개발가능성 판정
            if isinstance(feasibility, dict):
                feasibility_text = (
                    f"[필지 {i} 개발성적표]\n"
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

            # 관련 법규
            laws = analysis.get("laws", [])
            if laws:
                law_texts = []
                for law in laws[:5]:
                    law_texts.append(
                        f"  · {law.get('zone_district_name', '')} | "
                        f"{law.get('land_use_activity', '')} | "
                        f"{law.get('permission_status', '')} | "
                        f"{law.get('condition_exception', '')[:50] if law.get('condition_exception') else ''}"
                    )
                context_parts.append(f"[필지 {i} 관련 법규]\n" + "\n".join(law_texts) + "\n")

        return context_parts

    def _build_case3_context(self, analysis_list: List[Dict[str, Any]]) -> List[str]:
        """Case 3 분석 결과 컨텍스트 (주소 없이 용도지역/행위만)"""
        context_parts = []

        for i, analysis in enumerate(analysis_list, 1):
            zone = analysis.get("zone", "")
            if isinstance(zone, list):
                zone = ", ".join(zone)
            act = analysis.get("activities", [])
            feasibility = analysis.get("feasibility", {})
            laws = analysis.get("laws", [])

            # 검색 조건
            context_parts.append(
                f"[검색 {i} 조건]\n"
                f"- 용도지역: {zone}\n"
                f"- 토지이용행위: {', '.join(act) if act else '-'}\n"
            )

            # 개발가능성 판정
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

            # 관련 법규
            if laws:
                law_texts = []
                for law in laws[:8]:
                    condition = law.get('condition_exception', '')
                    condition_short = condition[:50] + "..." if condition and len(condition) > 50 else (condition or "")
                    law_texts.append(
                        f"  · {law.get('zone_district_name', '')} | "
                        f"{law.get('land_use_activity', '')} | "
                        f"{law.get('permission_status', '')} | "
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

            # DB에서 조회된 추가 규제
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

            # DB 원본 데이터 (조건/예외)
            if reg.get("raw_data"):
                reg_text += "\n[관련 조문]\n"
                for item in reg["raw_data"][:3]:
                    condition = item.get("condition_exception", "")
                    if condition and len(condition) > 10:
                        reg_text += f"  · {condition[:120]}...\n"

            context_parts.append(reg_text)

        # 법률/조례 비교
        logger.debug(f"[디버그] special_data keys: {special_data.keys() if special_data else 'empty'}")
        if special_data.get("law_comparison"):
            lc = special_data["law_comparison"]
            logger.debug(f"[디버그] law_comparison 있음: 건축법 {lc.get('building_law_count', 0)}건, 조례 {lc.get('ordinance_count', 0)}건")

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

            # 건축법 vs 조례 직접 비교
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
                        bl_status = building_law.get("permission_status", "")
                        bl_condition = building_law.get("condition", "") or building_law.get("condition_exception", "")
                        bl_cond_short = bl_condition[:80] + "..." if bl_condition and len(bl_condition) > 80 else (bl_condition or "조건 없음")

                        lc_text += f"  [건축법] {bl_name}\n"
                        lc_text += f"    · 판정: {bl_status}\n"
                        lc_text += f"    · 조건: {bl_cond_short}\n"

                    if ordinance_list:
                        lc_text += f"  [조례 - {len(ordinance_list)}개 지역]\n"
                        for ord_item in ordinance_list[:3]:
                            ord_name = ord_item.get("law_name", "")[:35]
                            ord_status = ord_item.get("permission_status", "")
                            ord_condition = ord_item.get("condition", "") or ord_item.get("condition_exception", "")
                            ord_cond_short = ord_condition[:80] + "..." if ord_condition and len(ord_condition) > 80 else (ord_condition or "조건 없음")

                            lc_text += f"    · {ord_name}\n"
                            lc_text += f"      판정: {ord_status} / 조건: {ord_cond_short}\n"

                    lc_text += "\n"

            # 조례 샘플 데이터
            sample_ordinances = lc.get("sample_ordinances", [])
            if sample_ordinances:
                lc_text += "[주요 조례 상세 내용]\n"
                lc_text += "※ 실제 적용되는 조례의 구체적 조건입니다.\n\n"

                for ord_item in sample_ordinances[:5]:
                    ord_name = ord_item.get("law_name", "")
                    ord_activity = ord_item.get("activity", "") or ord_item.get("land_use_activity", "")
                    ord_status = ord_item.get("permission_status", "")
                    ord_condition = ord_item.get("condition", "") or ord_item.get("condition_exception", "")
                    ord_cond_text = ord_condition[:120] + "..." if ord_condition and len(ord_condition) > 120 else (ord_condition or "")

                    lc_text += f"  ▸ {ord_name}\n"
                    lc_text += f"    행위: {ord_activity}\n"
                    lc_text += f"    판정: {ord_status}\n"
                    if ord_cond_text:
                        lc_text += f"    조건: {ord_cond_text}\n"
                    lc_text += "\n"

            context_parts.append(lc_text)
            logger.debug(f"[디버그] lc_text 추가됨, 길이: {len(lc_text)}자")

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
                land_use_activity, permission_status, condition_exception
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

            # 질문 정규화 (오타/띄어쓰기 보정)
            question_normalized = self.normalize_query(question)

            # ========================================
            # 1단계: 키워드 + 의도 추출
            # ========================================
            address_info = self.parse_address(question_normalized)
            zone_names = self.extract_zone_district_name(question_normalized)
            activities = self.extract_land_use_activity(question_normalized)
            region_codes = self.extract_region_codes(question_normalized)
            special_queries = self.extract_special_queries(question_normalized)

            logger.info(f"[1단계] 분석 - 주소: {address_info}, 지역지구: {zone_names}, 행위: {activities}, 특수쿼리: {special_queries}")

            # ========================================
            # 2단계: 케이스 분기
            # ========================================
            intent = self.classify_intent(address_info, zone_names, activities)
            logger.info(f"[2단계] 의도 분류: {intent['case']} - {intent['sub_case']}")

            # ========================================
            # 3단계: 데이터 검색 + 4단계: 법규 검토
            # ========================================
            case_result = None

            if intent["case"] == "CASE3":
                # Case 3: 주소 없이 용도지역/토지이용행위만
                case_result = self.process_case3(zone_names, activities)
            elif intent["case"] == "CASE2":
                # Case 2: 주소 + 용도지역
                case_result = self.process_case2(address_info, zone_names, activities)
            else:
                # Case 1: 주소만
                case_result = self.process_case1(address_info, activities)

            logger.info(f"[3-4단계] {case_result['case']}-{case_result['sub_case']}: {case_result['message']}")

            # ========================================
            # 특수 쿼리 처리 (건폐율/용적률, 법률 비교 등)
            # ========================================
            special_data = {}
            if special_queries:
                # 필지 정보에서 용도지역 추출 또는 질문에서 추출한 용도지역 사용
                target_zone = None
                if case_result.get("lands") and len(case_result["lands"]) > 0:
                    target_zone = case_result["lands"][0].get("zone1")
                elif zone_names:
                    target_zone = zone_names[0]

                if target_zone:
                    # 건폐율/용적률 쿼리
                    if "coverage_ratio" in special_queries or "floor_area_ratio" in special_queries:
                        regulations = self.get_zone_regulations(target_zone)
                        if regulations:
                            special_data["regulations"] = regulations
                            logger.info(f"[특수쿼리] 규제 정보 조회: {target_zone}")

                    # 법률/조례 비교 쿼리
                    if "law_comparison" in special_queries:
                        comparison = self.compare_laws(target_zone)
                        if comparison:
                            special_data["law_comparison"] = comparison
                            logger.info(f"[특수쿼리] 법률 비교 조회: {target_zone}, 결과: {comparison.get('total_items', 0)}건, 비교항목: {len(comparison.get('comparisons', []))}개")

            # ========================================
            # 컨텍스트 구성 (분리된 메서드 호출)
            # ========================================
            context = self._build_context(case_result, special_data, email, question_normalized)

            # 디버깅: 컨텍스트 내용 로그 출력
            logger.info(f"[컨텍스트 길이] {len(context)} 글자")
            logger.info(f"[컨텍스트 미리보기]\n{context[:500]}...")

            # ========================================
            # 5단계: LLM 리포트 생성
            # ========================================

            # ----------------------------------------
            # System Prompt (English for better reasoning)
            # 시스템 프롬프트 (추론 성능 향상을 위해 영어로 작성)
            # ----------------------------------------
            system_prompt = (
                # Role Definition (역할 정의)
                "You are a Korean land/building regulation expert. "
                "You help users understand if specific business activities are permitted on their land.\n\n"

                # Task Description (작업 설명)
                "## TASK\n"
                "Analyze the user's question about land development and provide a clear, actionable answer "
                "based ONLY on the [ANALYSIS DATA] provided below.\n\n"

                # Chain of Thought (단계별 사고 유도)
                "## THINKING PROCESS (Follow these steps internally)\n"
                "1. Identify: What land/address is the user asking about?\n"
                "2. Extract: What activity/business does the user want to do?\n"
                "3. Match: Find the zoning district from parcel info\n"
                "4. Search: Look for relevant laws matching zone + activity\n"
                "5. Judge: Is it 가능/조건부 가능/불가?\n"
                "6. Explain: Why? What are the conditions?\n\n"

                # Strict Rules (엄격한 규칙 - 할루시네이션 방지)
                "## STRICT RULES\n"
                "1. Use ONLY information from [ANALYSIS DATA]. NEVER make up laws or conditions.\n"
                "2. IMPORTANT: If ANY relevant data exists in [ANALYSIS DATA], you MUST use it to answer.\n"
                "   - '건축법' includes: 건축법, 건축법시행령, 건축법시행규칙\n"
                "   - '조례' includes: 도시계획조례, 건축조례, 지구단위계획\n"
                "   - Match partial law names (e.g., '건축법시행령 별표1' is part of 건축법)\n"
                "3. Say '해당 정보가 제공되지 않았습니다' ONLY when [ANALYSIS DATA] is completely empty.\n"
                "4. If zone mismatch, start with: '⚠️ 용도지역 불일치'\n"
                "5. Always cite the exact law name when mentioning regulations.\n"
                "6. Keep answer concise (800-1200 characters in Korean, 약 800~1200자).\n"
                "7. For law comparison questions: Look for [법률/조례 비교] section and explain the differences.\n\n"

                # Output Format (출력 형식)
                "## OUTPUT FORMAT (Must respond in Korean)\n\n"
                "IMPORTANT: Write in a friendly, conversational tone like a helpful expert consultant.\n"
                "- Avoid overly formal markdown headers (##, ###)\n"
                "- Use simple formatting: bold for key points, bullet points sparingly\n"
                "- Start with a direct answer, then explain\n"
                "- Be concise but warm\n\n"
                "### Style Examples:\n"
                "❌ Bad: '## 1. 결론\\n해당 필지에서...'\n"
                "✅ Good: '네, **카페 운영 가능**합니다! 다만 몇 가지 조건이 있어요.'\n\n"
                "❌ Bad: '### 3. 관련 법규\\n- 건축법시행령 별표1...'\n"
                "✅ Good: '관련 법규를 보면, **건축법시행령 별표1**에서 휴게음식점을 허용하고 있어요.'\n\n"
                "### Answer Structure (flexible, not rigid):\n"
                "1. **핵심 답변** - 질문에 대한 직접적인 대답 (1-2문장)\n"
                "2. **상세 설명** - 근거 법률, 조건, 제한사항 등\n"
                "3. **참고/주의사항** - 추가 확인 필요사항 (선택)\n\n"

                # Example (Few-shot 예시)
                "## EXAMPLE ANSWERS\n\n"
                "### Example 1 (건축 가능 여부)\n"
                "```\n"
                "네, 해당 필지에서 **카페 운영이 가능**합니다! 🏠\n\n"
                "**필지 정보**\n"
                "서울시 종로구 청운동 1-2 (제1종일반주거지역, 지목: 대)\n\n"
                "**관련 법규**\n"
                "건축법시행령 별표1 제3호나목에 따라 휴게음식점이 허용돼요.\n"
                "다만 **4층 이하** 건물에서만 가능하고, 조례에 따라 추가 제한이 있을 수 있어요.\n\n"
                "💡 실제 창업 전에 관할 구청 건축과에서 사전상담 받아보시는 걸 추천드려요!\n"
                "```\n\n"
                "### Example 2 (법률 비교)\n"
                "```\n"
                "건축법과 도시계획조례의 주요 차이점을 설명드릴게요.\n\n"
                "**건축법** (국가법)\n"
                "전국에 공통 적용되는 기본 규정이에요. 건축물 용도별 허용 여부의 큰 틀을 정합니다.\n\n"
                "**도시계획조례** (지자체법)\n"
                "각 지자체가 지역 특성에 맞게 추가로 정한 규정이에요. 건축법보다 더 엄격하거나 세부적인 조건을 붙이는 경우가 많아요.\n\n"
                "예를 들어, 건축법에서 '가능'이어도 조례에서 면적이나 층수 제한을 둘 수 있어요.\n"
                "```\n\n"

                # Analysis Data (분석 데이터)
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
            logger.info(f"[답변 미리보기] {answer[:200]}...")

            return {
                "summaryTitle": summary_title,
                "answer": answer
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
