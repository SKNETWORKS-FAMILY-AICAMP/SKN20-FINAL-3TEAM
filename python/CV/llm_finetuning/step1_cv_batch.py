"""
Phase 1: CV 배치 추론 (로컬 GPU)
sampled_images.json 기반 2,000장 평면도 → topology_graph.json 생성
"""

import json
import sys
import torch
from pathlib import Path
from tqdm import tqdm

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import PipelineConfig
from training_utils import ProgressTracker

# 기존 CV 추론 파이프라인 임포트
try:
    from CV.cv_inference.pipeline import InferencePipeline
    from CV.cv_inference.config import InferenceConfig
except ImportError as e:
    print(f"❌ CV 추론 모듈을 임포트할 수 없습니다: {e}")
    print(f"   프로젝트 루트: {project_root}")
    sys.exit(1)


def run_cv_batch(config: PipelineConfig):
    """
    CV 배치 추론 실행

    Args:
        config: 파이프라인 설정
    """
    print("=" * 60)
    print("Phase 1: CV 배치 추론 (로컬 GPU)")
    print("=" * 60)

    # 1. GPU 확인
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"✅ GPU: {gpu_name} ({gpu_memory:.1f} GB)")
    else:
        print("⚠️  GPU를 사용할 수 없습니다. CPU 모드로 실행됩니다.")

    # 2. 샘플 이미지 로드
    sampled_images_path = config.TRAINING_DATA_DIR / "sampled_images.json"

    if not sampled_images_path.exists():
        raise FileNotFoundError(
            f"sampled_images.json을 찾을 수 없습니다: {sampled_images_path}\n"
            f"Phase 0 (step0_sample_images.py)을 먼저 실행하세요."
        )

    sampled_stems = json.loads(sampled_images_path.read_text(encoding='utf-8'))
    print(f"✅ 샘플 이미지: {len(sampled_stems)}개")

    # 3. 진행률 추적 초기화
    progress_file = config.PROGRESS_DIR / "cv_batch_progress.json"
    tracker = ProgressTracker(progress_file)

    remaining = tracker.get_remaining(sampled_stems)
    print(f"✅ 처리 대기: {len(remaining)}개")

    if not remaining:
        print("\n✅ 모든 이미지 처리 완료!")
        return

    # 4. CV 추론 파이프라인 초기화
    print("\n🔧 CV 추론 파이프라인 초기화 중...")

    # InferenceConfig 로드 (기존 설정 재사용)
    inference_config = InferenceConfig()

    # InferencePipeline 초기화
    try:
        pipeline = InferencePipeline(config=inference_config)
        pipeline.load_models()  # 모델 로드 필수
        print("✅ CV 추론 파이프라인 초기화 완료")
    except Exception as e:
        print(f"❌ 파이프라인 초기화 실패: {e}")
        raise

    # 5. 배치 처리
    print(f"\n🚀 배치 처리 시작 ({len(remaining)}개)")
    print(f"   시각화 저장: {config.SAVE_VISUALIZATION}")
    print(f"   CUDA 캐시 정리 주기: {config.CUDA_CACHE_CLEAR_INTERVAL}건")

    success_count = 0
    failed_count = 0

    for idx, image_stem in enumerate(tqdm(remaining, desc="CV 추론"), start=1):
        try:
            # 이미지 경로 생성
            image_path = config.IMAGE_DIR / f"{image_stem}.PNG"

            if not image_path.exists():
                # .png 확장자도 시도
                image_path = config.IMAGE_DIR / f"{image_stem}.png"

            if not image_path.exists():
                print(f"\n⚠️  이미지를 찾을 수 없습니다: {image_stem}")
                tracker.mark_failed(image_stem)
                failed_count += 1
                continue

            # 출력 디렉토리 생성
            output_dir = config.OUTPUT_DIR / image_stem
            output_dir.mkdir(parents=True, exist_ok=True)

            # CV 추론 실행
            result = pipeline.run(
                image_path=image_path,
                save_json=False,  # 우리가 직접 저장
                save_visualization=config.SAVE_VISUALIZATION
            )

            # topology_graph.json 저장
            topology_path = output_dir / "topology_graph.json"
            topology_path.write_text(
                json.dumps(result['topology_graph'], ensure_ascii=False, indent=2),
                encoding='utf-8'
            )

            # 완료 표시
            tracker.mark_completed(image_stem)
            success_count += 1

        except Exception as e:
            print(f"\n⚠️  {image_stem} 처리 실패: {e}")
            tracker.mark_failed(image_stem)
            failed_count += 1

        # CUDA 캐시 정리 (주기적)
        if torch.cuda.is_available() and idx % config.CUDA_CACHE_CLEAR_INTERVAL == 0:
            torch.cuda.empty_cache()

    # 6. 결과 요약
    stats = tracker.get_stats()

    print("\n" + "=" * 60)
    print("📊 처리 결과")
    print("=" * 60)
    print(f"성공: {success_count}개")
    print(f"실패: {failed_count}개")
    print(f"총 완료: {stats['completed']}개")
    print(f"총 실패: {stats['failed']}개")

    if failed_count > 0:
        print(f"\n⚠️  실패한 이미지 목록: {tracker.failed}")

    print("=" * 60)


if __name__ == "__main__":
    config = PipelineConfig()
    run_cv_batch(config)
