"""
law_verification.py - 건축 법규 답변 자동 검증 파이프라인

LLM이 생성한 건축 법규 답변의 정확성을 자동으로 검증하는 모듈.
답변이 사용자 질문의 조건(지역, 용도 등)과 실제 법령 DB의 수치에 부합하는지 검증.
"""

import json
import logging
import re
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from pydantic import BaseModel, Field, field_validator
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI
from CV.rag_system.config import RAGConfig

logger = logging.getLogger("LawVerification")


# ==========================================
# 검증 결과 열거형
# ==========================================
class VerificationStatus(str, Enum):
    """검증 상태"""
    PASS = "pass"
    FAIL = "fail"
    RETRY = "retry"
    PARTIAL = "partial"


# ==========================================
# Pydantic 스키마 정의
# ==========================================
class ExtractedLawInfo(BaseModel):
    """LLM 답변에서 추출된 법규 정보"""
    region: Optional[str] = Field(None, description="지역명 (예: 서울특별시 강남구)")
    zone_district: Optional[str] = Field(None, description="용도지역/지구 (예: 제1종일반주거지역)")
    building_coverage_ratio: Optional[float] = Field(None, description="건폐율 (%) - 답변에 명시된 수치")
    floor_area_ratio: Optional[float] = Field(None, description="용적률 (%) - 답변에 명시된 수치")
    height_limit: Optional[float] = Field(None, description="높이 제한 (m)")
    floor_limit: Optional[int] = Field(None, description="층수 제한")
    land_use_activity: Optional[str] = Field(None, description="토지 이용 행위 (예: 건축물신축)")
    permission_category: Optional[str] = Field(None, description="허가 구분 (허용/불허/조건부허용)")
    cited_laws: List[str] = Field(default_factory=list, description="인용된 법률/조례명")
    conditions: Optional[str] = Field(None, description="조건 및 예외사항")
    
    @field_validator('building_coverage_ratio', 'floor_area_ratio', 'height_limit')
    @classmethod
    def validate_positive(cls, v):
        """수치는 0보다 커야 함"""
        if v is not None and v < 0:
            raise ValueError("수치는 0 이상이어야 합니다")
        return v


class QuestionContext(BaseModel):
    """사용자 질문의 컨텍스트"""
    address: Optional[str] = Field(None, description="주소/필지")
    lot_number: Optional[str] = Field(None, description="지번")
    region: Optional[str] = Field(None, description="지역")
    zone_district: Optional[str] = Field(None, description="용도지역")
    activities: List[str] = Field(default_factory=list, description="질문한 토지이용 행위")
    asked_items: List[str] = Field(default_factory=list, description="질문한 항목 (건폐율, 용적률, 일조권 등)")


class VerificationResult(BaseModel):
    """검증 결과"""
    status: VerificationStatus = Field(..., description="검증 상태 (pass/fail/retry/partial)")
    score: float = Field(..., description="검증 점수 (0-100)")
    issues: List[str] = Field(default_factory=list, description="발견된 문제점")
    warnings: List[str] = Field(default_factory=list, description="경고사항")
    details: Dict[str, Any] = Field(default_factory=dict, description="상세 검증 결과")
    recommendation: Optional[str] = Field(None, description="개선 권장사항")


class DBReference(BaseModel):
    """DB 조회 결과 (참조 데이터)"""
    region_code: str
    region_name: str
    zone_district_name: str
    law_name: str
    land_use_activity: str
    permission_category: str
    condition_exception: Optional[str]


