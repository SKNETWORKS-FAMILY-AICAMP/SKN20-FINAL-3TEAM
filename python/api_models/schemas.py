"""
Pydantic 모델 정의
FastAPI 요청/응답 스키마
"""

from typing import Dict, Any
from pydantic import BaseModel


class AnalysisResult(BaseModel):
    """분석 결과 (13개 지표 + LLM 분석 document)"""
    # 13개 지표
    windowless_ratio: float
    has_special_space: bool
    bay_count: int
    balcony_ratio: float
    living_room_ratio: float
    bathroom_ratio: float
    kitchen_ratio: float
    room_count: int
    compliance_grade: str
    ventilation_quality: str
    has_etc_space: bool
    structure_type: str
    bathroom_count: int
    # LLM 분석 결과 (to_natural_language() 출력)
    document: str


class AnalyzeResponse(BaseModel):
    """도면 분석 응답 모델 - Spring Boot와 매핑"""
    topology_json: str  # 1번: topology_graph.json (문자열)
    topology_image_url: str  # 2번: topology 시각화 (base64 이미지)
    llm_analysis_json: str  # 3번: llm_analysis.json (FloorPlanAnalysis 전체)


class SaveRequest(BaseModel):
    """저장 요청 모델 - Spring Boot에서 llm_analysis_json (3번) 전송"""
    llm_analysis_json: str  # llm_analysis.json 문자열 (FloorPlanAnalysis)


class SaveResponse(BaseModel):
    """저장 응답 모델 - Spring Boot로 4번 데이터 전송"""
    document_id: str
    metadata: Dict[str, Any]  # 13개 지표
    document: str  # 분석 설명
    embedding: list[float]  # 전체 임베딩 벡터 (1536차원)


class ChatRequest(BaseModel):
    """챗봇 요청 모델"""
    email: str
    question: str


class ChatResponse(BaseModel):
    """챗봇 응답 모델"""
    summaryTitle: str
    answer: str


# 의도 분류 관련 스키마

class IntentClassification(BaseModel):
    """의도 분류 결과 (FLOORPLAN_SEARCH 또는 REGULATION_SEARCH)"""
    intent_type: str  # "FLOORPLAN_SEARCH" | "REGULATION_SEARCH"
    confidence: float  # 0.0 - 1.0
    extracted_metadata: Dict[str, Any]
    reasoning: str
