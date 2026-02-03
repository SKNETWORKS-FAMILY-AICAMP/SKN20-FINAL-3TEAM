"""
RAG 시스템 서비스
평면도 분석 및 메타데이터 추출
"""

import logging
from typing import Optional, Dict, Any

from CV.rag_system.config import RAGConfig
from CV.rag_system.embeddings import EmbeddingManager
from CV.rag_system.vector_store import VectorStore
from CV.rag_system.llm_client import OpenAIClient
from CV.rag_system.schemas import FloorPlanAnalysis
from CV.rag_system.prompts import SYSTEM_PROMPT, build_analysis_prompt

logger = logging.getLogger("RAGService")


class RAGService:
    """RAG 시스템 관리 서비스"""
    
    def __init__(self):
        self.config: Optional[RAGConfig] = None
        self.embedding_manager: Optional[EmbeddingManager] = None
        self.vector_store: Optional[VectorStore] = None
        self.llm_client: Optional[OpenAIClient] = None
    
    def load_components(self):
        """RAG 컴포넌트를 lazy loading 방식으로 로드"""
        if self.llm_client is not None:
            return
        
        logger.info("RAG 컴포넌트 로딩 중...")
        
        try:
            self.config = RAGConfig()
            self.embedding_manager = EmbeddingManager(
                api_key=self.config.OPENAI_API_KEY,
                model="text-embedding-3-small"
            )
            self.vector_store = VectorStore(db_path="CV/rag_data")
            self.llm_client = OpenAIClient(
                api_key=self.config.OPENAI_API_KEY,
                model=self.config.OPENAI_MODEL,
                temperature=self.config.OPENAI_TEMPERATURE
            )
            logger.info("RAG 컴포넌트 로딩 완료!")
        except Exception as e:
            logger.error(f"RAG 컴포넌트 로딩 실패: {e}")
            raise
    
    def analyze_topology(self, topology_data: Dict[str, Any]) -> FloorPlanAnalysis:
        """
        topology 데이터로 RAG LLM 분석 실행
        
        Args:
            topology_data: topology_graph.json 데이터
            
        Returns:
            FloorPlanAnalysis 객체
        """
        self.load_components()
        
        # 쿼리 생성 및 임베딩
        stats = topology_data.get('statistics', {})
        query_text = f"{stats.get('structure_type', '혼합형')} 건축물 {stats.get('bay_count', 0)}Bay 침실 {stats.get('room_count', 0)}개"
        query_embedding = self.embedding_manager.embed_text(query_text)
        
        # RAG 검색
        rag_results = self.vector_store.search_evaluation(
            query_embedding=query_embedding,
            k=self.config.TOP_K
        )
        
        # 컨텍스트 포맷
        context_parts = [f"[참고 {i}]\n{result['document']}\n" for i, result in enumerate(rag_results, 1)]
        rag_context = "\n".join(context_parts)
        
        # LLM 분석 생성
        prompt = build_analysis_prompt(topology_data, rag_context)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        analysis_result = self.llm_client.query(
            messages=messages,
            response_model=FloorPlanAnalysis
        )
        
        return analysis_result
    
    def extract_metrics(self, analysis: FloorPlanAnalysis) -> Dict[str, Any]:
        """
        FloorPlanAnalysis에서 13개 지표 추출
        
        Args:
            analysis: LLM 분석 결과
            
        Returns:
            13개 지표 딕셔너리
        """
        # 거실 면적 비율 계산
        living_room = next((s for s in analysis.spaces if '거실' in s.space_name), None)
        living_room_ratio = living_room.area_ratio if living_room and living_room.area_ratio else 0.0
        
        # 주방 면적 비율 계산
        kitchen = next((s for s in analysis.spaces if '주방' in s.space_name), None)
        kitchen_ratio = kitchen.area_ratio if kitchen and kitchen.area_ratio else 0.0
        
        # 화장실 면적 비율 계산
        bathrooms = [s for s in analysis.spaces if '욕실' in s.space_name or '화장실' in s.space_name]
        bathroom_ratio = sum(s.area_ratio for s in bathrooms if s.area_ratio) if bathrooms else 0.0
        
        # 기타공간/특화공간 유무 확인
        space_types = set([s.space_type for s in analysis.spaces])
        has_etc_space = "기타공간" in space_types
        has_special_space = "특화공간" in space_types
        
        # 적합성 등급
        compliance_grade = analysis.compliance.overall_grade if analysis.compliance else "미평가"
        
        return {
            "windowless_ratio": round(analysis.windowless_ratio / 100.0, 4) if analysis.windowless_ratio > 1 else round(analysis.windowless_ratio, 4),
            "has_special_space": has_special_space,
            "bay_count": analysis.bay_count,
            "balcony_ratio": round(analysis.balcony_ratio / 100.0, 4) if analysis.balcony_ratio > 1 else round(analysis.balcony_ratio, 4),
            "living_room_ratio": round(living_room_ratio, 4),
            "bathroom_ratio": round(bathroom_ratio, 4),
            "kitchen_ratio": round(kitchen_ratio, 4),
            "room_count": analysis.room_count,
            "compliance_grade": compliance_grade,
            "ventilation_quality": analysis.ventilation_quality,
            "has_etc_space": has_etc_space,
            "structure_type": analysis.structure_type,
            "bathroom_count": analysis.bathroom_count
        }
    
    def is_loaded(self) -> bool:
        """컴포넌트 로드 여부 확인"""
        return self.llm_client is not None


# 싱글톤 인스턴스
rag_service = RAGService()
