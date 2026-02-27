"""
임베딩 생성 서비스
RunPod Serverless를 통한 Qwen3-Embedding-0.6B 벡터 생성
"""

import logging

from services.runpod_client import embed_text_sync

logger = logging.getLogger("EmbeddingService")


class EmbeddingService:
    """임베딩 벡터 생성 서비스 (RunPod 기반)"""

    def __init__(self):
        self._loaded = True  # RunPod는 항상 사용 가능

    def load_manager(self):
        """RunPod 기반이므로 로컬 로딩 불필요"""
        logger.info("임베딩 서비스: RunPod Serverless 사용")

    def generate_embedding(self, text: str) -> list[float]:
        """
        document 텍스트로부터 임베딩 벡터 생성 (RunPod GPU)

        Args:
            text: 임베딩할 텍스트 (최대 8000자)

        Returns:
            1024차원 임베딩 벡터
        """
        try:
            truncated_text = text[:8000]
            embedding = embed_text_sync(truncated_text)
            return embedding
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            return [0.0] * 1024

    def is_loaded(self) -> bool:
        """RunPod 기반이므로 항상 True"""
        return True


# 싱글톤 인스턴스
embedding_service = EmbeddingService()
