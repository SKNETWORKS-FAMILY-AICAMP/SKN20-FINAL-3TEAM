"""RAG 시스템 설정"""
import logging
from pydantic_settings import BaseSettings
from pathlib import Path

logger = logging.getLogger("RAGConfig")

# vLLM 헬스체크 결과 캐시 (프로세스 당 1회만 실행)
_vllm_health_checked = False
_vllm_is_available = False


def _check_vllm_health(base_url: str, timeout: float = 3.0) -> bool:
    """vLLM 서버 헬스체크 (최초 1회)"""
    global _vllm_health_checked, _vllm_is_available
    if _vllm_health_checked:
        return _vllm_is_available

    _vllm_health_checked = True

    if not base_url:
        _vllm_is_available = False
        return False

    import httpx
    # /v1 경로 제거하여 베이스 URL 추출
    health_url = base_url.rstrip("/").removesuffix("/v1") + "/health"
    try:
        resp = httpx.get(health_url, timeout=timeout)
        _vllm_is_available = resp.status_code == 200
    except Exception:
        # /health 실패 시 /v1/models 시도
        try:
            models_url = base_url.rstrip("/") + "/models"
            resp = httpx.get(models_url, timeout=timeout)
            _vllm_is_available = resp.status_code == 200
        except Exception:
            _vllm_is_available = False

    return _vllm_is_available


class RAGConfig(BaseSettings):
    # Embedding 모델 (Qwen3-Embedding-0.6B)
    EMBEDDING_MODEL: str = "qwen3-embedding-0.6b"
    EMBEDDING_DIM: int = 1024

    # PostgreSQL pgvector 설정
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "arae"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "1234"

    # LLM 백엔드 선택: "openai" 또는 "vllm"
    LLM_BACKEND: str = "openai"

    # OpenAI 설정 (LLM_BACKEND=openai)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.1

    # vLLM 설정 (LLM_BACKEND=vllm)
    VLLM_BASE_URL: str = ""
    VLLM_MODEL_NAME: str = ""
    VLLM_SEARCH_MODEL_NAME: str = ""

    # RAG 파라미터
    TOP_K: int = 5
    MAX_CONTEXT_LENGTH: int = 4000

    def model_post_init(self, __context) -> None:
        """설정 로드 후 vLLM 헬스체크 → 실패 시 OpenAI로 자동 전환"""
        if self.LLM_BACKEND == "vllm":
            if _check_vllm_health(self.VLLM_BASE_URL):
                logger.info("✅ vLLM 서버 연결 확인 (%s) → vllm 백엔드 사용", self.VLLM_BASE_URL)
            else:
                logger.warning(
                    "⚠️ vLLM 서버 연결 실패 (%s) → OpenAI 백엔드로 자동 전환",
                    self.VLLM_BASE_URL,
                )
                self.LLM_BACKEND = "openai"

    class Config:
        # python/.env 파일을 명시적으로 찾기
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        env_file_encoding = 'utf-8'
        extra = 'ignore'
