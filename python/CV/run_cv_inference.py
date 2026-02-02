"""
건축 평면도 인식 추론 파이프라인 CLI 엔트리 포인트

사용법:
    # 단일 이미지 추론
    python run_cv_inference.py -i test_images/APT_FP_OBJ_001046197.PNG

    # 배치 추론 (폴더 내 모든 이미지)
    python run_cv_inference.py -i test_images/ --batch

    # JSON만 출력 (시각화 없이)
    python run_cv_inference.py -i test_images/APT_FP_OBJ_001046197.PNG --no-vis

    # 출력 폴더 지정
    python run_cv_inference.py -i test_images/APT_FP_OBJ_001046197.PNG -o results/
"""

import argparse
from pathlib import Path

from cv_inference.pipeline import InferencePipeline
from cv_inference.config import InferenceConfig


def main():
    parser = argparse.ArgumentParser(
        description='건축 평면도 인식 추론 파이프라인',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
예시:
  python run_cv_inference.py -i test_images/APT_FP_OBJ_001046197.PNG
  python run_cv_inference.py -i test_images/ --batch
  python run_cv_inference.py -i test_images/APT_FP_OBJ_001046197.PNG --no-vis
        '''
    )
    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='입력 이미지 경로 또는 폴더 경로'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='출력 폴더 경로 (기본: ./output)'
    )
    parser.add_argument(
        '--no-json',
        action='store_true',
        help='JSON 출력 비활성화'
    )
    parser.add_argument(
        '--no-vis',
        action='store_true',
        help='시각화 출력 비활성화'
    )
    parser.add_argument(
        '--batch',
        action='store_true',
        help='배치 처리 모드 (폴더 내 모든 이미지)'
    )
    parser.add_argument(
        '--pattern',
        type=str,
        default='*.PNG',
        help='배치 모드 파일 패턴 (기본: *.PNG)'
    )

    args = parser.parse_args()

    # 설정
    config = InferenceConfig()
    if args.output:
        config.OUTPUT_PATH = Path(args.output)
        config.OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    # 파이프라인 초기화
    print("=" * 60)
    print("건축 평면도 인식 추론 파이프라인")
    print("=" * 60)

    pipeline = InferencePipeline(config)
    pipeline.load_models()

    # 실행
    input_path = Path(args.input)

    print("=" * 60)
    print("추론 시작")
    print("=" * 60)

    if args.batch or input_path.is_dir():
        results = pipeline.run_batch(
            input_path,
            pattern=args.pattern,
            save_json=not args.no_json,
            save_visualization=not args.no_vis
        )
        print(f"\n처리 완료: {len(results)} 이미지")
    else:
        result = pipeline.run(
            input_path,
            save_json=not args.no_json,
            save_visualization=not args.no_vis
        )
        print("\n추론 완료!")

        # 결과 요약 출력
        if "source_result" in result:
            print("\n결과 요약:")
            for model_name, model_data in result["source_result"]["models"].items():
                count = model_data.get("count", 0)
                time_ms = model_data.get("inference_time_ms", 0)
                print(f"  - {model_name}: {count}개 검출 ({time_ms:.1f}ms)")

    print("=" * 60)
    print(f"결과 저장 위치: {config.OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
