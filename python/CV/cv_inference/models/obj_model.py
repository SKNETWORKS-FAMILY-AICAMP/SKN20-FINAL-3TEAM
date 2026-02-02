"""
OBJ 모델 래퍼 (YOLOv5 객체 인식)
- 5개 클래스: 변기, 세면대, 싱크대, 욕조, 가스레인지
"""

import torch
import cv2
import numpy as np
from typing import List, Dict, Any
from pathlib import Path

from .base_model import BaseModel


class OBJModel(BaseModel):
    """객체 인식 모델 (YOLOv5)"""

    def __init__(self, model_config, inference_config):
        super().__init__(model_config)
        self.inference_config = inference_config
        self.yolo_path = inference_config.YOLO_PATH

    def load_model(self) -> None:
        """YOLOv5 모델 로드"""
        self.model = torch.hub.load(
            str(self.yolo_path),
            'custom',
            str(self.config.model_path),
            source='local',
            _verbose=False
        )
        self.model.conf = self.config.conf_threshold
        self.model.iou = self.config.iou_threshold
        self.model.to(self.device)

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """이미지 전처리 - RGB 변환 및 리사이즈"""
        # BGR -> RGB
        rgb_img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        bh, bw = rgb_img.shape[:2]

        # 32의 배수로 크롭
        cropped_img = rgb_img[:bh // 32 * 32, :bw // 32 * 32, :]

        # 620x436으로 리사이즈
        w, h = self.config.input_size
        resized_img = cv2.resize(cropped_img, dsize=(w, h), interpolation=cv2.INTER_AREA)

        return resized_img

    def inference(self, preprocessed_input: np.ndarray) -> Any:
        """YOLOv5 추론"""
        results = self.model(preprocessed_input)
        return results.pandas().xyxy[0]

    def postprocess(self, raw_output: Any, original_size: tuple) -> List[Dict]:
        """bbox를 원본 크기로 복원하고 표준 형식으로 변환"""
        annotations = []
        scale_factor = self.inference_config.RESIZE_FACTOR  # 8

        for idx, row in raw_output.iterrows():
            # 좌표 복원 (*8)
            xmin = int(row['xmin'] * scale_factor)
            ymin = int(row['ymin'] * scale_factor)
            xmax = int(row['xmax'] * scale_factor)
            ymax = int(row['ymax'] * scale_factor)

            # 클래스 ID 매핑
            yolo_class = int(row['class'])
            category_id = self.inference_config.OBJ_CLASS_MAP.get(yolo_class, 4)
            category_name = self.inference_config.CATEGORIES.get(category_id, "unknown")

            annotation = {
                "id": idx,
                "category_id": category_id,
                "category_name": category_name,
                "bbox": [xmin, ymin, xmax - xmin, ymax - ymin],  # [x, y, w, h]
                "segmentation": [],
                "area": (xmax - xmin) * (ymax - ymin),
                "confidence": float(row['confidence']),
                "iscrowd": 0,
                "attributes": {
                    "occluded": False,
                    "rotation": 0.0
                }
            }
            annotations.append(annotation)

        return annotations
