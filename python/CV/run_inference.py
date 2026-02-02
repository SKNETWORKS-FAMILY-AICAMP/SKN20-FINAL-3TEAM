"""
건축 평면도 인식 및 분석 통합 파이프라인 CLI

사용법:
    # CV 추론 + RAG 분석 (전체 파이프라인)
    python run_inference.py -i test_images/APT_FP_OBJ_001046197.PNG

    # CV 추론만 실행
    python run_inference.py -i test_images/APT_FP_OBJ_001046197.PNG --cv-only

    # RAG 분석만 실행 (기존 topology.json 필요)
    python run_inference.py -i test_images/APT_FP_OBJ_001046197.PNG --rag-only

    # 배치 처리 (CV + RAG)
    python run_inference.py -i test_images/ --batch

    # 사내 평가 문서 색인 (최초 1회)
    python run_inference.py --index-eval
"""

import argparse
from pathlib import Path


def run_cv_inference(input_path: Path, config, save_json: bool = True, save_vis: bool = True):
    """CV 추론 실행"""
    from cv_inference.pipeline import InferencePipeline

    pipeline = InferencePipeline(config)
    pipeline.load_models()

    result = pipeline.run(
        input_path,
        save_json=save_json,
        save_visualization=save_vis
    )

    # 결과 요약 출력
    if "source_result" in result:
        print("\n[CV] 결과 요약:")
        for model_name, model_data in result["source_result"]["models"].items():
            count = model_data.get("count", 0)
            time_ms = model_data.get("inference_time_ms", 0)
            print(f"  - {model_name}: {count}개 검출 ({time_ms:.1f}ms)")

    return result


def run_rag_analysis(topology_path: Path, output_path: Path = None):
    """RAG 분석 실행"""
    from rag_system.config import RAGConfig
    from rag_system.rag_pipeline import RAGPipeline

    config = RAGConfig()
    pipeline = RAGPipeline(config)

    analysis = pipeline.analyze_topology(str(topology_path))

    # 결과 출력
    print("\n[RAG] 분석 결과:")
    print(f"  - 건축물 유형: {analysis.structure_type}")
    print(f"  - Bay 수: {analysis.bay_count}")
    print(f"  - 총 공간 수: {analysis.total_spaces}")
    print(f"  - 발코니 비율: {analysis.balcony_ratio:.2f}%")
    print(f"  - 창문 없는 공간 비율: {analysis.windowless_ratio:.2f}%")
    print(f"  - 환기 품질: {analysis.ventilation_quality}")

    # JSON 저장
    if output_path is None:
        output_path = topology_path.parent / "analysis_result.json"
    pipeline.save_analysis_json(analysis, str(output_path))

    return analysis


def main():
    parser = argparse.ArgumentParser(
        description='건축 평면도 인식 및 분석 통합 파이프라인',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
예시:
  python run_inference.py -i test_images/APT_FP_OBJ_001046197.PNG
  python run_inference.py -i test_images/APT_FP_OBJ_001046197.PNG --cv-only
  python run_inference.py -i test_images/APT_FP_OBJ_001046197.PNG --rag-only
  python run_inference.py -i test_images/ --batch
  python run_inference.py --index-eval
        '''
    )

    # 입력/출력 옵션
    parser.add_argument('--input', '-i', type=str, help='입력 이미지 경로 또는 폴더 경로')
    parser.add_argument('--output', '-o', type=str, default=None, help='출력 폴더 경로 (기본: ./output)')

    # 실행 모드 옵션
    parser.add_argument('--cv-only', action='store_true', help='CV 추론만 실행')
    parser.add_argument('--rag-only', action='store_true', help='RAG 분석만 실행 (기존 topology.json 필요)')
    parser.add_argument('--index-eval', action='store_true', help='사내 평가 문서 색인 (최초 1회)')

    # CV 옵션
    parser.add_argument('--no-json', action='store_true', help='JSON 출력 비활성화')
    parser.add_argument('--no-vis', action='store_true', help='시각화 출력 비활성화')
    parser.add_argument('--batch', action='store_true', help='배치 처리 모드')
    parser.add_argument('--pattern', type=str, default='*.PNG', help='배치 모드 파일 패턴 (기본: *.PNG)')

    args = parser.parse_args()

    # 사내 평가 문서 색인
    if args.index_eval:
        from rag_system.config import RAGConfig
        from rag_system.rag_pipeline import RAGPipeline

        print("=" * 60)
        print("사내 평가 문서 색인")
        print("=" * 60)

        config = RAGConfig()
        pipeline = RAGPipeline(config)
        pipeline.index_evaluation_document("rag_data/사내_평가_문서.json")
        print("색인 완료!")
        return

    # 입력 필수 체크
    if not args.input:
        parser.print_help()
        return

    input_path = Path(args.input)

    # CV 설정
    from cv_inference.config import InferenceConfig
    cv_config = InferenceConfig()
    if args.output:
        cv_config.OUTPUT_PATH = Path(args.output)
        cv_config.OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("건축 평면도 인식 및 분석 파이프라인")
    print("=" * 60)

    # 배치 처리
    if args.batch or input_path.is_dir():
        from cv_inference.pipeline import InferencePipeline

        if not args.rag_only:
            print("\n[CV] 배치 추론 시작...")
            pipeline = InferencePipeline(cv_config)
            pipeline.load_models()
            results = pipeline.run_batch(
                input_path,
                pattern=args.pattern,
                save_json=not args.no_json,
                save_visualization=not args.no_vis
            )
            print(f"\n[CV] 처리 완료: {len(results)} 이미지")

        if not args.cv_only:
            print("\n[RAG] 배치 분석 시작...")
            # output 디렉토리에서 topology_graph.json 찾기
            topology_files = list(cv_config.OUTPUT_PATH.glob("*/topology_graph.json"))
            for topology_file in topology_files:
                print(f"\n분석 중: {topology_file.parent.name}")
                try:
                    run_rag_analysis(topology_file)
                except Exception as e:
                    print(f"  오류: {e}")
            print(f"\n[RAG] 처리 완료: {len(topology_files)} 도면")

    # 단일 이미지 처리
    else:
        image_name = input_path.stem
        output_dir = cv_config.OUTPUT_PATH / image_name

        # CV 추론
        if not args.rag_only:
            print("\n[CV] 추론 시작...")
            run_cv_inference(input_path, cv_config, save_json=not args.no_json, save_vis=not args.no_vis)
            print("[CV] 추론 완료!")

        # RAG 분석
        if not args.cv_only:
            topology_path = output_dir / "topology_graph.json"

            if not topology_path.exists():
                print(f"\n[RAG] 오류: topology_graph.json을 찾을 수 없습니다: {topology_path}")
                print("  --cv-only 없이 실행하거나, CV 추론을 먼저 실행하세요.")
                return

            print("\n[RAG] 분석 시작...")
            run_rag_analysis(topology_path)
            print("[RAG] 분석 완료!")

    print("\n" + "=" * 60)
    print(f"결과 저장 위치: {cv_config.OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
