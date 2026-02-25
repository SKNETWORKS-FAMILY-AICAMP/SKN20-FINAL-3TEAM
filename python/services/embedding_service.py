"""
임베딩 생성 서비스
OpenAI Embedding API를 사용한 벡터 생성
"""

import logging
from typing import Optional

from CV.rag_system.embeddings import EmbeddingManager
from CV.rag_system.config import RAGConfig

logger = logging.getLogger("EmbeddingService")


class EmbeddingService:
    """임베딩 벡터 생성 서비스"""
    
    def __init__(self):
        self.embedding_manager: Optional[EmbeddingManager] = None
        self.config: Optional[RAGConfig] = None
    
    def load_manager(self):
        """임베딩 매니저 lazy loading"""
        if self.embedding_manager is not None:
            return
        
        logger.info("임베딩 매니저 로딩 중...")
        try:
            self.config = RAGConfig()
            self.embedding_manager = EmbeddingManager(
                api_key=self.config.OPENAI_API_KEY,
                model="text-embedding-3-small"
            )
            logger.info("임베딩 매니저 로딩 완료!")
        except Exception as e:
            logger.error(f"임베딩 매니저 로딩 실패: {e}")
            raise
    
    def generate_embedding(self, text: str) -> list[float]:
        """
        document 텍스트로부터 임베딩 벡터 생성
        
        Args:
            text: 임베딩할 텍스트 (최대 8000자)
            
        Returns:
            1536차원 임베딩 벡터
        """
        self.load_manager()
        
        try:
            # 토큰 제한 고려하여 잘라냄
            truncated_text = text[:8000]
            embedding = self.embedding_manager.embed_text(truncated_text)
            return embedding
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            # 실패 시 0 벡터 반환
            return [0.0] * 1536
    
    def is_loaded(self) -> bool:
        """매니저 로드 여부 확인"""
        return self.embedding_manager is not None


# 싱글톤 인스턴스
embedding_service = EmbeddingService()
