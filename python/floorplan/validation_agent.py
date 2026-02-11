import csv
import json
import random
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ValidationInputError(ValueError):
    """Raised when validation inputs are missing or malformed."""


@dataclass(frozen=True)
class ValidationThresholds:
    format_pass_rate: float = 0.98
    mrr: float = 0.80
    recall_at_3: float = 0.90


@dataclass(frozen=True)
class ValidationConfig:
    ground_truth_path: Path
    output_dir: Path
    sample_size: int = 100
    seed: int = 42
    thresholds: ValidationThresholds = ValidationThresholds()


@dataclass
class ValidationCase:
    query_id: str
    query_text: str
    relevant_document_ids: list[str]
    structure_type: str = "unknown"
    bay_count: str = "unknown"
    balcony_ratio_bucket: str = "unknown"
    query_type: str = "unknown"


@dataclass
class ValidationCaseResult:
    query_id: str
    query_text: str
    relevant_document_ids: list[str]
    top_k_ids: list[str]
    top1_id: str | None
    format_pass: bool
    has_document_id_token: bool
    has_metadata_section: bool
    has_layout_section: bool
    mrr: float
    recall_at_3: float
    latency_ms: int
    error_type: str | None
    error_message: str | None


def _split_ids(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        values = [str(item).strip() for item in raw if str(item).strip()]
        return list(dict.fromkeys(values))
    text = str(raw).strip()
    if not text:
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                values = [str(item).strip() for item in parsed if str(item).strip()]
                return list(dict.fromkeys(values))
        except json.JSONDecodeError:
            pass

    chunks = [part.strip().strip('"').strip("'") for part in re.split(r"[,\|;]", text)]
    values = [part for part in chunks if part]
    return list(dict.fromkeys(values))


def _extract_structure_type(text: str) -> str:
    if "판상형" in text:
        return "판상형"
    if "타워형" in text:
        return "타워형"
    if "복도형" in text:
        return "복도형"
    if "혼합형" in text:
        return "혼합형"
    return "unknown"


def _extract_bay_count(text: str) -> str:
    match = re.search(r"(\d+)\s*(?:Bay|베이)", text, flags=re.IGNORECASE)
    if not match:
        return "unknown"
    return match.group(1)


def _extract_balcony_bucket(text: str) -> str:
    if not re.search(r"(발코니|balcony)", text, flags=re.IGNORECASE):
        return "unknown"
    op_match = re.search(r"(이상|이하|초과|미만|동일)", text)
    num_match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:%|퍼센트)?", text)
    if not op_match or not num_match:
        return "mentioned"
    return f"{op_match.group(1)}_{num_match.group(1)}"


def _normalize_case(row: dict[str, Any], row_number: int) -> ValidationCase:
    query_id = str(
        row.get("query_id")
        or row.get("id")
        or row.get("case_id")
        or f"row-{row_number}"
    ).strip()
    query_text = str(row.get("query_text") or row.get("query") or row.get("prompt") or "").strip()
    if not query_text:
        raise ValidationInputError(f"ground truth row {row_number} has empty query_text")

    relevant_ids = _split_ids(
        row.get("relevant_document_ids")
        or row.get("relevant_ids")
        or row.get("ground_truth_ids")
        or row.get("answer_ids")
    )
    if not relevant_ids:
        raise ValidationInputError(f"ground truth row {row_number} has no relevant document ids")

    structure_type = str(row.get("structure_type") or "").strip() or _extract_structure_type(query_text)
    bay_count = str(row.get("bay_count") or "").strip() or _extract_bay_count(query_text)
    balcony_bucket = str(row.get("balcony_ratio_bucket") or "").strip() or _extract_balcony_bucket(query_text)
    query_type = str(row.get("query_type") or row.get("intent_type") or "").strip() or "unknown"

    return ValidationCase(
        query_id=query_id,
        query_text=query_text,
        relevant_document_ids=relevant_ids,
        structure_type=structure_type,
        bay_count=bay_count,
        balcony_ratio_bucket=balcony_bucket,
        query_type=query_type,
    )


