"""
CV 도면 분석 에이전트
이미지 → CV 추론 → LLM 분석 → 메트릭 추출 → document 생성 → 임베딩 생성
"""

import json
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from agents.base import BaseAgent
from api_models.schemas import CVAnalysisResult
from api_utils.image_utils import image_to_base64

logger = logging.getLogger("CVAnalysisAgent")


class CVAnalysisAgent(BaseAgent):
    """CV 도면 분석 에이전트 — 이미지 → 분석 결과 일체"""

    @property
    def name(self) -> str:
        return "cv_analysis"

    def __init__(self):
        self._cv_service = None
        self._rag_service = None
        self._embedding_service = None

    def _load_components(self):
        """기존 싱글톤 서비스 참조 (lazy loading)"""
        if self._cv_service is not None:
            return
        from services.cv_service import cv_service
        from services.rag_service import rag_service
        from services.embedding_service import embedding_service
        self._cv_service = cv_service
        self._rag_service = rag_service
        self._embedding_service = embedding_service

    def execute(
        self,
        image: np.ndarray,
        filename: str,
        mode: str = "full",
    ) -> CVAnalysisResult:
        """
        도면 이미지 분석 실행

        Args:
            image: OpenCV 이미지 (np.ndarray)
            filename: 원본 파일명
            mode:
                "preview" — 단계 1,2,3만 실행 (/analyze 미리보기용)
                "full"    — 단계 1~6 모두 실행 (/orchestrate 이미지 모드)

        Returns:
            CVAnalysisResult
        """
        self._load_components()

        # ===== 공통 (preview + full) =====

        # 1. CV 추론
        logger.info(f"[{mode}] CV 추론 시작: {filename}")
        results = self._cv_service.analyze_image(
            image=image,
            filename=filename,
            save_json=True,
            save_visualization=True,
        )
        topology_data = results.get("topology_graph", {})

        # 2. topology 이미지 base64
        topology_image_path = self._cv_service.get_topology_image_path(filename)
        if topology_image_path.exists():
            topo_img = cv2.imread(str(topology_image_path))
            topology_image_base64 = f"data:image/png;base64,{image_to_base64(topo_img)}"
        else:
            logger.warning(f"Topology 이미지 없음: {topology_image_path}")
            topology_image_base64 = ""

        # 3. LLM 분석 (RAG)
        logger.info(f"[{mode}] RAG LLM 분석 시작...")
        llm_analysis = self._rag_service.analyze_topology(topology_data)
        llm_analysis_dict = (
            llm_analysis.model_dump()
            if hasattr(llm_analysis, "model_dump")
            else llm_analysis.dict()
        )

        # 3-1. llm_analysis.json 파일 저장
        try:
            output_dir = self._cv_service.pipeline.config.OUTPUT_PATH / Path(filename).stem
            output_dir.mkdir(parents=True, exist_ok=True)
            llm_analysis_path = output_dir / "llm_analysis.json"
            with open(llm_analysis_path, "w", encoding="utf-8") as f:
                json.dump(llm_analysis_dict, f, ensure_ascii=False, indent=2)
            logger.info(f"llm_analysis.json 저장 완료: {llm_analysis_path}")
        except Exception as save_err:
            logger.error(f"llm_analysis.json 저장 실패: {save_err}")

        # ===== preview: 여기서 종료 =====
        if mode == "preview":
            return CVAnalysisResult(
                topology_data=topology_data,
                topology_image_base64=topology_image_base64,
                llm_analysis=llm_analysis_dict,
                metrics={},
                document="",
                embedding=[],
            )

        # ===== full: 메트릭 + document + 임베딩까지 =====

        # 4. 메트릭 추출
        logger.info("[full] 메트릭 추출...")
        metrics = self._rag_service.extract_metrics(llm_analysis)

        # 5. document 생성
        logger.info("[full] document 생성...")
        document = llm_analysis.to_natural_language()

        # 6. 임베딩 생성
        logger.info("[full] 임베딩 생성...")
        embedding = self._embedding_service.generate_embedding(document)

        logger.info(f"[full] CV 분석 완료: {filename}")
        return CVAnalysisResult(
            topology_data=topology_data,
            topology_image_base64=topology_image_base64,
            llm_analysis=llm_analysis_dict,
            metrics=metrics,
            document=document,
            embedding=embedding,
        )

    def is_loaded(self) -> bool:
        return self._cv_service is not None
