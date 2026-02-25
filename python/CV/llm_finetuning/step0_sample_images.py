"""
Phase 0: 대표 샘플 2,000장 선정
9,991장에서 층화 샘플링으로 다양성 보장하는 2,000장 선정
"""

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import List

from config import PipelineConfig


def extract_prefix(filename: str, n_chars: int = 3) -> str:
    """
    파일명에서 접두사 추출 (아파트 단지/동 식별용)

    Args:
        filename: 파일명 (예: "ABC_001_01.PNG")
        n_chars: 추출할 문자 수

    Returns:
        접두사 (예: "ABC")
    """
    return filename[:n_chars]


def stratified_sample(
    all_images: List[Path],
    sample_size: int,
    random_seed: int = 42
) -> List[str]:
    """
    층화 샘플링으로 대표 샘플 선정

    전략:
    1. 파일명 접두사(아파트 단지)별 그룹화
    2. 각 그룹에서 비례 할당
    3. 그룹 수 < 비례 할당분인 경우 전수 포함
    4. 잔여분은 가장 큰 그룹에서 랜덤 추출

    Args:
        all_images: 전체 이미지 경로 목록
        sample_size: 선정할 샘플 수
        random_seed: 랜덤 시드

    Returns:
        선정된 이미지 stem 목록
    """
    random.seed(random_seed)

    # 1. 접두사별 그룹화
    groups = defaultdict(list)
    for img_path in all_images:
        prefix = extract_prefix(img_path.name)
        groups[prefix].append(img_path.stem)

    print(f"✅ 그룹화 완료: {len(groups)}개 그룹")
    print(f"   그룹 크기 범위: {min(len(v) for v in groups.values())} ~ {max(len(v) for v in groups.values())}개")

    # 2. 그룹 크기 정렬 (큰 순서)
    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)

    # 3. 각 그룹에서 비례 할당
    total_images = len(all_images)
    sampled = []

    for prefix, images in sorted_groups:
        group_size = len(images)
        # 비례 할당 계산
        allocation = int(sample_size * group_size / total_images)

        # 그룹이 작으면 전수 포함
        if group_size <= allocation:
            sampled.extend(images)
        else:
            # 랜덤 샘플링
            sampled.extend(random.sample(images, allocation))

    # 4. 목표 수에 미달하면 가장 큰 그룹에서 추가 샘플링
    if len(sampled) < sample_size:
        remaining = sample_size - len(sampled)
        largest_group = sorted_groups[0][1]
        # 이미 포함된 이미지 제외
        available = [img for img in largest_group if img not in sampled]

        if available:
            additional = random.sample(available, min(remaining, len(available)))
            sampled.extend(additional)
            print(f"   추가 샘플링: {len(additional)}개 (가장 큰 그룹에서)")

    # 5. 목표 수 초과 시 트림
    if len(sampled) > sample_size:
        sampled = random.sample(sampled, sample_size)

    return sorted(sampled)


def run_sampling(config: PipelineConfig):
    """
    샘플링 실행

    Args:
        config: 파이프라인 설정
    """
    print("=" * 60)
    print("Phase 0: 대표 샘플 2,000장 선정")
    print("=" * 60)

    # 1. 디렉토리 생성
    config.create_directories()

    # 2. 전체 이미지 로드
    print(f"\n📂 이미지 디렉토리: {config.IMAGE_DIR}")

    if not config.IMAGE_DIR.exists():
        raise FileNotFoundError(f"이미지 디렉토리를 찾을 수 없습니다: {config.IMAGE_DIR}")

    all_images = sorted(config.IMAGE_DIR.glob("*.PNG"))

    if not all_images:
        # .png 확장자도 시도
        all_images = sorted(config.IMAGE_DIR.glob("*.png"))

    print(f"✅ 전체 이미지: {len(all_images)}개")

    if len(all_images) < config.SAMPLE_SIZE:
        print(f"⚠️  전체 이미지 수({len(all_images)})가 샘플 크기({config.SAMPLE_SIZE})보다 작습니다.")
        print(f"   전체 이미지를 사용합니다.")
        sampled_stems = [img.stem for img in all_images]
    else:
        # 3. 층화 샘플링 실행
        print(f"\n🎲 층화 샘플링 시작 (목표: {config.SAMPLE_SIZE}개, seed: {config.RANDOM_SEED})")
        sampled_stems = stratified_sample(
            all_images,
            config.SAMPLE_SIZE,
            config.RANDOM_SEED
        )

    print(f"✅ 샘플링 완료: {len(sampled_stems)}개")

    # 4. 결과 저장
    output_path = config.TRAINING_DATA_DIR / "sampled_images.json"
    output_path.write_text(
        json.dumps(sampled_stems, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    print(f"\n💾 저장 완료: {output_path}")
    print(f"   크기: {output_path.stat().st_size / 1024:.1f} KB")

    # 5. 통계 출력
    print("\n" + "=" * 60)
    print("📊 샘플링 통계")
    print("=" * 60)
    print(f"전체 이미지: {len(all_images)}개")
    print(f"선정된 샘플: {len(sampled_stems)}개")
    print(f"샘플링 비율: {len(sampled_stems) / len(all_images) * 100:.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    config = PipelineConfig()
    run_sampling(config)
