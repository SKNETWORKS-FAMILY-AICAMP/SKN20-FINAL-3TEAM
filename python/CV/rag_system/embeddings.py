"""임베딩 생성 (Qwen3-Embedding-0.6B, 1024차원)"""
import logging
from typing import List

from sentence_transformers import SentenceTransformer

logger = logging.getLogger("EmbeddingManager")


class EmbeddingManager:
    """Qwen3-Embedding-0.6B 기반 임베딩 매니저 (싱글톤 모델 로딩)"""

    _model: SentenceTransformer = None

    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B"):
        self.model_name = model_name
        self.dimensions = 1024

        if EmbeddingManager._model is None:
            logger.info(f"Qwen3 임베딩 모델 로딩: {model_name}")
            EmbeddingManager._model = SentenceTransformer(model_name)
            logger.info("Qwen3 임베딩 모델 로딩 완료")

        self.model = EmbeddingManager._model

    def embed_text(self, text: str) -> List[float]:
        """단일 텍스트 임베딩"""
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """배치 임베딩"""
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return [e.tolist() for e in embeddings]

    def embed_space_document(self, space_data: dict) -> List[float]:
        """
        topology.json의 공간 노드를 임베딩

        Args:
            space_data: nodes[i] 형식의 공간 데이터

        Returns:
            1024-dim 임베딩 벡터
        """
        text_parts = [
            f"공간명: {space_data['label']}",
            f"타입: {space_data['space_type']}",
        ]

        if space_data.get('contains', {}).get('objects'):
            objects = [obj['category_name'] for obj in space_data['contains']['objects']]
            text_parts.append(f"포함 객체: {', '.join(objects)}")

        if space_data.get('contains', {}).get('ocr_labels'):
            text_parts.append(f"라벨: {', '.join(space_data['contains']['ocr_labels'])}")

        full_text = "\n".join(text_parts)
        return self.embed_text(full_text)
