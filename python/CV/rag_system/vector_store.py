"""ChromaDB 기반 벡터 저장소"""
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional

class VectorStore:
    def __init__(self, db_path: str = "rag_data"):
        """
        ChromaDB 초기화

        Args:
            db_path: ChromaDB 저장 디렉토리
        """
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False)
        )

        # 컬렉션 생성
        self.evaluation_collection = self.client.get_or_create_collection(
            name="evaluation_docs",
            metadata={"description": "사내 평가 문서"}
        )

        self.topology_collection = self.client.get_or_create_collection(
            name="topology_analyses",
            metadata={"description": "도면 분석 결과"}
        )

    def insert_evaluation(self, doc_id: str, content: str,
                         embedding: List[float], metadata: dict = None):
        """사내 평가 문서 삽입"""
        self.evaluation_collection.add(
            ids=[doc_id],
            documents=[content],
            embeddings=[embedding],
            metadatas=[metadata] if metadata else None
        )

    def insert_topology(self, doc_id: str, content: str,
                       embedding: List[float], metadata: dict = None):
        """도면 분석 결과 삽입"""
        self.topology_collection.add(
            ids=[doc_id],
            documents=[content],
            embeddings=[embedding],
            metadatas=[metadata] if metadata else None
        )

    def search_evaluation(self, query_embedding: List[float], k: int = 5) -> List[Dict]:
        """
        사내 평가 문서 검색

        Args:
            query_embedding: 쿼리 임베딩 벡터 (512-dim)
            k: 반환할 결과 수

        Returns:
            [{'id': ..., 'document': ..., 'metadata': ..., 'distance': ...}, ...]
        """
        results = self.evaluation_collection.query(
            query_embeddings=[query_embedding],
            n_results=k
        )

        return self._format_results(results)

    def search_topology(self, query_embedding: List[float], k: int = 5,
                       where: dict = None) -> List[Dict]:
        """
        도면 분석 결과 검색

        Args:
            query_embedding: 쿼리 임베딩 벡터
            k: 반환할 결과 수
            where: 메타데이터 필터 (예: {"structure_type": "판상형"})

        Returns:
            검색 결과 리스트
        """
        results = self.topology_collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where
        )

        return self._format_results(results)

    def _format_results(self, results: dict) -> List[Dict]:
        """ChromaDB 결과 포맷 변환"""
        formatted = []
        for i in range(len(results['ids'][0])):
            formatted.append({
                'id': results['ids'][0][i],
                'document': results['documents'][0][i],
                'metadata': results['metadatas'][0][i] if results['metadatas'][0] else {},
                'distance': results['distances'][0][i]
            })
        return formatted
