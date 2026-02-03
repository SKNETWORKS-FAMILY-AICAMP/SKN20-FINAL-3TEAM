"""
CV 파이프라인 서비스
도면 이미지 분석 및 topology 생성
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

import cv2
import numpy as np

from CV.cv_inference.pipeline import InferencePipeline
from CV.cv_inference.config import InferenceConfig

logger = logging.getLogger("CVService")


class CVService:
    """CV 파이프라인 관리 서비스"""
    
    def __init__(self):
        self.pipeline: Optional[InferencePipeline] = None
        
    def load_pipeline(self):
        """CV 파이프라인을 lazy loading 방식으로 로드"""
        if self.pipeline is not None:
            return self.pipeline
        
        logger.info("=" * 60)
        logger.info("첫 요청 감지 - CV 모델 로딩 중...")
        logger.info("=" * 60)
        
        try:
            config = InferenceConfig()
            config.OUTPUT_PATH = Path("./temp_output")
            config.OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
            
            self.pipeline = InferencePipeline(config)
            self.pipeline.load_models()
            
            logger.info("CV 모델 로딩 완료!")
            return self.pipeline
        except Exception as e:
            logger.error(f"CV 모델 로딩 실패: {e}")
            raise
    
    def analyze_image(
        self,
        image: np.ndarray,
        filename: str,
        save_json: bool = True,
        save_visualization: bool = True
    ) -> Dict[str, Any]:
        """
        이미지 분석 실행
        
        Args:
            image: OpenCV 이미지
            filename: 파일명
            save_json: JSON 저장 여부
            save_visualization: 시각화 저장 여부
            
        Returns:
            분석 결과 딕셔너리
        """
        pipeline = self.load_pipeline()
        
        # 임시 파일로 저장
        temp_dir = Path("./temp_input")
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / filename
        cv2.imwrite(str(temp_path), image)
        
        logger.info(f"이미지 분석 시작: {filename}")
        
        # CV 파이프라인 실행
        results = pipeline.run(
            temp_path,
            save_json=save_json,
            save_visualization=save_visualization
        )
        
        # 임시 파일 정리
        temp_path.unlink(missing_ok=True)
        
        logger.info("이미지 분석 완료!")
        return results
    
    def get_topology_image_path(self, filename: str) -> Path:
        """topology 이미지 경로 반환"""
        if self.pipeline is None:
            raise RuntimeError("파이프라인이 로드되지 않았습니다.")
        
        file_stem = Path(filename).stem
        return self.pipeline.config.OUTPUT_PATH / file_stem / "topology_result.png"
    
    def is_loaded(self) -> bool:
        """파이프라인 로드 여부 확인"""
        return self.pipeline is not None


# 싱글톤 인스턴스
cv_service = CVService()
