"""LLM API 추상화 계층"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Type
from pydantic import BaseModel
from openai import OpenAI

class LLMClient(ABC):
    @abstractmethod
    def query(self, messages: List[Dict], response_model: Optional[Type[BaseModel]] = None):
        """LLM 쿼리"""
        pass

class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", temperature: float = 0.1):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature

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
                temperature=self.temperature
            )
            return response.choices[0].message.parsed
        else:
            # 일반 텍스트
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature
            )
            return response.choices[0].message.content

# 로컬 모델로 교체 가능
class LocalLLMClient(LLMClient):
    """
    나중에 Qwen 3, Llama 등 로컬 모델로 교체

    예시:
    - ollama API
    - vllm 서버
    - transformers 직접 로드
    """
    def __init__(self, model_path: str):
        self.model_path = model_path
        # TODO: 로컬 모델 초기화

    def query(self, messages: List[Dict], response_model: Optional[Type[BaseModel]] = None):
        # TODO: 로컬 모델 추론
        pass
