"""Pydantic 스키마 정의"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class NonCompliantItem(BaseModel):
    """부적합 항목"""
    category: str = Field(description="평가 카테고리 (채광/환기/가족융화/수납)")
    item: str = Field(description="부적합 항목")
    reason: str = Field(description="부적합 사유")
    recommendation: str = Field(description="개선 권고사항")


class ComplianceEvaluation(BaseModel):
    """사내 평가 기준 적합성 평가"""
    overall_grade: str = Field(description="종합 등급 (최우수/우수/보통/미흡/불합격)")
    compliant_items: List[str] = Field(description="적합 항목 목록", default=[])
    non_compliant_items: List[NonCompliantItem] = Field(description="부적합 항목 목록", default=[])
    summary: str = Field(description="적합성 평가 요약")


class SpaceAnalysis(BaseModel):
    """개별 공간 분석 결과"""
    space_name: str = Field(description="공간명 (예: 거실, 침실1)")
    space_type: str = Field(description="공간 타입 (예: 공통공간, 개인공간)")
    area_m2: Optional[float] = Field(description="면적(m²)", default=None)
    area_ratio: Optional[float] = Field(description="면적 비율 (%)", default=None)
    has_window: bool = Field(description="창문 유무", default=True)
    features: List[str] = Field(description="주요 특징", default=[])
    connected_spaces: List[str] = Field(description="연결된 공간", default=[])
    evaluation_comment: str = Field(description="설계 평가 코멘트")

class FloorPlanAnalysis(BaseModel):
    """전체 평면도 분석 결과"""
    image_name: str = Field(description="이미지 파일명")
    structure_type: str = Field(description="건축물 유형 (판상형/타워형/혼합형)")
    bay_count: int = Field(description="Bay 수")
    total_spaces: int = Field(description="전체 공간 수")
    room_count: int = Field(description="침실 수")
    bathroom_count: int = Field(description="욕실 수")
    balcony_ratio: float = Field(description="발코니 비율 (%)")
    windowless_ratio: float = Field(description="창 없는 공간 비율 (%)")
    ventilation_quality: str = Field(description="환기 품질 (우수/양호/보통/미흡)")

    summary: str = Field(description="전체 평면도 요약")
    spaces: List[SpaceAnalysis] = Field(description="공간별 분석")

    design_evaluation: Optional[Dict[str, str]] = Field(description="설계 평가 (채광, 환기, 가족융화, 수납)", default=None)
    recommendations: Optional[List[str]] = Field(description="개선 제안", default=None)

    # 사내 평가 기준 적합성 평가
    compliance: Optional[ComplianceEvaluation] = Field(description="사내 평가 기준 적합성 평가", default=None)

    def to_natural_language(self) -> str:
        """
        의미적 내용만 자연어로 변환 (벡터 임베딩용)

        숫자/비율은 메타데이터로 필터링하고,
        의미적 평가 내용만 임베딩하여 유사도 검색에 활용

        Returns:
            의미적 내용 (summary + 평가 + 공간별 코멘트 + 적합성 평가)
        """
        nl_parts = []

        # 1. 전체 요약 (의미적)
        nl_parts.append(self.summary)

        # 2. 설계 평가 (의미적)
        if self.design_evaluation:
            eval_sentences = [f"{k}은(는) {v}" for k, v in self.design_evaluation.items()]
            nl_parts.append(". ".join(eval_sentences) + ".")

        # 3. 공간별 평가 코멘트 (의미적)
        for space in self.spaces:
            nl_parts.append(f"{space.space_name}: {space.evaluation_comment}")

        # 4. 적합성 평가 (의미적)
        if self.compliance:
            nl_parts.append(f"사내 기준 적합성: {self.compliance.overall_grade}. {self.compliance.summary}")
            if self.compliance.non_compliant_items:
                for item in self.compliance.non_compliant_items:
                    nl_parts.append(f"부적합({item.category}): {item.item} - {item.recommendation}")

        return " ".join(nl_parts)

class RAGQuery(BaseModel):
    """RAG 쿼리 입력"""
    query: str = Field(description="사용자 질문")
    topology_file: Optional[str] = Field(description="topology.json 경로", default=None)
