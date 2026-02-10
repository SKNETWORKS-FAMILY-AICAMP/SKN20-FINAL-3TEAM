"""
의도 분류 서비스
GPT-4o-mini를 사용하여 사용자 질문을 FLOORPLAN_SEARCH 또는 REGULATION_SEARCH로 분류
"""

import json
import logging
from typing import Optional

from openai import OpenAI

from CV.rag_system.config import RAGConfig
from api_models.schemas import IntentClassification

logger = logging.getLogger("IntentClassifierService")


SYSTEM_PROMPT = """당신은 건축 질의를 위한 의도 분류 전문가입니다.

사용자의 질문을 다음 카테고리 중 **정확히 하나**로 분류하세요:

1. **FLOORPLAN_SEARCH**: 유사한 도면 찾기, 건축 레이아웃, 디자인 패턴, 도면 평가에 관한 질문
   예시:
   - "3Bay 판상형 침실 3개 도면 찾아줘"
   - "거실이 넓은 평면도 보여줘"
   - "이 도면의 채광은 어때?"
   - "무창 비율이 낮은 도면 추천해줘"
   - "판상형 구조의 장단점은?"

2. **REGULATION_SEARCH**: 건축법규, 용도지역 규정, 토지이용 규제, 건축 허가에 관한 질문
   예시:
   - "강남구 대치동에 미용실 지을 수 있어?"
   - "제1종일반주거지역 건축 규정이 뭐야?"
   - "이 지역에 3층 건물 지을 수 있어?"
   - "용적률 제한이 어떻게 돼?"

**분류 규칙**:
- 도면/평면도/레이아웃/구조/공간 배치 → FLOORPLAN_SEARCH
- 법규/지역/용도/허가/규정/제한 → REGULATION_SEARCH
- 애매한 경우: 질문의 핵심 목적이 무엇인지 판단
  - "이 도면이 법규에 맞아?" → FLOORPLAN_SEARCH (도면 평가가 핵심)
  - "이 지역에 이런 구조 지을 수 있어?" → REGULATION_SEARCH (법규 확인이 핵심)

JSON 형식으로 출력하세요."""


class IntentClassifierService:
    """의도 분류 서비스 - GPT-4o-mini 기반"""

    def __init__(self):
        self.config: Optional[RAGConfig] = None
        self.openai_client: Optional[OpenAI] = None

    def load_components(self):
        """OpenAI 클라이언트를 lazy loading 방식으로 로드"""
        if self.openai_client is not None:
            return

        logger.info("의도 분류 컴포넌트 로딩 중...")

        try:
            self.config = RAGConfig()
            self.openai_client = OpenAI(api_key=self.config.OPENAI_API_KEY)
            logger.info("의도 분류 컴포넌트 로딩 완료!")
        except Exception as e:
            logger.error(f"의도 분류 컴포넌트 로딩 실패: {e}")
            raise

    def classify_intent(self, question: str) -> IntentClassification:
        """
        사용자 질문을 검색 의도 카테고리로 분류

        Args:
            question: 사용자 질문

        Returns:
            IntentClassification(
                intent_type: "FLOORPLAN_SEARCH" | "REGULATION_SEARCH",
                confidence: 0.0 - 1.0,
                extracted_metadata: Dict[str, Any],
                reasoning: str
            )
        """
        self.load_components()

        try:
            logger.info(f"질문 의도 분류 중: {question}")

            # 1. 분류 프롬프트 구성
            user_prompt = f"""다음 질문을 분류하세요:

질문: "{question}"

응답은 다음 JSON 형식으로 작성하세요:
{{
  "intent_type": "FLOORPLAN_SEARCH" 또는 "REGULATION_SEARCH",
  "confidence": 0.0에서 1.0 사이의 신뢰도,
  "extracted_metadata": {{
    // 도면 검색인 경우: bay_count, room_count, structure_type, compliance_grade, keywords 등
    // 법규 검색인 경우: address, zone_district, land_use_activity, region_code 등
  }},
  "reasoning": "분류한 이유를 간단히 설명"
}}"""

            # 2. 구조화된 출력으로 GPT-4o-mini 호출
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.1,  # 결정론적 분류
                response_format={"type": "json_object"}
            )

            # 3. Pydantic으로 파싱 및 검증
            result_text = response.choices[0].message.content
            result_dict = json.loads(result_text)

            intent_classification = IntentClassification(**result_dict)

            logger.info(
                f"의도 분류 완료: {intent_classification.intent_type} "
                f"(신뢰도: {intent_classification.confidence:.2f})"
            )

            return intent_classification

        except Exception as e:
            logger.error(f"의도 분류 실패: {e}")
            # 기본값: FLOORPLAN_SEARCH (더 안전한 선택)
            return IntentClassification(
                intent_type="FLOORPLAN_SEARCH",
                confidence=0.5,
                extracted_metadata={},
                reasoning=f"분류 중 오류 발생: {str(e)}"
            )

    def is_loaded(self) -> bool:
        """컴포넌트 로드 여부 확인"""
        return self.openai_client is not None


# 싱글톤 인스턴스
intent_classifier_service = IntentClassifierService()
