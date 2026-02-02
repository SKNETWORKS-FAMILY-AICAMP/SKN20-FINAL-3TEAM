"""
STR 모델 래퍼 (DeepLabV3+ 구조 분석)
- 출력: 출입문, 창호, 벽체
"""

import torch
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple
import albumentations as album

from .base_model import BaseModel


class STRModel(BaseModel):
    """구조 분석 모델 (DeepLabV3+)"""

    def __init__(self, model_config, inference_config):
        super().__init__(model_config)
        self.inference_config = inference_config

    def load_model(self) -> None:
        """DeepLabV3+ 모델 로드"""
        self.model = torch.load(
            str(self.config.model_path),
            map_location=self.device,
            weights_only=False
        )
        self.model = self.model.to(self.device)
        self.model.eval()

    def preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int]]:
        """이미지 전처리"""
        rgb_img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        bh, bw = rgb_img.shape[:2]

        # 이미지 방향에 따른 크기 설정
        if bh > bw:
            w, h = 436, 620
            fw, fh = 448, 640
        else:
            w, h = 620, 436
            fw, fh = 640, 448

        # 32의 배수로 크롭
        cropped_img = rgb_img[:bh // 32 * 32, :bw // 32 * 32, :]

        # 리사이즈
        resized_img = cv2.resize(cropped_img, dsize=(w, h), interpolation=cv2.INTER_AREA)

        # 패딩된 캔버스에 배치
        rh, rw = resized_img.shape[:2]
        img = (np.ones((fh, fw, 3)) * 255).astype(np.uint8)
        img[:rh, :rw, :] = resized_img

        # Augmentation (패딩)
        transform = album.Compose([
            album.PadIfNeeded(min_height=448, min_width=640, always_apply=True, border_mode=0)
        ])
        sample = transform(image=img)
        img = (sample['image'] / 255).transpose(2, 0, 1).astype('float32')

        return img, (w, h)

    def inference(self, preprocessed_input: Tuple[np.ndarray, Tuple[int, int]]) -> np.ndarray:
        """Segmentation 추론"""
        img, resize_size = preprocessed_input
        x_tensor = torch.from_numpy(img).to(self.device).unsqueeze(0)

        with torch.no_grad():
            pred_mask = self.model(x_tensor)
            pred_mask = pred_mask.detach().squeeze().cpu().numpy()

        return pred_mask, resize_size

    def postprocess(self, raw_output: Tuple[np.ndarray, Tuple[int, int]], original_size: tuple) -> List[Dict]:
        """Segmentation 결과를 polygon으로 변환"""
        pred_mask, (rw, rh) = raw_output
        scale_factor = self.inference_config.RESIZE_FACTOR

        # 최대 확률 클래스 선택
        pred_vis = np.max(pred_mask.transpose(1, 2, 0), axis=-1).round() * \
                   (np.argmax(pred_mask.transpose(1, 2, 0), axis=-1) + 1).astype(int)

        # 리사이즈된 영역만 사용
        resize_mask = cv2.resize(
            pred_vis[:rh, :rw].astype(np.uint8),
            (rw * scale_factor, rh * scale_factor),
            interpolation=cv2.INTER_NEAREST
        )

        # 각 클래스별 contour 추출
        annotations = []
        unique_classes = np.unique(resize_mask)
        annotation_id = 0

        for cls_id in unique_classes:
            if cls_id == 0:  # background 스킵
                continue

            class_mask = (resize_mask == cls_id).astype(np.uint8)
            contours, _ = cv2.findContours(
                class_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 100:  # 최소 면적 필터
                    continue

                # Polygon 좌표 추출
                segmentation = contour.flatten().tolist()
                x, y, w, h = cv2.boundingRect(contour)

                # 카테고리 매핑
                cat_info = self.inference_config.STR_CLASS_MAP.get(int(cls_id), (11, "기타벽"))
                category_id, subcat = cat_info
                category_name = self.inference_config.CATEGORIES.get(category_id, "구조_벽체")

                annotation = {
                    "id": annotation_id,
                    "category_id": category_id,
                    "category_name": category_name,
                    "bbox": [x, y, w, h],
                    "segmentation": [segmentation],
                    "area": float(area),
                    "confidence": 1.0,
                    "iscrowd": 0,
                    "attributes": {
                        "subcat": subcat
                    }
                }
                annotations.append(annotation)
                annotation_id += 1

        return annotations

    def predict(self, image: np.ndarray) -> List[Dict]:
        """전체 예측 파이프라인 (오버라이드)"""
        original_size = (image.shape[1], image.shape[0])
        preprocessed = self.preprocess(image)
        raw_output = self.inference(preprocessed)
        return self.postprocess(raw_output, original_size)
