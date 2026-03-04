"""
PostgreSQL pgvector 기반 벡터 검색 서비스
사내 평가 문서 검색을 위한 서비스
"""

import logging
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from CV.rag_system.config import RAGConfig

logger = logging.getLogger("PgVectorService")


class PgVectorService:
    """PostgreSQL pgvector 벡터 검색 서비스"""

    def __init__(self):
        self.config: Optional[RAGConfig] = None
        self._pool: Optional[ThreadedConnectionPool] = None

    def _get_pool(self) -> ThreadedConnectionPool:
        """커넥션 풀 획득 (lazy init)"""
        if self._pool is None:
            if self.config is None:
                self.config = RAGConfig()
            self._pool = ThreadedConnectionPool(
                minconn=1, maxconn=4,
                host=self.config.POSTGRES_HOST,
                port=self.config.POSTGRES_PORT,
                database=self.config.POSTGRES_DB,
                user=self.config.POSTGRES_USER,
                password=self.config.POSTGRES_PASSWORD,
            )
        return self._pool

    def search_internal_eval(self, query_embedding: List[float], k: int = 5) -> List[Dict]:
        """
        사내 평가 문서 검색 (PostgreSQL pgvector)

        Args:
            query_embedding: 쿼리 임베딩 벡터 (1024-dim)
            k: 반환할 결과 수

        Returns:
            [{'id': ..., 'document': ..., 'metadata': ..., 'distance': ...}, ...]
        """
        pool = self._get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # pgvector cosine distance 검색
                # embedding <=> query_embedding 은 cosine distance
                embedding_str = f"[{','.join(map(str, query_embedding))}]"

                cur.execute("""
                    SELECT
                        id,
                        keywords,
                        document,
                        embedding <=> %s::vector AS distance
                    FROM internal_eval
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (embedding_str, embedding_str, k))

                rows = cur.fetchall()

                results = []
                for row in rows:
                    results.append({
                        'id': str(row['id']),
                        'document': row['document'],
                        'metadata': {'keywords': row['keywords']} if row['keywords'] else {},
                        'distance': float(row['distance'])
                    })

                logger.info(f"pgvector 검색 완료: {len(results)}개 결과")
                return results

        except Exception as e:
            logger.error(f"pgvector 검색 실패: {e}")
            return []
        finally:
            pool.putconn(conn)

    def close(self):
        """연결 종료"""
        if self._pool:
            self._pool.closeall()

    def is_loaded(self) -> bool:
        """서비스 로드 여부 확인"""
        return self.config is not None


# 싱글톤 인스턴스
pgvector_service = PgVectorService()
