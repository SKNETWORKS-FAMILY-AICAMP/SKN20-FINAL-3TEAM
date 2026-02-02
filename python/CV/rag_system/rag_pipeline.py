"""간단한 순차 RAG 파이프라인"""
import json
from typing import List, Dict

from .config import RAGConfig
from .embeddings import EmbeddingManager
from .vector_store import VectorStore
from .llm_client import OpenAIClient
from .schemas import FloorPlanAnalysis
from .prompts import SYSTEM_PROMPT, build_analysis_prompt

class RAGPipeline:
    def __init__(self, config: RAGConfig):
        self.config = config

        # 컴포넌트 초기화
        self.embedding_manager = EmbeddingManager(
            api_key=config.OPENAI_API_KEY,
            model="text-embedding-3-small"
        )
        self.vector_store = VectorStore(db_path="rag_data")
        self.llm_client = OpenAIClient(
            api_key=config.OPENAI_API_KEY,
            model=config.OPENAI_MODEL,
            temperature=config.OPENAI_TEMPERATURE
        )

    def index_evaluation_document(self, doc_path: str = "rag_data/사내_평가_문서.json"):
        """사내 평가 문서를 벡터 DB에 색인"""
        with open(doc_path, 'r', encoding='utf-8') as f:
            doc = json.load(f)

        chunks = doc.get('chunks_for_embedding', [])
        print(f"Indexing {len(chunks)} chunks from evaluation document...")

        # 배치 임베딩
        texts = [chunk['content'] for chunk in chunks]
        embeddings = self.embedding_manager.embed_batch(texts)

        for chunk, embedding in zip(chunks, embeddings):
            # ChromaDB 메타데이터는 리스트를 지원하지 않으므로 문자열로 변환
            keywords = chunk.get('keywords', [])
            keywords_str = ', '.join(keywords) if isinstance(keywords, list) else str(keywords)

            self.vector_store.insert_evaluation(
                doc_id=chunk['chunk_id'],
                content=chunk['content'],
                embedding=embedding,
                metadata={
                    'section_ref': chunk.get('section_ref', ''),
                    'keywords': keywords_str
                }
            )

        print("Evaluation document indexed successfully.")

    def analyze_topology(self, topology_path: str) -> FloorPlanAnalysis:
        """
        topology.json 분석 (순차 실행)

        Flow:
        1. topology.json 로드
        2. 쿼리 생성 및 임베딩
        3. RAG 검색
        4. LLM 분석 생성
        5. 결과 색인
        """
        # 1. topology.json 로드
        with open(topology_path, 'r', encoding='utf-8') as f:
            topology_data = json.load(f)

        # 2. 쿼리 생성 및 임베딩
        stats = topology_data.get('statistics', {})
        query_text = f"{stats.get('structure_type', '혼합형')} 건축물 {stats.get('bay_count', 0)}Bay 침실 {stats.get('room_count', 0)}개"
        query_embedding = self.embedding_manager.embed_text(query_text)

        # 3. RAG 검색
        rag_results = self.vector_store.search_evaluation(
            query_embedding=query_embedding,
            k=self.config.TOP_K
        )

        # 컨텍스트 포맷
        context_parts = [f"[참고 {i}]\n{result['document']}\n" for i, result in enumerate(rag_results, 1)]
        rag_context = "\n".join(context_parts)

        # 4. LLM 분석 생성
        prompt = build_analysis_prompt(topology_data, rag_context)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        analysis_result = self.llm_client.query(
            messages=messages,
            response_model=FloorPlanAnalysis
        )

        # 5. 결과 색인
        self._index_analysis(topology_data, analysis_result)

        return analysis_result

    def _index_analysis(self, topology_data: dict, analysis: FloorPlanAnalysis):
        """분석 결과를 벡터 DB에 색인 (자연어 변환)"""
        image_name = topology_data['image_info']['file_name']

        # 거실 면적 비율 계산
        living_room = next((s for s in analysis.spaces if '거실' in s.space_name), None)
        living_room_ratio = living_room.area_ratio if living_room and living_room.area_ratio else 0.0

        # 주방 면적 비율 계산
        kitchen = next((s for s in analysis.spaces if '주방' in s.space_name), None)
        kitchen_ratio = kitchen.area_ratio if kitchen and kitchen.area_ratio else 0.0

        # 화장실 면적 비율 계산 (욕실/화장실 합산)
        bathrooms = [s for s in analysis.spaces if '욕실' in s.space_name or '화장실' in s.space_name]
        bathroom_ratio = sum(s.area_ratio for s in bathrooms if s.area_ratio) if bathrooms else 0.0

        # 기타공간/특화공간 유무 확인
        space_types = set([s.space_type for s in analysis.spaces])
        has_etc_space = "기타공간" in space_types
        has_special_space = "특화공간" in space_types

        # 적합성 등급
        compliance_grade = analysis.compliance.overall_grade if analysis.compliance else "미평가"

        # Natural Language 문서만 저장 (의미적 내용)
        nl_text = analysis.to_natural_language()
        nl_embedding = self.embedding_manager.embed_text(nl_text)
        self.vector_store.insert_topology(
            doc_id=image_name,
            content=nl_text,
            embedding=nl_embedding,
            metadata={
                'image_name': image_name,
                'structure_type': analysis.structure_type,
                'bay_count': analysis.bay_count,
                'room_count': analysis.room_count,
                'bathroom_count': analysis.bathroom_count,
                'living_room_ratio': living_room_ratio,
                'kitchen_ratio': kitchen_ratio,
                'bathroom_ratio': bathroom_ratio,
                'balcony_ratio': analysis.balcony_ratio,
                'windowless_ratio': analysis.windowless_ratio,
                'ventilation_quality': analysis.ventilation_quality,
                'has_etc_space': has_etc_space,
                'has_special_space': has_special_space,
                'compliance_grade': compliance_grade
            }
        )

        print(f"Indexed {image_name}")

    def save_analysis_json(self, analysis: FloorPlanAnalysis, output_path: str):
        """분석 결과를 JSON 파일로 저장"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis.model_dump(), f, ensure_ascii=False, indent=2)

        print(f"Analysis saved to {output_path}")
