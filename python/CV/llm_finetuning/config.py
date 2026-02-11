"""
통합 설정 파일 - Qwen3 학습 데이터 생성 파이프라인
로컬 GPU (Phase 0-1) + RunPod A100 (Phase 2-6) 통합 설정
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PipelineConfig:
    # === 경로 설정 ===
    # 로컬 환경 기본 경로
    _IS_LOCAL: bool = not os.path.exists("/workspace")

    @property
    def PROJECT_ROOT(self) -> Path:
        """프로젝트 루트 경로"""
        if self._IS_LOCAL:
            # 로컬: python/ 폴더까지
            return Path(__file__).parent.parent.parent.resolve()
        else:
            # RunPod: /workspace/python
            return Path("/workspace/python")

    @property
    def IMAGE_DIR(self) -> Path:
        """평면도 이미지 디렉토리"""
        if self._IS_LOCAL:
            # 로컬: F 드라이브
            return Path(r"F:\건축 도면 데이터\APT_FP_Cleaned\training")
        else:
            # RunPod
            return Path("/workspace/data/APT_FP_Cleaned/training")

    @property
    def TRAINING_DATA_DIR(self) -> Path:
        """학습 데이터 출력 디렉토리"""
        if self._IS_LOCAL:
            # 로컬: python/CV/llm_finetuning/training_data
            return Path(__file__).parent / "training_data"
        else:
            # RunPod: /workspace/python/CV/llm_finetuning/training_data
            return Path("/workspace/python/CV/llm_finetuning/training_data")

    @property
    def OUTPUT_DIR(self) -> Path:
        """개별 이미지 산출물 디렉토리"""
        return self.TRAINING_DATA_DIR / "output"

    @property
    def PROGRESS_DIR(self) -> Path:
        """진행률 추적 디렉토리"""
        return self.TRAINING_DATA_DIR / "progress"

    @property
    def RAG_DOC_PATH(self) -> Path:
        """RAG 문서 경로"""
        return self.PROJECT_ROOT / "CV" / "rag_data" / "사내_평가_문서.json"

    # === 샘플링 설정 (Phase 0) ===
    TOTAL_IMAGES: int = 9991
    SAMPLE_SIZE: int = 2000
    RANDOM_SEED: int = 42
    STRATIFY_BY: str = "filename_prefix"  # 파일명 접두사로 층화 샘플링

    # === CV 추론 설정 (Phase 1) ===
    SAVE_VISUALIZATION: bool = False
    CUDA_CACHE_CLEAR_INTERVAL: int = 50  # 매 50건마다 캐시 정리

    # === RAG 임베딩 설정 (Phase 2) ===
    EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-0.6B"
    EMBEDDING_DIM: int = 768              # 768 또는 1024 (768 권장)
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_MAX_LENGTH: int = 512
    TOP_K: int = 5

    # === OpenAI API 설정 (Phase 3A) ===
    OPENAI_API_KEY: Optional[str] = None  # 환경변수에서 로드
    OPENAI_MODEL: str = "gpt-4o"          # 최고 품질 모델
    OPENAI_TEMPERATURE: float = 0.1
    OPENAI_MAX_RETRIES: int = 3
    OPENAI_CONCURRENT_REQUESTS: int = 5   # 동시 요청 수

    # === Gemini API 설정 (Phase 3B) ===
    GOOGLE_API_KEY: Optional[str] = None  # 환경변수에서 로드
    GEMINI_MODEL: str = "gemini-3-pro"    # Gemini 3 Pro
    GEMINI_TEMPERATURE: float = 0.1
    GEMINI_MAX_RETRIES: int = 3
    GEMINI_CONCURRENT_REQUESTS: int = 5

    # === 품질 비교 설정 (Phase 4) ===
    QUALITY_SAMPLE_SIZE: int = 100        # 품질 비교용 샘플 수
    MIN_SCHEMA_COMPLIANCE: float = 0.95   # 최소 스키마 준수율

    # === JSONL 설정 (Phase 5) ===
    TRAIN_RATIO: float = 0.9

    # === Qwen3 파인튜닝 설정 (Phase 6) ===
    QWEN3_BASE_MODEL: str = "Qwen/Qwen3-8B"
    LORA_R: int = 64
    LORA_ALPHA: int = 128
    LORA_DROPOUT: float = 0.05
    LEARNING_RATE: float = 2e-4
    NUM_EPOCHS: int = 3
    BATCH_SIZE: int = 2                   # A100 80GB 기준
    GRADIENT_ACCUMULATION: int = 8        # effective batch = 16
    MAX_SEQ_LENGTH: int = 4096
    WARMUP_RATIO: float = 0.03
    SAVE_STEPS: int = 100
    LOGGING_STEPS: int = 10

    def __post_init__(self):
        """환경변수에서 API 키 로드"""
        # object.__setattr__는 frozen dataclass에서 값 설정하는 방법
        if self.OPENAI_API_KEY is None:
            object.__setattr__(self, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))

        if self.GOOGLE_API_KEY is None:
            object.__setattr__(self, 'GOOGLE_API_KEY', os.getenv('GOOGLE_API_KEY'))

    def create_directories(self):
        """필요한 디렉토리 생성"""
        directories = [
            self.TRAINING_DATA_DIR,
            self.OUTPUT_DIR,
            self.PROGRESS_DIR,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        print(f"✅ 디렉토리 생성 완료:")
        print(f"   - 학습 데이터: {self.TRAINING_DATA_DIR}")
        print(f"   - 출력: {self.OUTPUT_DIR}")
        print(f"   - 진행률: {self.PROGRESS_DIR}")
