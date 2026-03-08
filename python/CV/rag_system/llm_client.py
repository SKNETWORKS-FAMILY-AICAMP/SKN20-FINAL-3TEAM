"""LLM API 추상화 계층"""
import json
import re
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Type

from pydantic import BaseModel
from openai import OpenAI, LengthFinishReasonError

logger = logging.getLogger(__name__)


def _repair_truncated_json(raw: str) -> dict:
    """
    vLLM 토큰 제한으로 잘린 JSON을 복구한다.

    전략:
    1. 우선 그대로 파싱 시도
    2. 실패 시 열린 문자열·배열·객체를 닫아 복구
    """
    # 1차: 그대로 파싱
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    text = raw.rstrip()

    # 열린 문자열 닫기 — 마지막 쌍따옴표가 닫히지 않았으면 닫아줌
    quote_count = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '\\':
            i += 2
            continue
        if ch == '"':
            quote_count += 1
        i += 1
    if quote_count % 2 == 1:
        text += '"'

    # 마지막 불완전한 key-value 쌍 제거 (trailing comma 등)
    text = re.sub(r',\s*"[^"]*"\s*:\s*"?$', '', text)
    text = re.sub(r',\s*$', '', text)

    # 열린 괄호 닫기
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    text += ']' * max(open_brackets, 0)
    text += '}' * max(open_braces, 0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 최후 수단: 마지막 완전한 값까지만 남기고 재시도
    for trim in range(1, min(200, len(text))):
        candidate = text[:-trim]
        candidate = re.sub(r',\s*$', '', candidate)
        ob = candidate.count('{') - candidate.count('}')
        obt = candidate.count('[') - candidate.count(']')
        candidate += ']' * max(obt, 0)
        candidate += '}' * max(ob, 0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise ValueError(f"JSON 복구 실패 (원본 길이: {len(raw)})")

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
    max_tokens를 지정하지 않아 vLLM이 (max_model_len - prompt_tokens)로 자동 계산.
    """

    # Qwen3 thinking 비활성화 — 불필요한 <think> 토큰 생성 방지
    _NO_THINK = {"chat_template_kwargs": {"enable_thinking": False}}

    _MAX_RETRIES_ON_LENGTH = 1  # 장황 모드 잘림 시 재시도 횟수

    def __init__(self, base_url: str, model: str, temperature: float = 0.0):
        self.client = OpenAI(api_key="EMPTY", base_url=base_url)
        self.model = model
        self.temperature = temperature
        logger.info(f"LocalLLMClient 초기화: base_url={base_url}, model={model}")

    @staticmethod
    def _strip_think(text: str) -> str:
        """Qwen3 <think>...</think> 블록 제거"""
        if text is None:
            return ""
        text = re.sub(r"<think>[\s\S]*?</think>\s*", "", text)
        text = re.sub(r"</?think>\s*", "", text)
        return text.strip()

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
                    extra_body=self._NO_THINK,
                    max_tokens=8000,
                )
            except LengthFinishReasonError as e:
                response = e.completion
                usage = response.usage
                logger.warning(
                    "[CV-LLM] ⚠️ max_tokens 잘림 (temperature=%.1f) — "
                    "prompt=%d, completion=%d, total=%d",
                    self.temperature,
                    usage.prompt_tokens if usage else -1,
                    usage.completion_tokens if usage else -1,
                    usage.total_tokens if usage else -1,
                )

                # 장황 모드 재시도: temperature를 올려서 다른 생성 경로 유도
                retry_temp = 0.2
                for attempt in range(1, self._MAX_RETRIES_ON_LENGTH + 1):
                    logger.info(
                        "[CV-LLM] 🔄 재시도 %d/%d (temperature=%.1f)",
                        attempt, self._MAX_RETRIES_ON_LENGTH, retry_temp,
                    )
                    try:
                        response = self.client.beta.chat.completions.parse(
                            model=self.model,
                            messages=messages,
                            response_format=response_model,
                            temperature=retry_temp,
                            extra_body=self._NO_THINK,
                            max_tokens=8000,
                        )
                        # 재시도 성공
                        usage = response.usage
                        if usage:
                            logger.info(
                                "[CV-LLM] ✅ 재시도 성공 — prompt=%d, completion=%d, total=%d, finish=%s",
                                usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
                                response.choices[0].finish_reason,
                            )
                        parsed = response.choices[0].message.parsed
                        if parsed is not None:
                            return parsed
                        raw = self._strip_think(response.choices[0].message.content)
                        repaired = _repair_truncated_json(raw)
                        return response_model.model_validate(repaired)
                    except LengthFinishReasonError as retry_e:
                        logger.warning("[CV-LLM] ⚠️ 재시도 %d도 잘림", attempt)
                        response = retry_e.completion

                # 모든 재시도 실패 — 마지막 응답으로 JSON 복구 시도
                raw = self._strip_think(response.choices[0].message.content)
                logger.warning("[CV-LLM] 🔧 JSON 복구 시도 (output_len=%d chars)", len(raw))
                repaired = _repair_truncated_json(raw)
                return response_model.model_validate(repaired)
            usage = response.usage
            if usage:
                logger.info(
                    "[CV-LLM] 토큰 사용량 — prompt=%d, completion=%d, total=%d, finish=%s",
                    usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
                    response.choices[0].finish_reason,
                )
            parsed = response.choices[0].message.parsed
            if parsed is None:
                logger.warning("[CV-LLM] parsed 결과 None — 수동 JSON 파싱 시도")
                raw = self._strip_think(response.choices[0].message.content)
                repaired = _repair_truncated_json(raw)
                return response_model.model_validate(repaired)
            return parsed
        else:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                extra_body=self._NO_THINK,
            )
            usage = response.usage
            if usage:
                logger.info(
                    "[CV-LLM] 토큰 사용량 — prompt=%d, completion=%d, total=%d, finish=%s",
                    usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
                    response.choices[0].finish_reason,
                )
            return self._strip_think(response.choices[0].message.content)
