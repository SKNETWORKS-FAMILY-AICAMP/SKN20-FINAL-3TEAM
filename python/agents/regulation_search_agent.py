"""
법/조례 검색 에이전트
chatbot_service_v2 래핑
"""

import logging
from typing import Optional

from agents.base import BaseAgent

logger = logging.getLogger("RegulationSearchAgent")


class RegulationSearchAgent(BaseAgent):
    """법/조례 검색 에이전트 — chatbot_service_v2 래핑"""

    @property
    def name(self) -> str:
        return "regulation_search"

    def __init__(self):
        self._chatbot_service = None

    def _load_components(self):
        if self._chatbot_service is not None:
            return
        from services.chatbot_service_v2 import chatbot_service
        self._chatbot_service = chatbot_service
        logger.info("RegulationSearchAgent 컴포넌트 로드 완료")

    def execute(self, email: str, question: str) -> dict:
        """
        법/조례 검색 실행

        Args:
            email: 사용자 이메일
            question: 사용자 질문

        Returns:
            {"summaryTitle": str, "answer": str}
        """
        self._load_components()
        logger.info(f"[regulation] 질의: {question}")
        result = self._chatbot_service.ask(email, question)
        return {
            "summaryTitle": result["summaryTitle"],
            "answer": result["answer"],
        }

    def is_loaded(self) -> bool:
        return self._chatbot_service is not None