def _load_ground_truth(path: Path) -> list[ValidationCase]:
    if not path.exists():
        raise ValidationInputError(f"ground truth file not found: {path}")
    if not path.is_file():
        raise ValidationInputError(f"ground truth path is not a file: {path}")

    suffix = path.suffix.lower()
    rows: list[dict[str, Any]] = []

    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = [dict(row) for row in reader]
    elif suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                parsed = json.loads(stripped)
                if not isinstance(parsed, dict):
                    raise ValidationInputError("jsonl rows must be objects")
                rows.append(parsed)
    elif suffix == ".json":
        with path.open("r", encoding="utf-8") as f:
            parsed = json.load(f)
        if not isinstance(parsed, list):
            raise ValidationInputError("json ground truth must be a list of objects")
        for item in parsed:
            if not isinstance(item, dict):
                raise ValidationInputError("json ground truth rows must be objects")
            rows.append(item)
    else:
        raise ValidationInputError(
            f"unsupported ground truth format: {path.suffix} (supported: .csv, .jsonl, .json)"
        )

    if not rows:
        raise ValidationInputError("ground truth file is empty")

    cases: list[ValidationCase] = []
    for i, row in enumerate(rows, start=1):
        cases.append(_normalize_case(row, i))
    return cases


def _stratum_key(case: ValidationCase) -> tuple[str, str, str, str]:
    return (
        case.structure_type or "unknown",
        case.bay_count or "unknown",
        case.balcony_ratio_bucket or "unknown",
        case.query_type or "unknown",
    )


def _allocate_stratified_counts(
    groups: dict[tuple[str, str, str, str], list[ValidationCase]],
    target_size: int,
    rng: random.Random,
) -> dict[tuple[str, str, str, str], int]:
    total = sum(len(items) for items in groups.values())
    if target_size >= total:
        return {key: len(items) for key, items in groups.items()}
    if target_size <= 0:
        raise ValidationInputError("sample size must be greater than zero")

    keys = list(groups.keys())
    sizes = {key: len(groups[key]) for key in keys}
    n_groups = len(keys)

    allocation = {key: 0 for key in keys}
    if target_size >= n_groups:
        for key in keys:
            allocation[key] = 1
        remaining = target_size - n_groups
    else:
        ranked_keys = sorted(keys, key=lambda key: sizes[key], reverse=True)
        chosen = ranked_keys[:target_size]
        for key in chosen:
            allocation[key] = 1
        return allocation

    residual_sizes = {key: max(sizes[key] - allocation[key], 0) for key in keys}
    residual_total = sum(residual_sizes.values())
    if remaining <= 0 or residual_total <= 0:
        return allocation

    base_extra = {
        key: int((remaining * residual_sizes[key]) / residual_total) for key in keys
    }
    for key, extra in base_extra.items():
        allocation[key] += min(extra, residual_sizes[key])

    allocated = sum(allocation.values())
    left = target_size - allocated
    if left <= 0:
        return allocation

    remainders: list[tuple[float, float, tuple[str, str, str, str]]] = []
    for key in keys:
        if allocation[key] >= sizes[key]:
            continue
        exact = (remaining * residual_sizes[key]) / residual_total
        fractional = exact - int(exact)
        remainders.append((fractional, rng.random(), key))
    remainders.sort(reverse=True)

    idx = 0
    while left > 0 and idx < len(remainders):
        _, _, key = remainders[idx]
        if allocation[key] < sizes[key]:
            allocation[key] += 1
            left -= 1
        idx += 1

    if left > 0:
        expandable = [key for key in keys if allocation[key] < sizes[key]]
        while left > 0 and expandable:
            key = rng.choice(expandable)
            allocation[key] += 1
            left -= 1
            expandable = [k for k in keys if allocation[k] < sizes[k]]

    return allocation


def _stratified_sample(cases: list[ValidationCase], sample_size: int, seed: int) -> list[ValidationCase]:
    groups: dict[tuple[str, str, str, str], list[ValidationCase]] = {}
    for case in cases:
        groups.setdefault(_stratum_key(case), []).append(case)

    rng = random.Random(seed)
    allocation = _allocate_stratified_counts(groups, sample_size, rng)
    selected: list[ValidationCase] = []

    for key, items in groups.items():
        k = allocation.get(key, 0)
        if k <= 0:
            continue
        if k >= len(items):
            selected.extend(items)
            continue
        picked = rng.sample(items, k)
        selected.extend(picked)

    rng.shuffle(selected)
    return selected[:sample_size]


def _first_relevant_rank(ranked_ids: list[str], relevant_set: set[str]) -> int | None:
    for idx, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant_set:
            return idx
    return None


