"""RAG 시스템 설정"""
from pydantic_settings import BaseSettings
from pathlib import Path

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

    # RAG 파라미터
    TOP_K: int = 5
    MAX_CONTEXT_LENGTH: int = 4000

    class Config:
        # python/.env 파일을 명시적으로 찾기
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        env_file_encoding = 'utf-8'
        extra = 'ignore'
