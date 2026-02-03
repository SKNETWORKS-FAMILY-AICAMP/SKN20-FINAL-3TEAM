"""RAG 시스템 설정"""
from pydantic_settings import BaseSettings
from pathlib import Path

class RAGConfig(BaseSettings):
    # Embedding 모델 (OpenAI)
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 512

    # PostgreSQL pgvector 설정
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "arae"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "1234"

    # LLM
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.1

    # RAG 파라미터
    TOP_K: int = 5
    MAX_CONTEXT_LENGTH: int = 4000

    class Config:
        # python/.env 파일을 명시적으로 찾기
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        env_file_encoding = 'utf-8'

