from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    """모든 에이전트의 베이스 클래스"""

    @property
    @abstractmethod
    def name(self) -> str:
        """에이전트 식별 이름"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """에이전트 메인 실행 메서드"""
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """내부 컴포넌트 로드 완료 여부"""
        pass
