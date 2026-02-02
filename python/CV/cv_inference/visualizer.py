"""
결과 시각화 모듈
- bbox, segmentation, 라벨 시각화
- 한글 폰트 지원
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from .config import CATEGORY_COLORS, EDGE_COLORS


class ResultVisualizer:
    """추론 결과 시각화"""

    def __init__(self, config):
        self.config = config
        self.font = None
        self._load_font()

    def _load_font(self):
        """한글 폰트 로드"""
        font_paths = [
            "C:/Windows/Fonts/malgun.ttf",      # Windows
            "C:/Windows/Fonts/NanumGothic.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # Linux
            "/System/Library/Fonts/AppleGothic.ttf"  # macOS
        ]

        for font_path in font_paths:
            try:
                self.font = ImageFont.truetype(font_path, 20)
                break
            except:
                continue

        if self.font is None:
            self.font = ImageFont.load_default()

    def _get_color(self, category_name: str) -> Tuple[int, int, int]:
        """카테고리별 색상 반환"""
        return CATEGORY_COLORS.get(category_name, (128, 128, 128))

    def _draw_dashed_line(
        self,
        image: np.ndarray,
        pt1: Tuple[int, int],
        pt2: Tuple[int, int],
        color: Tuple[int, int, int],
        thickness: int = 2,
        gap: int = 10
    ) -> None:
        """점선 그리기"""
        dist = np.sqrt((pt2[0] - pt1[0]) ** 2 + (pt2[1] - pt1[1]) ** 2)
        if dist == 0:
            return

        pts = []
        for i in np.arange(0, dist, gap):
            r = i / dist
            x = int(pt1[0] * (1 - r) + pt2[0] * r)
            y = int(pt1[1] * (1 - r) + pt2[1] * r)
            pts.append((x, y))

        for i in range(0, len(pts) - 1, 2):
            cv2.line(image, pts[i], pts[i + 1], color, thickness)

    def visualize(
        self,
        image: np.ndarray,
        low_result: Dict,
        show_bbox: bool = True,
        show_segmentation: bool = True,
        show_labels: bool = True,
        alpha: float = 0.4
    ) -> np.ndarray:
        """결과 시각화"""
        output_image = image.copy()
        annotations = low_result.get("annotations", [])

        # 1. Segmentation 먼저 그리기 (투명도 적용)
        if show_segmentation:
            overlay = output_image.copy()
            for ann in annotations:
                if ann.get("segmentation") and len(ann["segmentation"]) > 0:
                    color = self._get_color(ann.get("category_name", ""))
                    for seg in ann["segmentation"]:
                        if len(seg) >= 6:  # 최소 3개 점
                            pts = np.array(seg).reshape(-1, 2).astype(np.int32)
                            cv2.fillPoly(overlay, [pts], color)

            cv2.addWeighted(overlay, alpha, output_image, 1 - alpha, 0, output_image)

        # 2. Bounding box 그리기
        if show_bbox:
            for ann in annotations:
                bbox = ann.get("bbox", [])
                if len(bbox) == 4:
                    x, y, w, h = [int(v) for v in bbox]
                    color = self._get_color(ann.get("category_name", ""))
                    cv2.rectangle(output_image, (x, y), (x + w, y + h), color, 2)

        # 3. 라벨 그리기
        if show_labels:
            output_image = self._draw_labels(output_image, annotations)

        return output_image

    def _draw_labels(self, image: np.ndarray, annotations: List[Dict]) -> np.ndarray:
        """라벨 텍스트 그리기 (한글 지원)"""
        # OpenCV -> PIL
        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_image)

        for ann in annotations:
            bbox = ann.get("bbox", [])
            if len(bbox) != 4:
                continue

            x, y, w, h = [int(v) for v in bbox]

            # 라벨 텍스트 결정
            if ann.get("source_model") == "OCR":
                label = ann.get("attributes", {}).get("OCR", "")
            else:
                label = ann.get("category_name", "").split("_")[-1]

            if not label:
                continue

            # 텍스트 크기 계산
            text_bbox = draw.textbbox((0, 0), label, font=self.font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            # 라벨 위치 (bbox 상단)
            label_x = x
            label_y = max(0, y - text_height - 5)

            # 배경 그리기
            draw.rectangle(
                [label_x - 2, label_y - 2, label_x + text_width + 2, label_y + text_height + 2],
                fill=(255, 255, 255)
            )

            # 텍스트 그리기
            draw.text((label_x, label_y), label, font=self.font, fill=(0, 0, 0))

        # PIL -> OpenCV
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    def visualize_by_model(
        self,
        image: np.ndarray,
        source_result: Dict,
        model_name: str,
        alpha: float = 0.4
    ) -> np.ndarray:
        """특정 모델 결과만 시각화"""
        output_image = image.copy()

        model_data = source_result.get("models", {}).get(model_name, {})
        annotations = model_data.get("annotations", [])

        if not annotations:
            return output_image

        # Segmentation
        overlay = output_image.copy()
        for ann in annotations:
            color = self._get_color(ann.get("category_name", ""))

            # Segmentation 그리기
            if ann.get("segmentation") and len(ann["segmentation"]) > 0:
                for seg in ann["segmentation"]:
                    if len(seg) >= 6:
                        pts = np.array(seg).reshape(-1, 2).astype(np.int32)
                        cv2.fillPoly(overlay, [pts], color)

            # Bbox 그리기
            bbox = ann.get("bbox", [])
            if len(bbox) == 4:
                x, y, w, h = [int(v) for v in bbox]
                cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)

        cv2.addWeighted(overlay, alpha, output_image, 1 - alpha, 0, output_image)

        # 라벨 그리기
        output_image = self._draw_labels(output_image, annotations)

        return output_image

    def visualize_topology(
        self,
        image: np.ndarray,
        topology: Dict,
        alpha: float = 0.5
    ) -> np.ndarray:
        """토폴로지 그래프 시각화"""
        output_image = image.copy()
        overlay = output_image.copy()

        nodes = topology.get("nodes", [])
        edges = topology.get("edges", [])

        # 노드 (공간) 시각화
        for node in nodes:
            color = self._get_color(node.get("category_name", ""))

            # Segmentation 그리기
            for seg in node.get("segmentation", []):
                if len(seg) >= 6:
                    pts = np.array(seg).reshape(-1, 2).astype(np.int32)
                    cv2.fillPoly(overlay, [pts], color)

        cv2.addWeighted(overlay, alpha, output_image, 1 - alpha, 0, output_image)

        # 엣지 (연결) 시각화 - 연결 타입별 색상 구분
        node_centroids = {n["node_id"]: tuple(n["centroid"]) for n in nodes}
        for edge in edges:
            src = node_centroids.get(edge["source_node"])
            tgt = node_centroids.get(edge["target_node"])
            if src and tgt:
                connection_type = edge.get("connection_type", "door")
                edge_color = EDGE_COLORS.get(connection_type, (0, 255, 0))

                # 연결 타입별 선 스타일
                if connection_type == "door":
                    # 출입문: 실선
                    cv2.line(output_image, src, tgt, edge_color, 3)
                elif connection_type == "window":
                    # 창문: 점선 효과 (짧은 선분들)
                    self._draw_dashed_line(output_image, src, tgt, edge_color, 3, 15)
                else:
                    # 열린 공간: 점선 효과 (더 긴 간격)
                    self._draw_dashed_line(output_image, src, tgt, edge_color, 3, 25)

                # 중간점에 연결 유형 표시
                mid = ((src[0] + tgt[0]) // 2, (src[1] + tgt[1]) // 2)
                cv2.circle(output_image, mid, 8, edge_color, -1)

        # 노드 라벨 그리기
        pil_image = Image.fromarray(cv2.cvtColor(output_image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_image)

        for node in nodes:
            centroid = tuple(node.get("centroid", [0, 0]))
            label = node.get("label", "")

            if label:
                # 텍스트 크기 계산
                text_bbox = draw.textbbox((0, 0), label, font=self.font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

                # 중심점에 라벨 배치
                label_x = centroid[0] - text_width // 2
                label_y = centroid[1] - text_height // 2

                # 배경
                draw.rectangle(
                    [label_x - 3, label_y - 3, label_x + text_width + 3, label_y + text_height + 3],
                    fill=(255, 255, 255, 200)
                )

                # 텍스트
                draw.text((label_x, label_y), label, font=self.font, fill=(0, 0, 0))

        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    def save_visualization(
        self,
        image: np.ndarray,
        output_path: Path,
        file_stem: str,
        suffix: str = ""
    ) -> Path:
        """시각화 이미지 저장 (이미지별 폴더 구조)"""
        # 이미지별 출력 폴더 생성
        image_output_dir = output_path / file_stem
        image_output_dir.mkdir(parents=True, exist_ok=True)

        file_name = f"{suffix}_result.png" if suffix else "result.png"
        file_name = file_name.lstrip("_")
        file_path = image_output_dir / file_name

        cv2.imwrite(str(file_path), image)
        return file_path

    def create_model_comparison(
        self,
        image: np.ndarray,
        source_result: Dict,
        alpha: float = 0.4
    ) -> np.ndarray:
        """4개 모델 결과 비교 이미지 생성 (2x2 그리드)"""
        h, w = image.shape[:2]

        # 각 모델별 시각화
        obj_vis = self.visualize_by_model(image, source_result, "OBJ", alpha)
        ocr_vis = self.visualize_by_model(image, source_result, "OCR", alpha)
        str_vis = self.visualize_by_model(image, source_result, "STR", alpha)
        spa_vis = self.visualize_by_model(image, source_result, "SPA", alpha)

        # 크기 조정 (절반)
        half_w, half_h = w // 2, h // 2
        obj_vis = cv2.resize(obj_vis, (half_w, half_h))
        ocr_vis = cv2.resize(ocr_vis, (half_w, half_h))
        str_vis = cv2.resize(str_vis, (half_w, half_h))
        spa_vis = cv2.resize(spa_vis, (half_w, half_h))

        # 라벨 추가
        self._add_title(obj_vis, "OBJ (Objects)")
        self._add_title(ocr_vis, "OCR (Text)")
        self._add_title(str_vis, "STR (Structure)")
        self._add_title(spa_vis, "SPA (Space)")

        # 2x2 그리드 조합
        top_row = np.hstack([obj_vis, ocr_vis])
        bottom_row = np.hstack([str_vis, spa_vis])
        comparison = np.vstack([top_row, bottom_row])

        return comparison

    def _add_title(self, image: np.ndarray, title: str) -> None:
        """이미지에 제목 추가"""
        cv2.rectangle(image, (0, 0), (200, 30), (255, 255, 255), -1)
        cv2.putText(image, title, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
