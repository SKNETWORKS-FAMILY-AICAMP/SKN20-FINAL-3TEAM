"""
모델 기반 추상 클래스
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import numpy as np
import torch


class BaseModel(ABC):
    """모든 추론 모델의 기반 추상 클래스"""

    def __init__(self, config):
        self.config = config
        self.model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    @abstractmethod
    def load_model(self) -> None:
        """모델 로드"""
        pass

    @abstractmethod
    def preprocess(self, image: np.ndarray) -> Any:
        """입력 이미지 전처리"""
        pass

    @abstractmethod
    def inference(self, preprocessed_input: Any) -> Any:
        """추론 실행"""
        pass

    @abstractmethod
    def postprocess(self, raw_output: Any, original_size: tuple) -> List[Dict]:
        """출력 후처리 - 표준 annotation 형식으로 변환"""
        pass

    def predict(self, image: np.ndarray) -> List[Dict]:
        """전체 예측 파이프라인"""
        original_size = (image.shape[1], image.shape[0])  # (width, height)
        preprocessed = self.preprocess(image)
        raw_output = self.inference(preprocessed)
        return self.postprocess(raw_output, original_size)
