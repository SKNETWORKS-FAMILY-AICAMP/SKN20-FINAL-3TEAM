"""
의도 분류 + 오케스트레이션 서비스
GPT-4o-mini를 사용하여 사용자 질문을 분류하고 적절한 에이전트로 라우팅
"""

import json
import logging
import time
from typing import Any, Dict, Optional

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
    """의도 분류 + 오케스트레이션 서비스"""

    def __init__(self):
        self.config: Optional[RAGConfig] = None
        self.openai_client: Optional[OpenAI] = None
        self.floorplan_rag = None
        self.chatbot_service = None

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

    # ====== 오케스트레이션 메서드 ======

    def _load_agents(self):
        """에이전트를 lazy loading 방식으로 초기화"""
        if self.floorplan_rag is not None and self.chatbot_service is not None:
            return

        self.load_components()

        if self.floorplan_rag is None:
            self.floorplan_rag = self._initialize_floorplan_agent()

        if self.chatbot_service is None:
            self.chatbot_service = self._initialize_chatbot_agent()

    def _initialize_floorplan_agent(self):
        """ArchitecturalHybridRAG 인스턴스 생성"""
        from floorplan.pipeline import ArchitecturalHybridRAG

        logger.info("Floorplan 에이전트 초기화 중...")

        db_config = {
            "host": self.config.POSTGRES_HOST,
            "port": self.config.POSTGRES_PORT,
            "database": self.config.POSTGRES_DB,
            "user": self.config.POSTGRES_USER,
            "password": self.config.POSTGRES_PASSWORD,
        }

        rag = ArchitecturalHybridRAG(
            db_config=db_config,
            openai_api_key=self.config.OPENAI_API_KEY,
        )

        logger.info("Floorplan 에이전트 초기화 완료!")
        return rag

    def _initialize_chatbot_agent(self):
        """기존 ChatbotService 싱글톤 가져오기"""
        from services.chatbot_service_v2 import chatbot_service

        logger.info("Chatbot 에이전트 로드 완료!")
        return chatbot_service

    def _call_floorplan_agent(self, query: str, email: str) -> Dict[str, Any]:
        """도면 검색 에이전트 호출 + 응답 래핑"""
        result = self.floorplan_rag.run(query, email=email)

        return {
            "summaryTitle": query[:30] + "..." if len(query) > 30 else query,
            "answer": result.get("answer", "답변을 생성하지 못했습니다."),
            "floorplan_ids": result.get("floorplan_ids", []),
        }

    def _call_chatbot_agent(self, email: str, question: str) -> Dict[str, str]:
        """법/조례 검색 에이전트 호출"""
        result = self.chatbot_service.ask(email, question)

        return {
            "summaryTitle": result["summaryTitle"],
            "answer": result["answer"],
        }

    def route_query(self, email: str, question: str) -> Dict[str, Any]:
        """
        메인 오케스트레이션: 의도 분류 → 에이전트 라우팅 → 통합 응답
        """
        start_time = time.perf_counter()

        # 1. 입력 검증
        if not question or not question.strip():
            raise ValueError("질문이 비어있습니다")
        if len(question) > 1000:
            raise ValueError("질문이 너무 깁니다 (최대 1000자)")
        if not email or "@" not in email:
            raise ValueError("유효하지 않은 이메일")

        # 2. 컴포넌트 + 에이전트 로드
        self._load_agents()

        # 3. 의도 분류
        intent = self.classify_intent(question)

        logger.info(
            f"의도 분류 결과: {intent.intent_type} "
            f"(신뢰도: {intent.confidence:.2f})"
        )

        # 4. 라우팅
        agent_used = None
        response = None

        try:
            if intent.intent_type == "FLOORPLAN_SEARCH":
                response = self._call_floorplan_agent(question, email)
                agent_used = "floorplan"
            else:
                response = self._call_chatbot_agent(email, question)
                agent_used = "chatbot"
        except Exception as primary_err:
            logger.error(f"1차 에이전트 실패 ({intent.intent_type}): {primary_err}")
            # Fallback: 다른 에이전트 시도
            try:
                if intent.intent_type == "FLOORPLAN_SEARCH":
                    response = self._call_chatbot_agent(email, question)
                    agent_used = "chatbot"
                else:
                    response = self._call_floorplan_agent(question, email)
                    agent_used = "floorplan"
                logger.info(f"Fallback 에이전트 성공: {agent_used}")
            except Exception as fallback_err:
                raise RuntimeError(
                    f"모든 에이전트 실패 - 1차: {primary_err}, fallback: {fallback_err}"
                ) from fallback_err

        # 5. 응답 구성
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            f"오케스트레이션 완료: agent={agent_used}, "
            f"time={elapsed_ms}ms"
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


# 싱글톤 인스턴스
intent_classifier_service = IntentClassifierService()
