import argparse
import os
import re
import sys
from pathlib import Path


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value is not None and value != "" else default


def _parse_env_line(line: str):
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None, None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    if "=" not in stripped:
        return None, None
    key, raw_val = stripped.split("=", 1)
    key = key.strip()
    value = raw_val.strip()
    if not key:
        return None, None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def _load_env_file(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        key, value = _parse_env_line(line)
        if key and key not in os.environ:
            os.environ[key] = value
    return True


def _load_env_candidates() -> None:
    # Supports running from project root or python/floorplan directory.
    cwd = Path.cwd()
    this_dir = Path(__file__).resolve().parent
    candidates = [
        cwd / ".env",
        cwd.parent / ".env",
        this_dir / ".env",
        this_dir.parent / ".env",
        this_dir.parent.parent / ".env",
    ]
    loaded = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in loaded:
            continue
        if _load_env_file(resolved):
            loaded.add(resolved)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test runner for python/floorplan/pipeline.py"
    )
    parser.add_argument("-q", "--query", help="Single query to run")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start interactive query mode",
    )

    parser.add_argument("--db-host", default=_env("POSTGRES_HOST", "localhost"))
    parser.add_argument("--db-port", type=int, default=int(_env("POSTGRES_PORT", "5432")))
    parser.add_argument("--db-name", default=_env("POSTGRES_DB", "arae"))
    parser.add_argument("--db-user", default=_env("POSTGRES_USER", "postgres"))
    parser.add_argument("--db-password", default=_env("POSTGRES_PASSWORD", "1234"))

    parser.add_argument(
        "--openai-api-key",
        default=os.getenv("OPENAI_API_KEY"),
        help="OpenAI API key (or set OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--embedding-model",
        default=_env("EMBEDDING_MODEL", "text-embedding-3-small"),
    )
    parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=int(_env("EMBEDDING_DIMENSIONS", "512")),
    )
    parser.add_argument("--vector-weight", type=float, default=0.8)
    parser.add_argument("--text-weight", type=float, default=0.2)
    parser.add_argument(
        "--validate-sample",
        action="store_true",
        help="Run 100-sample validation (format + ranking metrics) using ground truth data",
    )
    parser.add_argument(
        "--validate-size",
        type=int,
        default=int(_env("VALIDATE_SIZE", "100")),
        help="Validation sample size (default: 100)",
    )
    parser.add_argument(
        "--validate-seed",
        type=int,
        default=int(_env("VALIDATE_SEED", "42")),
        help="Validation sampling seed (default: 42)",
    )
    parser.add_argument(
        "--validate-output",
        default=_env("VALIDATE_OUTPUT_DIR", "artifacts/validation"),
        help="Validation output directory",
    )
    parser.add_argument(
        "--ground-truth-path",
        default=_env("GROUND_TRUTH_PATH", "data/ground_truth.csv"),
        help="Ground truth file path (.csv, .jsonl, .json)",
    )
    return parser


def build_rag(args: argparse.Namespace):
    from pipeline import ArchitecturalHybridRAG

    if not args.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required. Pass --openai-api-key or set env.")

    db_config = {
        "host": args.db_host,
        "port": args.db_port,
        "database": args.db_name,
        "user": args.db_user,
        "password": args.db_password,
    }

    return ArchitecturalHybridRAG(
        db_config=db_config,
        openai_api_key=args.openai_api_key,
        embedding_model=args.embedding_model,
        embedding_dimensions=args.embedding_dimensions,
        vector_weight=args.vector_weight,
        text_weight=args.text_weight,
    )


def run_once(rag, query: str) -> None:
    answer = rag.run(query.strip())
    print("\n=== QUERY ===")
    print(query.strip())
    print("\n=== ANSWER ===")
    print(answer)


def run_interactive(rag) -> None:
    print("Interactive mode. Type 'exit' or 'quit' to stop.")
    while True:
        try:
            query = input("\nQuery> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return
        if query.lower() in {"exit", "quit"}:
            print("Bye.")
            return
        if not query:
            continue
        run_once(rag, query)


def run_image_name_test(rag, image_name: str) -> int:
    query = image_name.strip()
    answer = rag.run(query)

    has_document_id_line = bool(
        re.search(rf"(?m)^1\.\s*검색된 도면 id:\s*{re.escape(query)}\s*$", answer)
    )
    has_metadata_section = "2. 도면 기본 정보 요약" in answer
    has_layout_section = "3. 도면 공간 구성 설명" in answer
    passed = has_document_id_line and has_metadata_section and has_layout_section

    print("\n=== TEST QUERY ===")
    print(query)
    print("\n=== TEST CHECKS ===")
    print(f"- has_document_id_line: {has_document_id_line}")
    print(f"- has_metadata_section: {has_metadata_section}")
    print(f"- has_layout_section: {has_layout_section}")
    print(f"- result: {'PASS' if passed else 'FAIL'}")
    print("\n=== ANSWER ===")
    print(answer)

    return 0 if passed else 1


def main() -> int:
    _load_env_candidates()
    parser = build_parser()
    parser.add_argument(
        "--test-image-name",
        help=(
            "Run document_id query test and assert document-id prompt output format "
            "(example: APT_FP_OCR_030796374.PNG)"
        ),
    )
    args = parser.parse_args()

    try:
        rag = build_rag(args)
        if args.validate_sample:
            from validation_agent import (
                ValidationAgent,
                ValidationConfig,
                ValidationInputError,
            )

            try:
                config = ValidationConfig(
                    ground_truth_path=Path(args.ground_truth_path),
                    output_dir=Path(args.validate_output),
                    sample_size=int(args.validate_size),
                    seed=int(args.validate_seed),
                )
                validator = ValidationAgent(rag=rag, config=config)
                return validator.run()
            except ValidationInputError as exc:
                print(f"Validation input error: {exc}", file=sys.stderr)
                return 2

        if args.test_image_name:
            return run_image_name_test(rag, args.test_image_name)
        if args.interactive:
            run_interactive(rag)
        else:
            query = args.query or input("Query> ").strip()
            if not query:
                print("Empty query.")
                return 1
            run_once(rag, query)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
