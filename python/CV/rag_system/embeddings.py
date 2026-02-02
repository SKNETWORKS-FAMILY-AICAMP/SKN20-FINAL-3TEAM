"""임베딩 생성 (OpenAI text-embedding-3-small)"""
from openai import OpenAI
from typing import List

class EmbeddingManager:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.dimensions = 512  # text-embedding-3-small 기본 차원

    def embed_text(self, text: str) -> List[float]:
        """단일 텍스트 임베딩"""
        response = self.client.embeddings.create(
            input=text,
            model=self.model,
            dimensions=self.dimensions
        )
        return response.data[0].embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """배치 임베딩 (최대 2048개)"""
        response = self.client.embeddings.create(
            input=texts,
            model=self.model,
            dimensions=self.dimensions
        )
        return [data.embedding for data in response.data]

    def embed_space_document(self, space_data: dict) -> List[float]:
        """
        topology.json의 공간 노드를 임베딩

        Args:
            space_data: nodes[i] 형식의 공간 데이터

        Returns:
            512-dim 임베딩 벡터
        """
        # 공간 정보를 자연어로 변환
        text_parts = [
            f"공간명: {space_data['label']}",
            f"타입: {space_data['space_type']}",
        ]

        # 포함된 객체 추가
        if space_data.get('contains', {}).get('objects'):
            objects = [obj['category_name'] for obj in space_data['contains']['objects']]
            text_parts.append(f"포함 객체: {', '.join(objects)}")

        # OCR 라벨 추가
        if space_data.get('contains', {}).get('ocr_labels'):
            text_parts.append(f"라벨: {', '.join(space_data['contains']['ocr_labels'])}")

        full_text = "\n".join(text_parts)
        return self.embed_text(full_text)
