"""
CV 파이프라인 서비스
RunPod Serverless GPU를 통한 도면 이미지 분석
"""

import base64
import logging
from typing import Optional, Dict, Any

import cv2
import numpy as np

from services.runpod_client import cv_inference_async

logger = logging.getLogger("CVService")


class CVService:
    """CV 파이프라인 관리 서비스 (RunPod 기반)"""

    def __init__(self):
        self._loaded = True  # RunPod는 항상 사용 가능

    def load_pipeline(self):
        """RunPod 기반이므로 로컬 로딩 불필요"""
        logger.info("CV 서비스: RunPod Serverless 사용")
        return self

    async def analyze_image_async(
        self,
        image: np.ndarray,
        filename: str,
        save_json: bool = True,
        save_visualization: bool = True,
    ) -> Dict[str, Any]:
        """
        이미지 분석 실행 (RunPod GPU)

        Args:
            image: OpenCV 이미지
            filename: 파일명
            save_json: JSON 저장 여부 (RunPod에서 처리)
            save_visualization: 시각화 저장 여부 (RunPod에서 처리)

        Returns:
            분석 결과 딕셔너리
        """
        logger.info(f"이미지 분석 시작 (RunPod): {filename}")

        # OpenCV 이미지 -> base64
        _, buffer = cv2.imencode('.png', image)
        image_b64 = base64.b64encode(buffer).decode('utf-8')

        # RunPod 호출
        results = await cv_inference_async(image_b64, filename)

        logger.info("이미지 분석 완료 (RunPod)!")
        return results

    def analyze_image(
        self,
        image: np.ndarray,
        filename: str,
        save_json: bool = True,
        save_visualization: bool = True,
    ) -> Dict[str, Any]:
        """
        동기 버전 (기존 코드 호환용)
        asyncio 이벤트 루프에서 비동기 호출
        """
        import asyncio

        logger.info(f"이미지 분석 시작 (RunPod, sync): {filename}")

        # OpenCV 이미지 -> base64
        _, buffer = cv2.imencode('.png', image)
        image_b64 = base64.b64encode(buffer).decode('utf-8')

        # worker thread에서 새 이벤트 루프로 비동기 호출
        results = asyncio.run(cv_inference_async(image_b64, filename))

        logger.info("이미지 분석 완료 (RunPod, sync)!")
        return results

    def get_topology_image_base64(self) -> Optional[str]:
        """RunPod 응답에서 topology 이미지 base64가 포함됨"""
        return None

    def is_loaded(self) -> bool:
        """RunPod 기반이므로 항상 True"""
        return True


# 싱글톤 인스턴스
cv_service = CVService()
