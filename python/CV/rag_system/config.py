"""RAG 시스템 설정"""
from pydantic_settings import BaseSettings
from pathlib import Path

class RAGConfig(BaseSettings):
    # Embedding 모델 (OpenAI)
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 512

    # Vector DB (ChromaDB)
    CHROMA_DB_PATH: str = "rag_data"

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

