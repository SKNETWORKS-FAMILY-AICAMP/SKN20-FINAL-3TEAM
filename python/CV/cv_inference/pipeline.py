"""
건축 평면도 인식 추론 파이프라인
"""

import cv2
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .config import InferenceConfig
from .models.obj_model import OBJModel
from .models.ocr_model import OCRModel
from .models.str_model import STRModel
from .models.spa_model import SPAModel
from .aggregator import ResultAggregator
from .visualizer import ResultVisualizer


# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger("InferencePipeline")


class InferencePipeline:
    """건축 평면도 인식 추론 파이프라인"""

    def __init__(self, config: Optional[InferenceConfig] = None):
        self.config = config or InferenceConfig()

        # 모델 초기화
        self.obj_model = None
        self.ocr_model = None
        self.str_model = None
        self.spa_model = None

        # 후처리/시각화 모듈
        self.aggregator = ResultAggregator(self.config)
        self.visualizer = ResultVisualizer(self.config)

        self._models_loaded = False

    def load_models(self) -> None:
        """모든 모델 로드"""
        logger.info("Loading models...")
        logger.info(f"Device: cuda if available")

        # OBJ 모델
        logger.info("Loading OBJ model...")
        self.obj_model = OBJModel(self.config.OBJ_CONFIG, self.config)
        self.obj_model.load_model()

        # OCR 모델
        logger.info("Loading OCR model...")
        self.ocr_model = OCRModel(
            self.config.OCR_YOLO_CONFIG,
            self.config.OCR_CRNN_CONFIG,
            self.config
        )
        self.ocr_model.load_model()

        # STR 모델
        logger.info("Loading STR model...")
        self.str_model = STRModel(self.config.STR_CONFIG, self.config)
        self.str_model.load_model()

        # SPA 모델
        logger.info("Loading SPA model...")
        self.spa_model = SPAModel(self.config.SPA_CONFIG, self.config)
        self.spa_model.load_model()

        self._models_loaded = True
        logger.info("All models loaded successfully!")

    def run(
        self,
        image_path: Path,
        save_json: bool = True,
        save_visualization: bool = True
    ) -> Dict:
        """단일 이미지 추론 실행"""
        if not self._models_loaded:
            raise RuntimeError("Models not loaded. Call load_models() first.")

        image_path = Path(image_path)
        logger.info(f"Processing: {image_path.name}")

        # 이미지 로드
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        image_info = {
            "file_name": image_path.name,
            "width": image.shape[1],
            "height": image.shape[0]
        }

        inference_times = {}

        # OBJ 추론
        logger.info("Running OBJ inference...")
        start_time = time.time()
        obj_results = self.obj_model.predict(image)
        inference_times["OBJ"] = (time.time() - start_time) * 1000
        logger.info(f"OBJ: {len(obj_results)} objects detected ({inference_times['OBJ']:.1f}ms)")

        # OCR 추론
        logger.info("Running OCR inference...")
        start_time = time.time()
        ocr_results = self.ocr_model.predict(image)
        inference_times["OCR"] = (time.time() - start_time) * 1000
        logger.info(f"OCR: {len(ocr_results)} texts detected ({inference_times['OCR']:.1f}ms)")

        # STR 추론
        logger.info("Running STR inference...")
        start_time = time.time()
        str_results = self.str_model.predict(image)
        inference_times["STR"] = (time.time() - start_time) * 1000
        logger.info(f"STR: {len(str_results)} structures detected ({inference_times['STR']:.1f}ms)")

        # SPA 추론
        logger.info("Running SPA inference...")
        start_time = time.time()
        spa_results = self.spa_model.predict(image)
        inference_times["SPA"] = (time.time() - start_time) * 1000
        logger.info(f"SPA: {len(spa_results)} spaces detected ({inference_times['SPA']:.1f}ms)")

        # 결과 통합
        all_results = self.aggregator.aggregate(
            image_info, obj_results, ocr_results,
            str_results, spa_results, inference_times
        )

        # JSON 저장
        if save_json:
            saved_paths = self.aggregator.save_results(
                all_results,
                self.config.OUTPUT_PATH,
                image_path.stem
            )
            for result_type, path in saved_paths.items():
                logger.info(f"Saved {result_type}: {path}")

        # 시각화 저장
        if save_visualization:
            # 통합 시각화
            vis_image = self.visualizer.visualize(
                image, all_results["low_result"]
            )
            vis_path = self.visualizer.save_visualization(
                vis_image, self.config.OUTPUT_PATH, image_path.stem
            )
            logger.info(f"Saved visualization: {vis_path}")

            # 토폴로지 시각화
            topo_image = self.visualizer.visualize_topology(
                image, all_results["topology_graph"]
            )
            topo_path = self.visualizer.save_visualization(
                topo_image, self.config.OUTPUT_PATH, image_path.stem, "_topology"
            )
            logger.info(f"Saved topology visualization: {topo_path}")

            # 모델별 비교 시각화
            comparison_image = self.visualizer.create_model_comparison(
                image, all_results["source_result"]
            )
            comp_path = self.visualizer.save_visualization(
                comparison_image, self.config.OUTPUT_PATH, image_path.stem, "_comparison"
            )
            logger.info(f"Saved comparison visualization: {comp_path}")

        total_time = sum(inference_times.values())
        logger.info(f"Total inference time: {total_time:.1f}ms")

        return all_results

    def run_batch(
        self,
        image_dir: Path,
        pattern: str = "*.PNG",
        save_json: bool = True,
        save_visualization: bool = True
    ) -> List[Dict]:
        """배치 추론 실행"""
        if not self._models_loaded:
            raise RuntimeError("Models not loaded. Call load_models() first.")

        image_dir = Path(image_dir)
        image_paths = sorted(image_dir.glob(pattern))

        # 대소문자 무시
        if not image_paths:
            image_paths = sorted(image_dir.glob(pattern.lower()))

        logger.info(f"Found {len(image_paths)} images")

        results = []
        for idx, image_path in enumerate(image_paths, 1):
            logger.info(f"[{idx}/{len(image_paths)}] Processing {image_path.name}")
            try:
                result = self.run(image_path, save_json, save_visualization)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing {image_path}: {e}")

        logger.info(f"Batch processing completed: {len(results)}/{len(image_paths)} successful")
        return results

    def predict_single(self, image_path: Path) -> Dict:
        """단일 이미지 추론 (저장 없이)"""
        return self.run(image_path, save_json=False, save_visualization=False)
