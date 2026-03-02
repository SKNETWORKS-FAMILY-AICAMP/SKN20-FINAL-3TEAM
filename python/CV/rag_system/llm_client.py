"""LLM API 추상화 계층"""
import json
import re
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Type

from pydantic import BaseModel
from openai import OpenAI, LengthFinishReasonError

logger = logging.getLogger(__name__)

class LLMClient(ABC):
    @abstractmethod
    def query(self, messages: List[Dict], response_model: Optional[Type[BaseModel]] = None):
        """LLM 쿼리"""
        pass

class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", temperature: float = 0.1, max_tokens: int = 16000):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def query(self, messages: List[Dict], response_model: Optional[Type[BaseModel]] = None):
        """
        OpenAI API 호출

        Args:
            messages: [{"role": "system", "content": "..."}, ...]
            response_model: Pydantic 모델 (구조화된 출력)

        Returns:
            response_model 인스턴스 또는 문자열
        """
        if response_model:
            # 구조화된 출력
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=response_model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.parsed
        else:
            # 일반 텍스트
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content

class LocalLLMClient(LLMClient):
    """
    vLLM 서버 기반 로컬 LLM 클라이언트

    OpenAI 호환 API를 통해 vLLM 서버와 통신.
    beta.chat.completions.parse()로 구조화 출력 지원.
    """

    def __init__(self, base_url: str, model: str, temperature: float = 0.1, max_tokens: int = 7000):
        self.client = OpenAI(api_key="EMPTY", base_url=base_url)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        logger.info(f"LocalLLMClient 초기화: base_url={base_url}, model={model}")

    @staticmethod
    def _strip_think(text: str) -> str:
        """Qwen3 <think>...</think> 블록 제거"""
        if text is None:
            return ""
        return re.sub(r"<think>[\s\S]*?</think>\s*", "", text).strip()

    def query(self, messages: List[Dict], response_model: Optional[Type[BaseModel]] = None):
        """
        vLLM 서버 API 호출

        Args:
            messages: [{"role": "system", "content": "..."}, ...]
            response_model: Pydantic 모델 (구조화된 출력)

        Returns:
            response_model 인스턴스 또는 문자열
        """
        if response_model:
            try:
                response = self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=messages,
                    response_format=response_model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            except LengthFinishReasonError as e:
                logger.warning("vLLM 응답이 max_tokens에서 잘림 — 수동 JSON 파싱 시도")
                response = e.completion
                raw = self._strip_think(response.choices[0].message.content)
                return response_model(**json.loads(raw))
            parsed = response.choices[0].message.parsed
            if parsed is None:
                logger.warning("vLLM parsed 결과 None — 수동 JSON 파싱 시도")
                raw = self._strip_think(response.choices[0].message.content)
                return response_model(**json.loads(raw))
            return parsed
        else:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return self._strip_think(response.choices[0].message.content)
