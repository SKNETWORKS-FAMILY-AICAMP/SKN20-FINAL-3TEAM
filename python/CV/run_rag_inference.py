"""RAG 추론 CLI"""
import argparse
from pathlib import Path

from rag_system.config import RAGConfig
from rag_system.rag_pipeline import RAGPipeline

def main():
    parser = argparse.ArgumentParser(description="RAG 기반 평면도 분석")
    parser.add_argument('--index-eval', action='store_true',
                       help='사내 평가 문서 색인 (최초 1회)')
    parser.add_argument('--topology', type=str,
                       help='topology.json 경로')
    parser.add_argument('--output', type=str,
                       help='분석 결과 저장 경로 (JSON)')

    args = parser.parse_args()

    # 설정 로드
    config = RAGConfig()

    # RAG 파이프라인 초기화
    pipeline = RAGPipeline(config)

    # 사내 평가 문서 색인
    if args.index_eval:
        print("Indexing evaluation document...")
        pipeline.index_evaluation_document("rag_data/사내_평가_문서.json")
        return

    # topology.json 분석
    if args.topology:
        print(f"Analyzing topology: {args.topology}")
        analysis = pipeline.analyze_topology(args.topology)

        # 출력
        print("\n=== 분석 결과 ===")
        print(f"건축물 유형: {analysis.structure_type}")
        print(f"Bay 수: {analysis.bay_count}")
        print(f"총 공간 수: {analysis.total_spaces}")
        print(f"\n요약:\n{analysis.summary}")

        # JSON 저장
        if args.output:
            pipeline.save_analysis_json(analysis, args.output)
        else:
            # 기본 경로
            topology_path = Path(args.topology)
            output_path = topology_path.parent / "analysis_result.json"
            pipeline.save_analysis_json(analysis, str(output_path))

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
