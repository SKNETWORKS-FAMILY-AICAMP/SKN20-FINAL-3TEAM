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
    topology_json: str  # 1번: topology json string
    topology_image_url: str  # 2번: base64 이미지
    assessment_json: str  # 3번: topology_graph.json 전체
    
    # 13개 분석 지표 (flat 구조)
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
    analysis_description: str  # LLM 분석 결과 문서
    embedding: list[float]  # 임베딩 벡터 (1536차원)


class SaveRequest(BaseModel):
    """저장 요청 모델 - Spring Boot에서 assessmentJson (3번) 전송"""
    assessment_json: str  # topology_graph.json 문자열


class SaveResponse(BaseModel):
    """저장 응답 모델 - Spring Boot로 4번 데이터 전송"""
    document_id: str
    metadata: Dict[str, Any]  # 13개 지표
    document: str  # 분석 설명
    embedding: list[float]  # 전체 임베딩 벡터 (1536차원)