def _compute_mrr(ranked_ids: list[str], relevant_ids: list[str]) -> float:
    relevant_set = set(relevant_ids)
    if not relevant_set:
        return 0.0
    rank = _first_relevant_rank(ranked_ids, relevant_set)
    if rank is None:
        return 0.0
    return 1.0 / rank


def _compute_recall_at_3(ranked_ids: list[str], relevant_ids: list[str]) -> float:
    relevant_set = set(relevant_ids)
    if not relevant_set:
        return 0.0
    top3 = set(ranked_ids[:3])
    hit_count = len(top3.intersection(relevant_set))
    return hit_count / len(relevant_set)


def _check_answer_format(answer: str) -> tuple[bool, bool, bool, bool]:
    text = str(answer or "")
    has_document_id_token = "검색된 도면 id" in text
    has_metadata_section = "2. 도면 기본 정보 요약" in text
    has_layout_section = "3. 도면 공간 구성 설명" in text
    is_non_empty = bool(text.strip())
    return (
        is_non_empty and has_document_id_token and has_metadata_section and has_layout_section,
        has_document_id_token,
        has_metadata_section,
        has_layout_section,
    )


class ValidationAgent:
    def __init__(self, rag: Any, config: ValidationConfig):
        self.rag = rag
        self.config = config

    def _retrieve_ranked_ids(self, query: str) -> list[str]:
        query_json = self.rag._analyze_query(query)
        total_match_count = self.rag._count_matches(query_json.get("filters", {}) or {})
        retrieve_k = min(max(total_match_count, 3), 50)
        docs = self.rag._retrieve_hybrid(query_json, top_k=retrieve_k)
        docs = self.rag._rerank_by_query_signal_preferences(docs, query)
        return [str(row[0]) for row in docs if row]

    def _evaluate_case(self, case: ValidationCase) -> ValidationCaseResult:
        start = time.perf_counter()
        answer = ""
        top_k_ids: list[str] = []
        error_type: str | None = None
        error_message: str | None = None

        try:
            answer = self.rag.run(case.query_text)
        except Exception as exc:  # noqa: BLE001
            error_type = "run_error"
            error_message = str(exc)

        if error_type is None:
            try:
                top_k_ids = self._retrieve_ranked_ids(case.query_text)
            except Exception as exc:  # noqa: BLE001
                error_type = "retrieve_error"
                error_message = str(exc)

        format_pass, has_id_token, has_metadata, has_layout = _check_answer_format(answer)
        mrr = _compute_mrr(top_k_ids, case.relevant_document_ids) if error_type is None else 0.0
        recall_at_3 = (
            _compute_recall_at_3(top_k_ids, case.relevant_document_ids)
            if error_type is None
            else 0.0
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        return ValidationCaseResult(
            query_id=case.query_id,
            query_text=case.query_text,
            relevant_document_ids=case.relevant_document_ids,
            top_k_ids=top_k_ids[:10],
            top1_id=top_k_ids[0] if top_k_ids else None,
            format_pass=format_pass,
            has_document_id_token=has_id_token,
            has_metadata_section=has_metadata,
            has_layout_section=has_layout,
            mrr=round(mrr, 6),
            recall_at_3=round(recall_at_3, 6),
            latency_ms=latency_ms,
            error_type=error_type,
            error_message=error_message,
        )

    def _write_cases_jsonl(self, path: Path, case_results: list[ValidationCaseResult]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for result in case_results:
                f.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")

    def _write_cases_csv(self, path: Path, case_results: list[ValidationCaseResult]) -> None:
        columns = [
            "query_id",
            "query_text",
            "relevant_document_ids",
            "top_k_ids",
            "top1_id",
            "format_pass",
            "has_document_id_token",
            "has_metadata_section",
            "has_layout_section",
            "mrr",
            "recall_at_3",
            "latency_ms",
            "error_type",
            "error_message",
        ]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for result in case_results:
                payload = asdict(result)
                payload["relevant_document_ids"] = ",".join(result.relevant_document_ids)
                payload["top_k_ids"] = ",".join(result.top_k_ids)
                writer.writerow(payload)

    def _build_summary(self, cases: list[ValidationCase], case_results: list[ValidationCaseResult]) -> dict[str, Any]:
        total = len(case_results)
        if total == 0:
            raise ValidationInputError("no validation cases were executed")

        format_pass_count = sum(1 for r in case_results if r.format_pass)
        error_count = sum(1 for r in case_results if r.error_type is not None)

        mean_mrr = sum(r.mrr for r in case_results) / total
        mean_recall = sum(r.recall_at_3 for r in case_results) / total
        mean_latency_ms = int(sum(r.latency_ms for r in case_results) / total)
        format_pass_rate = format_pass_count / total
        error_rate = error_count / total

        thresholds = self.config.thresholds
        pass_checks = {
            "format_pass_rate": format_pass_rate >= thresholds.format_pass_rate,
            "mrr": mean_mrr >= thresholds.mrr,
            "recall_at_3": mean_recall >= thresholds.recall_at_3,
        }
        overall_pass = all(pass_checks.values())

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sample_size_requested": self.config.sample_size,
            "sample_size_executed": len(cases),
            "seed": self.config.seed,
            "thresholds": asdict(thresholds),
            "metrics": {
                "format_pass_rate": round(format_pass_rate, 6),
                "mrr": round(mean_mrr, 6),
                "recall_at_3": round(mean_recall, 6),
                "error_rate": round(error_rate, 6),
                "mean_latency_ms": mean_latency_ms,
            },
            "counts": {
                "format_pass": format_pass_count,
                "format_fail": total - format_pass_count,
                "error": error_count,
            },
            "checks": pass_checks,
            "overall_pass": overall_pass,
        }

    def _write_summary_json(self, path: Path, summary: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    def _write_summary_md(self, path: Path, summary: dict[str, Any]) -> None:
        metrics = summary["metrics"]
        thresholds = summary["thresholds"]
        checks = summary["checks"]
        lines = [
            "# Validation Summary",
            "",
            f"- Generated At (UTC): {summary['generated_at']}",
            f"- Requested Sample Size: {summary['sample_size_requested']}",
            f"- Executed Sample Size: {summary['sample_size_executed']}",
            f"- Seed: {summary['seed']}",
            f"- Overall PASS: {summary['overall_pass']}",
            "",
            "## Metrics",
            "",
            f"- Format Pass Rate: {metrics['format_pass_rate']} (threshold: {thresholds['format_pass_rate']})",
            f"- MRR: {metrics['mrr']} (threshold: {thresholds['mrr']})",
            f"- Recall@3: {metrics['recall_at_3']} (threshold: {thresholds['recall_at_3']})",
            f"- Error Rate: {metrics['error_rate']}",
            f"- Mean Latency (ms): {metrics['mean_latency_ms']}",
            "",
            "## Check Results",
            "",
            f"- format_pass_rate: {checks['format_pass_rate']}",
            f"- mrr: {checks['mrr']}",
            f"- recall_at_3: {checks['recall_at_3']}",
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run(self) -> int:
        cases = _load_ground_truth(self.config.ground_truth_path)
        sampled_cases = _stratified_sample(cases, self.config.sample_size, self.config.seed)

        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        case_results: list[ValidationCaseResult] = []

        total = len(sampled_cases)
        for idx, case in enumerate(sampled_cases, start=1):
            print(f"[{idx}/{total}] validating query_id={case.query_id}")
            result = self._evaluate_case(case)
            case_results.append(result)
            if result.error_type:
                print(f"  - error: {result.error_type}")
            else:
                print(
                    f"  - format_pass={result.format_pass}, mrr={result.mrr:.4f}, recall@3={result.recall_at_3:.4f}"
                )

        cases_jsonl = self.config.output_dir / "validation_cases.jsonl"
        cases_csv = self.config.output_dir / "validation_cases.csv"
        summary_json = self.config.output_dir / "validation_summary.json"
        summary_md = self.config.output_dir / "validation_summary.md"

        self._write_cases_jsonl(cases_jsonl, case_results)
        self._write_cases_csv(cases_csv, case_results)

        summary = self._build_summary(sampled_cases, case_results)
        self._write_summary_json(summary_json, summary)
        self._write_summary_md(summary_md, summary)

        print("\n=== VALIDATION SUMMARY ===")
        print(f"- overall_pass: {summary['overall_pass']}")
        print(f"- format_pass_rate: {summary['metrics']['format_pass_rate']}")
        print(f"- mrr: {summary['metrics']['mrr']}")
        print(f"- recall@3: {summary['metrics']['recall_at_3']}")
        print(f"- output_dir: {self.config.output_dir}")

        return 0 if summary["overall_pass"] else 1
