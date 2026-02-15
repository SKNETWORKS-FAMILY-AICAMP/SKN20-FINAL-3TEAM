"""
오케스트레이터 에이전트
입력 판단 → 의도 분류 → 에이전트 라우팅
"""

import json
import logging
import time
from typing import Any, Dict, Optional

import numpy as np
from openai import OpenAI

from agents.cv_analysis_agent import CVAnalysisAgent
from agents.floorplan_search_agent import FloorplanSearchAgent
from agents.regulation_search_agent import RegulationSearchAgent
from api_models.schemas import IntentClassification

logger = logging.getLogger("OrchestratorAgent")


INTENT_SYSTEM_PROMPT = """당신은 건축 질의를 위한 의도 분류 전문가입니다.

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


class OrchestratorAgent:
    """오케스트레이터: 입력 판단 + 의도 분류 + 라우팅"""

    def __init__(self):
        self._config = None
        self._openai_client: Optional[OpenAI] = None
        self.cv_agent = CVAnalysisAgent()
        self.floorplan_agent = FloorplanSearchAgent()
        self.regulation_agent = RegulationSearchAgent()

    def _load_components(self):
        if self._openai_client is not None:
            return
        from CV.rag_system.config import RAGConfig
        self._config = RAGConfig()
        self._openai_client = OpenAI(api_key=self._config.OPENAI_API_KEY)
        logger.info("OrchestratorAgent 컴포넌트 로드 완료")

    # ===== 내부 Tool 1: 입력 유형 판단 =====

    def _detect_input_type(self, has_image: bool) -> str:
        return "image" if has_image else "text"

    # ===== 내부 Tool 2: 의도 분류 (텍스트 전용) =====

    def _classify_intent(self, question: str) -> IntentClassification:
        """사용자 질문을 검색 의도 카테고리로 분류"""
        self._load_components()

        try:
            logger.info(f"질문 의도 분류 중: {question}")

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

            response = self._openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content
            result_dict = json.loads(result_text)
            intent = IntentClassification(**result_dict)

            logger.info(
                f"의도 분류 완료: {intent.intent_type} "
                f"(신뢰도: {intent.confidence:.2f})"
            )
            return intent

        except Exception as e:
            logger.error(f"의도 분류 실패: {e}")
            return IntentClassification(
                intent_type="FLOORPLAN_SEARCH",
                confidence=0.5,
                extracted_metadata={},
                reasoning=f"분류 중 오류 발생: {str(e)}",
            )

    # ===== 메인 라우팅 =====

    def route(
        self,
        email: str,
        question: str = "",
        image: Optional[np.ndarray] = None,
        filename: str = "",
    ) -> Dict[str, Any]:
        """오케스트레이션 메인 진입점"""
        start_time = time.perf_counter()

        # 입력 검증
        if image is None and (not question or not question.strip()):
            raise ValueError("질문 또는 이미지가 필요합니다")
        if question and len(question) > 1000:
            raise ValueError("질문이 너무 깁니다 (최대 1000자)")
        if not email or "@" not in email:
            raise ValueError("유효하지 않은 이메일")

        input_type = self._detect_input_type(has_image=image is not None)

        if input_type == "image":
            return self._route_image(
                email=email,
                image=image,
                filename=filename,
                start_time=start_time,
            )
        else:
            return self._route_text(
                email=email,
                question=question,
                start_time=start_time,
            )

    def _route_image(
        self,
        email: str,
        image: np.ndarray,
        filename: str,
        start_time: float,
    ) -> Dict[str, Any]:
        """이미지 입력 라우팅"""
        logger.info("[image] CV 분석 + 도면 검색 에이전트 호출")

        cv_result = self.cv_agent.execute(
            image=image, filename=filename, mode="full",
        )
        response = self.floorplan_agent.execute(
            mode="image", cv_result=cv_result,
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "intent_type": "FLOORPLAN_IMAGE",
            "confidence": 1.0,
            "agent_used": "cv_analysis + floorplan_search",
            "response": response,
            "metadata": {"query_time_ms": elapsed_ms},
        }

    def _route_text(
        self,
        email: str,
        question: str,
        start_time: float,
    ) -> Dict[str, Any]:
        """텍스트 입력 라우팅 (의도 분류 → 에이전트)"""
        intent = self._classify_intent(question)

        agent_used = None
        response = None

        try:
            if intent.intent_type == "FLOORPLAN_SEARCH":
                response = self.floorplan_agent.execute(
                    mode="text_search", query=question, email=email,
                )
                agent_used = "floorplan_search"
            else:
                response = self.regulation_agent.execute(
                    email=email, question=question,
                )
                agent_used = "regulation_search"
        except Exception as primary_err:
            logger.error(f"1차 에이전트 실패 ({intent.intent_type}): {primary_err}")
            # Fallback: 다른 에이전트 시도
            try:
                if intent.intent_type == "FLOORPLAN_SEARCH":
                    response = self.regulation_agent.execute(
                        email=email, question=question,
                    )
                    agent_used = "regulation_search"
                else:
                    response = self.floorplan_agent.execute(
                        mode="text_search", query=question, email=email,
                    )
                    agent_used = "floorplan_search"
                logger.info(f"Fallback 에이전트 성공: {agent_used}")
            except Exception as fallback_err:
                raise RuntimeError(
                    f"모든 에이전트 실패 - 1차: {primary_err}, fallback: {fallback_err}"
                ) from fallback_err

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            f"오케스트레이션 완료: agent={agent_used}, time={elapsed_ms}ms"
        )

        return {
            "intent_type": intent.intent_type,
            "confidence": intent.confidence,
            "agent_used": agent_used,
            "response": response,
            "metadata": {
                "query_time_ms": elapsed_ms,
                "extracted_metadata": intent.extracted_metadata,
                "reasoning": intent.reasoning,
            },
        }

    def is_loaded(self) -> bool:
        return self._openai_client is not None