# ==========================================
# 건축 법규 검증 클래스
# ==========================================
class ArchitectureLawValidator:
    """
    건축 법규 답변 자동 검증 파이프라인
    
    주요 기능:
    1. LLM 답변에서 법규 정보 추출 (Pydantic 스키마 기반)
    2. Hard Rule 검증: DB 데이터와 수치 비교
    3. Semantic Consistency 검증: LLM 기반 의미적 일관성 체크
    4. 최종 Pass/Fail 결정
    """
    
    # DB 연결 설정 (환경변수로 관리 권장)
    DB_CONFIG = {
        "host": "localhost",
        "database": "arae",
        "user": "postgres",
        "password": "1234",
        "port": 5432,
    }
    
    # 검증 임계값 설정
    PASS_THRESHOLD = 70.0  # 70점 이상 Pass
    RETRY_THRESHOLD = 50.0  # 50점 이상 Retry, 미만 Fail
    
    def __init__(self, openai_api_key: str = None, skip_db_init: bool = False):
        """
        Args:
            openai_api_key: OpenAI API 키 (None이면 RAGConfig에서 자동 로드)
            skip_db_init: True면 DB 연결을 초기화하지 않음 (테스트용)
        """
        # 모든 인스턴스 변수를 먼저 초기화 (예외 발생 시에도 속성 존재 보장)
        self.db_conn = None
        self._skip_db_init = skip_db_init
        self.client = None
        
        # OpenAI 클라이언트 초기화
        if openai_api_key is None:
            # RAGConfig에서 API 키 로드
            try:
                config = RAGConfig()
                openai_api_key = config.OPENAI_API_KEY
                logger.info("RAGConfig에서 OpenAI API 키 로드 성공")
            except Exception as e:
                logger.error(f"RAGConfig 로드 실패: {e}")
                raise ValueError("OpenAI API 키를 찾을 수 없습니다. .env 파일을 확인하세요.")
        
        self.client = OpenAI(api_key=openai_api_key)
        
        # DB 연결 초기화
        if not skip_db_init:
            try:
                self._connect_db()
            except Exception as e:
                logger.warning(f"DB 초기 연결 실패 (나중에 재시도됩니다): {e}")
        
    def _connect_db(self):
        """PostgreSQL 연결 (chatbot_service_v2와 동일한 방식)"""
        try:
            if self.db_conn is None or self.db_conn.closed:
                self.db_conn = psycopg2.connect(**self.DB_CONFIG)
                logger.info("DB 연결 성공")
        except Exception as e:
            logger.error(f"DB 연결 실패: {e}")
            raise
    
    def __del__(self):
        """소멸자: DB 연결 종료"""
        try:
            if hasattr(self, 'db_conn') and self.db_conn and not self.db_conn.closed:
                self.db_conn.close()
        except Exception:
            pass  # 소멸자에서는 예외를 무시
    
    # ==========================================
    # STEP 1: Information Extraction
    # ==========================================
    def extract_info_from_answer(self, llm_answer: str) -> ExtractedLawInfo:
        """
        LLM 답변에서 법규 정보를 추출하는 함수.
        
        Args:
            llm_answer: LLM이 생성한 답변 텍스트
            
        Returns:
            ExtractedLawInfo: 추출된 정보 (Pydantic 스키마)
        """
        logger.info("=== STEP 1: Information Extraction ===")
        
        # LLM을 사용한 구조화된 정보 추출
        extraction_prompt = f"""
다음 건축 법규 답변에서 핵심 정보를 추출하세요.

답변:
{llm_answer}

다음 항목들을 JSON 형식으로 추출하세요:
- region: 지역명 (예: "서울특별시 강남구")
- zone_district: 용도지역/지구 (예: "제1종일반주거지역")
- building_coverage_ratio: 건폐율 (숫자만, 단위 제외)
- floor_area_ratio: 용적률 (숫자만, 단위 제외)
- height_limit: 높이 제한 (숫자만, m 단위)
- floor_limit: 층수 제한 (숫자만)
- land_use_activity: 토지 이용 행위 (예: "건축물신축")
- permission_category: 허가 구분 ("허용", "불허", "조건부허용" 중 하나)
- cited_laws: 인용된 법률명 리스트 (예: ["건축법 제56조", "서울특별시 건축조례"])
- conditions: 조건 및 예외사항 텍스트

정보가 없으면 null로 표시하세요.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "너는 건축 법규 텍스트 분석 전문가야. JSON 형식으로만 답변해."},
                    {"role": "user", "content": extraction_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            extracted_data = json.loads(response.choices[0].message.content)
            logger.info(f"추출된 정보: {extracted_data}")
            
            # cited_laws가 None이면 빈 리스트로 변환 (Pydantic 검증 통과)
            if extracted_data.get('cited_laws') is None:
                extracted_data['cited_laws'] = []
            
            # Pydantic 검증
            return ExtractedLawInfo(**extracted_data)
            
        except Exception as e:
            logger.error(f"정보 추출 실패: {e}")
            # 실패 시 정규식 기반 폴백 추출
            return self._fallback_extraction(llm_answer)
    
    def _fallback_extraction(self, text: str) -> ExtractedLawInfo:
        """정규식 기반 폴백 추출 (LLM 실패 시)"""
        logger.warning("폴백 추출 모드 실행")
        
        extracted = {}
        
        # 건폐율 추출
        bcr_match = re.search(r'건폐율[:\s]*(\d+(?:\.\d+)?)%', text)
        if bcr_match:
            extracted['building_coverage_ratio'] = float(bcr_match.group(1))
        
        # 용적률 추출
        far_match = re.search(r'용적률[:\s]*(\d+(?:\.\d+)?)%', text)
        if far_match:
            extracted['floor_area_ratio'] = float(far_match.group(1))
        
        # 높이 제한 추출
        height_match = re.search(r'높이[:\s]*(\d+(?:\.\d+)?)m', text)
        if height_match:
            extracted['height_limit'] = float(height_match.group(1))
        
        # 층수 제한 추출
        floor_match = re.search(r'(\d+)층\s*(?:이하|까지)', text)
        if floor_match:
            extracted['floor_limit'] = int(floor_match.group(1))
        
        # 용도지역 추출
        zone_patterns = [
            r'제\d종(?:전용|일반)주거지역',
            r'(?:중심|일반|근린|유통)상업지역',
            r'(?:전용|일반|준)공업지역',
            r'(?:보전|생산|자연)녹지지역'
        ]
        for pattern in zone_patterns:
            match = re.search(pattern, text)
            if match:
                extracted['zone_district'] = match.group(0)
                break
        
        # 허가 구분 추출
        if '허용' in text and '조건부' in text:
            extracted['permission_category'] = '조건부허용'
        elif '불허' in text or '금지' in text:
            extracted['permission_category'] = '불허'
        elif '허용' in text or '가능' in text:
            extracted['permission_category'] = '허용'
        
        return ExtractedLawInfo(**extracted)
    
    # ==========================================
    # STEP 2: Deterministic Verification (Hard Rule)
    # ==========================================
    def verify_against_db(
        self,
        extracted_info: ExtractedLawInfo,
        question_context: QuestionContext
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        추출된 정보를 DB 데이터와 비교하여 Hard Rule 검증.
        
        Args:
            extracted_info: 추출된 법규 정보
            question_context: 질문 컨텍스트
            
        Returns:
            (검증통과여부, 이슈목록, 상세정보)
        """
        logger.info("=== STEP 2: Deterministic Verification (Hard Rule) ===")
        
        issues = []
        details = {}
        
        try:
            self._connect_db()
            cursor = self.db_conn.cursor(cursor_factory=RealDictCursor)
            
            # DB에서 해당 지역/용도지역의 법규 조회
            query = """
            SELECT 
                region_code, region_name, zone_district_name, 
                law_name, land_use_activity, permission_category, condition_exception
            FROM law
            WHERE 1=1
            """
            params = []
            
            # 지역 필터
            if question_context.region:
                query += " AND region_name ILIKE %s"
                params.append(f"%{question_context.region}%")
            
            # 용도지역 필터
            if extracted_info.zone_district:
                query += " AND zone_district_name = %s"
                params.append(extracted_info.zone_district)
            elif question_context.zone_district:
                query += " AND zone_district_name = %s"
                params.append(question_context.zone_district)
            
            # 토지이용 행위 필터
            if question_context.activities:
                activity_conditions = " OR ".join(["land_use_activity ILIKE %s"] * len(question_context.activities))
                query += f" AND ({activity_conditions})"
                params.extend([f"%{act}%" for act in question_context.activities])
            
            query += " LIMIT 50"
            
            cursor.execute(query, params)
            db_records = cursor.fetchall()
            
            details['db_record_count'] = len(db_records)
            details['db_records'] = [dict(record) for record in db_records]
            
            if not db_records:
                issues.append("❌ DB에서 해당 조건의 법규를 찾을 수 없습니다.")
                logger.warning("DB 조회 결과 없음")
                return False, issues, details
            
            # 1. 용도지역 일치성 검증
            if extracted_info.zone_district:
                db_zones = set(r['zone_district_name'] for r in db_records)
                if extracted_info.zone_district not in db_zones:
                    issues.append(f"⚠️ 용도지역 불일치: 답변={extracted_info.zone_district}, DB={db_zones}")
            
            # 2. 허가 구분 검증
            if extracted_info.permission_category:
                db_permissions = set(r['permission_category'] for r in db_records if r['land_use_activity'])
                
                # 답변이 "허용"인데 DB에 "불허"가 있으면 문제
                if extracted_info.permission_category == '허용' and '불허' in db_permissions:
                    issues.append(f"❌ 허가 구분 오류: 답변은 '허용'이나 DB에 '불허' 규정 존재")
                
                # 조건부허용인데 조건을 명시하지 않으면 경고
                if extracted_info.permission_category == '조건부허용' and not extracted_info.conditions:
                    issues.append(f"⚠️ 조건부허용이나 조건 내용이 답변에 누락됨")
            
            # 3. 건폐율/용적률 상한선 검증 (DB에 수치 데이터가 있다면)
            # 주의: Law 테이블에는 건폐율/용적률이 텍스트로 condition_exception에 포함될 수 있음
            # 실제 프로젝트에서는 별도 테이블이나 파싱 로직 필요
            for record in db_records:
                condition = record.get('condition_exception', '')
                if condition:
                    # 건폐율 체크
                    if extracted_info.building_coverage_ratio:
                        bcr_match = re.search(r'건폐율[:\s]*(\d+)%\s*이하', condition)
                        if bcr_match:
                            db_bcr = float(bcr_match.group(1))
                            if extracted_info.building_coverage_ratio > db_bcr:
                                issues.append(
                                    f"❌ 건폐율 초과: 답변={extracted_info.building_coverage_ratio}%, "
                                    f"법적상한={db_bcr}%"
                                )
                    
                    # 용적률 체크
                    if extracted_info.floor_area_ratio:
                        far_match = re.search(r'용적률[:\s]*(\d+)%\s*이하', condition)
                        if far_match:
                            db_far = float(far_match.group(1))
                            if extracted_info.floor_area_ratio > db_far:
                                issues.append(
                                    f"❌ 용적률 초과: 답변={extracted_info.floor_area_ratio}%, "
                                    f"법적상한={db_far}%"
                                )
            
            # 4. 인용 법률 검증 (DB의 law_name과 비교)
            if extracted_info.cited_laws:
                db_law_names = set(r['law_name'] for r in db_records if r['law_name'])
                for cited in extracted_info.cited_laws:
                    # 단순 포함 관계 체크 (정확한 매칭은 복잡할 수 있음)
                    if not any(cited in law_name or law_name in cited for law_name in db_law_names):
                        issues.append(f"⚠️ 인용 법률 '{cited}'이 DB 법규 목록에서 확인되지 않음")
            
            cursor.close()
            
            # 이슈가 없으면 통과
            verification_passed = len([i for i in issues if i.startswith('❌')]) == 0
            
            logger.info(f"Hard Rule 검증 결과: {'통과' if verification_passed else '실패'}")
            return verification_passed, issues, details
            
        except Exception as e:
            logger.error(f"DB 검증 오류: {e}")
            issues.append(f"❌ DB 검증 중 오류 발생: {str(e)}")
            return False, issues, details
    
    # ==========================================
    # STEP 3: Semantic Consistency Check (LLM Evaluation)
    # ==========================================
    def verify_semantic_consistency(
        self,
        llm_answer: str,
        question: str,
        db_reference: str,
        question_context: QuestionContext
    ) -> Tuple[bool, List[str], float]:
        """
        LLM을 사용하여 답변의 의미적 일관성 검증.
        
        Args:
            llm_answer: LLM이 생성한 답변
            question: 원본 질문
            db_reference: DB 조회 결과 (텍스트)
            question_context: 질문 컨텍스트
            
        Returns:
            (검증통과여부, 이슈목록, 일관성점수)
        """
        logger.info("=== STEP 3: Semantic Consistency Check (LLM Evaluation) ===")
        
        consistency_prompt = f"""
당신은 건축 법규 전문가입니다. 다음 항목을 검증하세요:

[사용자 질문]
{question}

[LLM 답변]
{llm_answer}

[DB 참조 데이터]
{db_reference}

[질문 컨텍스트]
- 질문한 항목: {', '.join(question_context.asked_items) if question_context.asked_items else '없음'}
- 요청 지역: {question_context.region or '없음'}
- 요청 용도지역: {question_context.zone_district or '없음'}
- 토지이용 행위: {', '.join(question_context.activities) if question_context.activities else '없음'}

다음 기준으로 검증하고 JSON으로 답변하세요:

1. 답변이 DB 참조 데이터의 범위를 벗어나는가? (hallucination 체크)
2. 질문에서 요청한 항목이 답변에 모두 포함되었는가? (completeness 체크)
3. 답변이 법령의 의미를 왜곡하거나 잘못 해석했는가?
4. 건축법과 조례가 충돌하는 경우 조례를 우선시했는가?
5. 조건부 허용인 경우 구체적인 조건을 명시했는가?

JSON 형식:
{{
    "hallucination_detected": true/false,
    "missing_items": ["건폐율", "일조권"],
    "misinterpretation": true/false,
    "ordinance_priority": true/false,
    "condition_specified": true/false,
    "consistency_score": 0-100,
    "issues": ["이슈1", "이슈2"],
    "explanation": "검증 설명"
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "너는 건축 법규 검증 전문가야. JSON 형식으로만 답변해."},
                    {"role": "user", "content": consistency_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"의미적 일관성 검증 결과: {result}")
            
            issues = result.get('issues', [])
            score = result.get('consistency_score', 50)
            
            # 심각한 문제가 있으면 실패
            passed = (
                not result.get('hallucination_detected', False) and
                not result.get('misinterpretation', False) and
                len(result.get('missing_items', [])) == 0
            )
            
            return passed, issues, score
            
        except Exception as e:
            logger.error(f"의미적 일관성 검증 실패: {e}")
            return False, [f"❌ LLM 검증 오류: {str(e)}"], 0.0
    
    # ==========================================
    # STEP 4: Final Decision Logic
    # ==========================================
    def verify(
        self,
        llm_answer: str,
        question: str,
        question_context: QuestionContext,
        db_reference: Optional[str] = None
    ) -> VerificationResult:
        """
        전체 검증 파이프라인 실행.
        
        Args:
            llm_answer: LLM이 생성한 답변
            question: 원본 질문
            question_context: 질문 컨텍스트
            db_reference: DB 참조 데이터 (선택)
            
        Returns:
            VerificationResult: 최종 검증 결과
        """
        logger.info("="*60)
        logger.info("법규 답변 검증 파이프라인 시작")
        logger.info("="*60)
        
        all_issues = []
        all_warnings = []
        details = {}
        
        # STEP 1: 정보 추출
        try:
            extracted_info = self.extract_info_from_answer(llm_answer)
            details['extracted_info'] = extracted_info.model_dump()
        except Exception as e:
            logger.error(f"정보 추출 실패: {e}")
            return VerificationResult(
                status=VerificationStatus.FAIL,
                score=0.0,
                issues=[f"❌ 정보 추출 실패: {str(e)}"],
                details=details
            )
        
        # STEP 2: Hard Rule 검증 (DB 비교)
        hard_rule_passed, hard_issues, hard_details = self.verify_against_db(
            extracted_info, question_context
        )
        all_issues.extend([i for i in hard_issues if i.startswith('❌')])
        all_warnings.extend([i for i in hard_issues if i.startswith('⚠️')])
        details['hard_rule'] = hard_details
        
        hard_score = 100.0 if hard_rule_passed else 30.0
        
        # STEP 3: 의미적 일관성 검증 (LLM)
        if not db_reference:
            # DB 조회 결과를 텍스트로 변환
            db_records = hard_details.get('db_records', [])
            db_reference = "\n".join([
                f"- {r['zone_district_name']}, {r['land_use_activity']}: {r['permission_category']} "
                f"({r['law_name']}) - {r['condition_exception']}"
                for r in db_records[:10]  # 최대 10개만
            ])
        
        semantic_passed, semantic_issues, semantic_score = self.verify_semantic_consistency(
            llm_answer, question, db_reference, question_context
        )
        all_issues.extend([i for i in semantic_issues if '❌' in i or '누락' in i or '왜곡' in i])
        all_warnings.extend([i for i in semantic_issues if '⚠️' in i])
        details['semantic_consistency'] = {
            'passed': semantic_passed,
            'score': semantic_score
        }
        
        # STEP 4: 최종 점수 계산 (가중 평균)
        # Hard Rule 60%, Semantic 40%
        final_score = (hard_score * 0.6) + (semantic_score * 0.4)
        
        # 감점 요소
        critical_issue_count = len([i for i in all_issues if '❌' in i or '초과' in i])
        final_score -= critical_issue_count * 10  # 중대 이슈당 -10점
        final_score = max(0.0, min(100.0, final_score))  # 0-100 범위로 제한
        
        # 최종 상태 결정
        if final_score >= self.PASS_THRESHOLD and critical_issue_count == 0:
            status = VerificationStatus.PASS
            recommendation = None
        elif final_score >= self.RETRY_THRESHOLD:
            status = VerificationStatus.RETRY
            recommendation = (
                "답변을 재작성하세요. "
                f"주요 이슈: {', '.join(all_issues[:3]) if all_issues else '경미한 불일치'}"
            )
        else:
            status = VerificationStatus.FAIL
            recommendation = (
                "답변이 법규와 심각하게 불일치합니다. "
                "DB 데이터를 재확인하고 전면 재작성이 필요합니다."
            )
        
        logger.info("="*60)
        logger.info(f"최종 검증 결과: {status.value.upper()} (점수: {final_score:.1f})")
        logger.info(f"이슈: {len(all_issues)}건, 경고: {len(all_warnings)}건")
        logger.info("="*60)
        
        return VerificationResult(
            status=status,
            score=round(final_score, 2),
            issues=all_issues,
            warnings=all_warnings,
            details=details,
            recommendation=recommendation
        )


# ==========================================
# 유틸리티 함수
# ==========================================
def format_verification_report(result: VerificationResult) -> str:
    """검증 결과를 사람이 읽기 쉬운 리포트로 포맷팅"""
    
    status_emoji = {
        VerificationStatus.PASS: "✅",
        VerificationStatus.FAIL: "❌",
        VerificationStatus.RETRY: "🔄",
        VerificationStatus.PARTIAL: "⚠️"
    }
    
    report = [
        "="*60,
        f"{status_emoji[result.status]} 법규 답변 검증 결과: {result.status.value.upper()}",
        "="*60,
        f"📊 검증 점수: {result.score}/100",
        ""
    ]
    
    if result.issues:
        report.append("🚨 발견된 이슈:")
        for issue in result.issues:
            report.append(f"  {issue}")
        report.append("")
    
    if result.warnings:
        report.append("⚠️ 경고사항:")
        for warning in result.warnings:
            report.append(f"  {warning}")
        report.append("")
    
    if result.recommendation:
        report.append("💡 권장사항:")
        report.append(f"  {result.recommendation}")
        report.append("")
    
    report.append("="*60)
    
    return "\n".join(report)


# ==========================================
# 사용 예시
# ==========================================
if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("법규 검증 에이전트 단독 실행")
    print("=" * 60)
    print("\n이 파일을 직접 실행하려면 test_law_verification.py를 사용하세요:")
    print("  python test_law_verification.py")
    print("\n또는 다음과 같이 환경변수를 설정하고 실행하세요:")
    print("  set OPENAI_API_KEY=your-api-key")
    print("  python services\\law_verification.py")
    print("=" * 60)
