"""
추론 파이프라인 설정
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ============================================================================
# 공간 관련 상수
# ============================================================================

# 공간명 동의어 사전 (같은 그룹은 동일 공간으로 판단)
SPACE_SYNONYMS: Dict[str, List[str]] = {
    "거실": ["거실", "리빙", "living", "리빙룸"],
    "침실": ["침실", "안방", "방", "룸", "bedroom", "master"],
    "주방": ["주방", "키친", "kitchen", "주방/식당", "식당", "주방및식당"],
    "현관": ["현관", "현관홀", "엔트런스", "entrance"],
    "발코니": ["발코니", "베란다", "balcony", "서비스발코니"],
    "화장실": ["화장실", "욕실", "bathroom", "toilet", "wc", "bath",
              "안방욕실", "부부욕실", "마스터욕실", "전용욕실", "가족욕실"],
    "실외기룸": ["실외기실", "실외기룸", "에어컨실", "AC실"],
    "드레스룸": ["드레스룸", "드레스실", "옷방", "wic", "워크인클로짓"],
    "엘리베이터홀": ["엘리베이터홀", "엘베홀", "EV홀", "E/V홀", "EL홀",
                   "승강기홀", "elevator hall", "엘리베이터 홀", "ELEV.홀",
                   "엘리베이터", "엘베", "EV", "E/V", "EL", "승강기", "elevator"],
    "계단실": ["계단실", "계단", "stair", "stairs", "stairwell"],

    "팬트리": ["팬트리", "키친팬트리", "식료품실", "pantry"],
    "다용도실": ["다용도실", "유틸리티", "utility"],
    "서재": ["서재", "공부방", "작업실", "홈오피스"],
    "세탁실": ["세탁실", "세탁공간", "런드리", "laundry", "빨래방"],
}

# 분석을 위한 공간 분류
SPACE_CLASSIFICATION: Dict[str, List[str]] = {
    "기타공간": ["대피공간", "실외기룸", "현관", "발코니"],
    "특화공간": ["팬트리", "드레스룸", "알파룸", "서재"],
    "습식공간": ["주방", "화장실", "세탁실"],
    "공통공간": ["거실"],
    "개인공간": ["침실", "파우더룸"]
}

# 세대 외부 공간 (분석에서 제외)
OUTSIDE_SPACES: List[str] = ["엘리베이터홀", "계단실"]


# ============================================================================
# 시각화 색상 상수 (BGR 형식)
# ============================================================================

# 카테고리별 색상 정의
CATEGORY_COLORS: Dict[str, Tuple[int, int, int]] = {
    # 객체 - 따뜻한 색상
    "객체_변기": (0, 0, 255),         # 빨강
    "객체_세면대": (0, 127, 255),     # 주황
    "객체_싱크대": (0, 255, 255),     # 노랑
    "객체_욕조": (127, 0, 255),       # 자주
    "객체_가스레인지": (255, 0, 127), # 분홍

    # 공간 - 시원한 색상
    "공간_거실": (255, 200, 100),     # 하늘
    "공간_침실": (255, 150, 100),     # 파랑
    "공간_주방": (100, 255, 100),     # 연두
    "공간_현관": (150, 150, 255),     # 연보라
    "공간_발코니": (200, 255, 200),   # 연초록
    "공간_화장실": (255, 200, 200),   # 연분홍
    "공간_실외기실": (200, 200, 200), # 회색
    "공간_드레스룸": (255, 220, 180), # 베이지
    "공간_기타": (180, 180, 180),     # 진회색
    "공간_다목적공간": (200, 200, 255),
    "공간_엘리베이터홀": (220, 220, 220),
    "공간_계단실": (180, 180, 220),
    "공간_엘리베이터": (160, 160, 200),

    # 구조
    "구조_출입문": (0, 255, 0),        # 초록
    "구조_창호": (255, 255, 0),        # 청록
    "구조_벽체": (128, 128, 128),      # 회색

    # OCR
    "OCR": (255, 0, 255)               # 마젠타
}

# 엣지 연결 타입별 색상 정의
EDGE_COLORS: Dict[str, Tuple[int, int, int]] = {
    "door": (0, 255, 0),      # 초록 - 출입문 연결
    "window": (255, 255, 0),  # 청록 - 창문 연결
    "open": (0, 165, 255)     # 주황 - 열린 공간 연결
}


# ============================================================================
# 모델 설정 클래스
# ============================================================================

@dataclass
class ModelConfig:
    """개별 모델 설정"""
    name: str
    model_path: Path
    input_size: Tuple[int, int]
    conf_threshold: float = 0.4
    iou_threshold: float = 0.5


@dataclass
class InferenceConfig:
    """추론 파이프라인 전체 설정"""

    # 기본 경로
    BASE_PATH: Path = field(default_factory=lambda: Path(r"c:\Users\ansck\Desktop\C_Vision"))

    # 이미지 설정
    ORIGINAL_SIZE: Tuple[int, int] = (4960, 3488)
    RESIZE_SIZE: Tuple[int, int] = (620, 436)
    PADDED_SIZE: Tuple[int, int] = (640, 448)
    RESIZE_FACTOR: int = 8

    # 카테고리 정의 (23개)
    CATEGORIES: Dict[int, str] = field(default_factory=lambda: {
        1: "공간_다목적공간",
        2: "공간_엘리베이터홀",
        3: "공간_계단실",
        4: "객체_변기",
        5: "객체_세면대",
        6: "객체_싱크대",
        7: "객체_욕조",
        8: "객체_가스레인지",
        9: "구조_출입문",
        10: "구조_창호",
        11: "구조_벽체",
        12: "background",
        13: "공간_거실",
        14: "공간_침실",
        15: "공간_주방",
        16: "공간_현관",
        17: "공간_발코니",
        18: "공간_화장실",
        19: "공간_실외기실",
        20: "공간_드레스룸",
        21: "OCR",
        22: "공간_기타",
        23: "공간_엘리베이터"
    })

    # OBJ 모델 클래스 매핑 (YOLO output class -> category_id)
    OBJ_CLASS_MAP: Dict[int, int] = field(default_factory=lambda: {
        0: 4,   # toilet -> 객체_변기
        1: 5,   # washstand -> 객체_세면대
        2: 6,   # sink -> 객체_싱크대
        3: 7,   # bathtub -> 객체_욕조
        4: 8    # gas-stove -> 객체_가스레인지
    })

    # OBJ 클래스 이름 (영문)
    OBJ_CLASS_NAMES: Dict[int, str] = field(default_factory=lambda: {
        0: "toilet",
        1: "washstand",
        2: "sink",
        3: "bathtub",
        4: "gas-stove"
    })

    # SPA 모델 클래스 매핑 (model output -> category_id)
    SPA_CLASS_MAP: Dict[int, int] = field(default_factory=lambda: {
        1: 1,    # 다목적공간
        2: 2,    # 엘리베이터홀
        3: 3,    # 계단실
        4: 13,   # 거실
        5: 14,   # 침실
        6: 15,   # 주방
        7: 16,   # 현관
        8: 17,   # 발코니
        9: 18,   # 화장실
        10: 19,  # 실외기실
        11: 20,  # 드레스룸
        12: 22,  # 기타
        13: 23   # 엘리베이터
    })

    # STR 모델 클래스 매핑 (3개 대분류: 출입문, 창호, 벽체)
    STR_CLASS_MAP: Dict[int, Tuple[int, str]] = field(default_factory=lambda: {
        1: (9, "출입문"),
        2: (10, "창호"),
        3: (11, "벽체")
    })

    def __post_init__(self):
        """경로 초기화"""
        INFERENCE_PATH = Path(__file__).parent
        self.MODEL_PATH = INFERENCE_PATH / "model"
        self.OUTPUT_PATH = self.BASE_PATH / "output"
        self.YOLO_PATH = INFERENCE_PATH / "yolov5"

        # 모델별 설정
        self.OBJ_CONFIG = ModelConfig(
            name="OBJ",
            model_path=self.MODEL_PATH / "OBJ" / "OBJ_YOLO_model.pt",
            input_size=(620, 436),
            conf_threshold=0.4,
            iou_threshold=0.5
        )

        self.OCR_YOLO_CONFIG = ModelConfig(
            name="OCR_YOLO",
            model_path=self.MODEL_PATH / "OCR" / "OCR_yolov5_pretrained.pt",
            input_size=(4960, 3488),
            conf_threshold=0.4,
            iou_threshold=0.5
        )

        self.OCR_CRNN_CONFIG = ModelConfig(
            name="OCR_CRNN",
            model_path=self.MODEL_PATH / "OCR" / "CRNN_OCR_BEST_MODEL.pt",
            input_size=(250, 60),
            conf_threshold=0.0,
            iou_threshold=0.0
        )

        self.STR_CONFIG = ModelConfig(
            name="STR",
            model_path=self.MODEL_PATH / "STR" / "STR_FP_test_model.pth",
            input_size=(620, 436),
            conf_threshold=0.0,
            iou_threshold=0.0
        )

        self.SPA_CONFIG = ModelConfig(
            name="SPA",
            model_path=self.MODEL_PATH / "SPA" / "SPA_FP_DeepLabV3_model.pth",
            input_size=(620, 436),
            conf_threshold=0.0,
            iou_threshold=0.0
        )

        # OCR 관련 파일 경로
        self.VOCABULARY_PATH = self.MODEL_PATH / "OCR" / "vocabulary.txt"
        self.REMOVE_WORD_PATH = self.MODEL_PATH / "OCR" / "most_frequent_word.txt"

        # 출력 디렉토리 생성 (이미지별 폴더는 저장 시 동적 생성)
        self.OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
