"""
이미지 기반 유사 도면 검색 모듈.

pipeline.py의 텍스트 검색 로직(analyze_query, doc_ratio_constraints, rerank 등)과
완전히 분리된 이미지 전용 검색 경로.

흐름: 임베딩 생성 → 필터+코사인 유사도 검색 → 필터 완화 폴백 → top_k 반환
"""

import json
import logging
import os
import re
from typing import Any, Optional

import psycopg2

logger = logging.getLogger("ImageSearch")

# ── 상수 ──────────────────────────────────────────────

ALLOWED_FILTER_COLUMNS = [
    "windowless_count", "balcony_ratio", "living_room_ratio",
    "bathroom_ratio", "kitchen_ratio", "structure_type",
    "bay_count", "room_count", "bathroom_count",
    "compliance_grade", "ventilation_quality",
    "has_special_space", "has_etc_space",
]

FLOAT_FILTERS = {"balcony_ratio", "living_room_ratio", "bathroom_ratio", "kitchen_ratio"}
VALID_RATIO_OPERATORS = {"이상", "이하", "초과", "미만", "동일"}
RATIO_EQUAL_TOLERANCE = 3.0

# 필터 완화 우선순위 (위에서부터 먼저 제거)
_FILTER_DROP_PRIORITY = [
    {"compliance_grade", "ventilation_quality"},
    {"balcony_ratio", "living_room_ratio", "bathroom_ratio", "kitchen_ratio",
     "has_special_space", "has_etc_space"},
    {"windowless_count"},
    {"bathroom_count"},
    {"bay_count"},
    {"structure_type"},
    {"room_count"},
]

# ── 임베딩 모델 싱글턴 ────────────────────────────────

_LOCAL_MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
_EMBEDDING_DIM = 1024
_local_model = None


def _get_embedding_model():
    """Qwen3-Embedding-0.6B 모델 로드 (최초 1회)"""
    global _local_model
    if _local_model is not None:
        return _local_model

    from sentence_transformers import SentenceTransformer

    logger.info("임베딩 모델 로드 시작: %s", _LOCAL_MODEL_NAME)
    hf_token = os.getenv("HF_TOKEN", "").strip()
    kwargs = {"token": hf_token} if hf_token else {}
    _local_model = SentenceTransformer(_LOCAL_MODEL_NAME, **kwargs)
    logger.info("임베딩 모델 로드 완료")
    return _local_model


def embed_text(text: str) -> list[float]:
    """텍스트 → 1024-dim 임베딩 벡터"""
    model = _get_embedding_model()
    encoded = model.encode(text, normalize_embeddings=True)
    embedding = encoded.tolist() if hasattr(encoded, "tolist") else list(encoded)
    if len(embedding) != _EMBEDDING_DIM:
        raise ValueError(
            f"Embedding dim mismatch: expected={_EMBEDDING_DIM}, actual={len(embedding)}"
        )
    return embedding


# ── SQL 필터 빌더 ─────────────────────────────────────

def _parse_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(\.\d+)?", value)
        if match:
            return float(match.group())
    return None


def _normalize_ratio_operator(op: Any) -> Optional[str]:
    if not isinstance(op, str):
        return None
    cleaned = op.strip()
    return cleaned if cleaned in VALID_RATIO_OPERATORS else None


def _ratio_filter_to_bounds(value: Any) -> list[dict[str, Any]]:
    """비율 필터 값 → [{op, val}, ...] 목록으로 변환"""
    if not isinstance(value, dict):
        return []

    bounds: list[dict[str, Any]] = []

    # bounds 배열
    raw_bounds = value.get("bounds")
    if isinstance(raw_bounds, list):
        for item in raw_bounds:
            if not isinstance(item, dict):
                continue
            op = _normalize_ratio_operator(item.get("op", item.get("operator")))
            val = _parse_float(item.get("val", item.get("value")))
            if op is not None and val is not None:
                bounds.append({"op": op, "val": val})

    # min/max 형식
    min_val = _parse_float(value.get("min", value.get("lower")))
    max_val = _parse_float(value.get("max", value.get("upper")))
    if min_val is not None:
        bounds.append({"op": "이상", "val": min_val})
    if max_val is not None:
        bounds.append({"op": "이하", "val": max_val})

    # op/val 단일 형식
    op = _normalize_ratio_operator(value.get("op", value.get("operator")))
    val = _parse_float(value.get("val", value.get("value")))
    if op is not None and val is not None:
        if op == "동일":
            bounds.append({"op": "이상", "val": round(val - RATIO_EQUAL_TOLERANCE, 4)})
            bounds.append({"op": "이하", "val": round(val + RATIO_EQUAL_TOLERANCE, 4)})
        else:
            bounds.append({"op": op, "val": val})

    # 중복 제거
    seen: set[tuple[str, float]] = set()
    deduped: list[dict[str, Any]] = []
    for b in bounds:
        key = (b["op"], float(b["val"]))
        if key not in seen:
            seen.add(key)
            deduped.append(b)
    return deduped


def build_filter_where(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    """필터 dict → (WHERE SQL, params) 변환"""
    clauses: list[str] = []
    params: list[Any] = []

    for col in ALLOWED_FILTER_COLUMNS:
        value = filters.get(col)
        if value is None:
            continue
        db_col = f"fa.{col}"

        if col in FLOAT_FILTERS:
            bounds = _ratio_filter_to_bounds(
                value if isinstance(value, dict) else {"op": "동일", "val": value}
            )
            for b in bounds:
                clauses.append(f"ratio_cmp({db_col}::double precision, %s, %s)")
                params.extend([b["op"], b["val"]])
        else:
            clauses.append(f"{db_col} = %s")
            params.append(value)

    where_sql = " AND ".join(clauses) if clauses else "TRUE"
    return where_sql, params


def relax_filters(filters: dict[str, Any]) -> list[dict[str, Any]]:
    """필터를 점진적으로 완화한 후보 목록 반환"""
    candidates: list[dict[str, Any]] = []
    current = dict(filters)
    for drop_set in _FILTER_DROP_PRIORITY:
        keys_to_drop = [k for k in current if k in drop_set]
        if keys_to_drop:
            current = {k: v for k, v in current.items() if k not in drop_set}
            candidates.append(current.copy())
    return candidates


# ── 핵심: 유사 도면 검색 ──────────────────────────────

_BASE_SELECT = """
    SELECT f.id AS floorplan_id, f.name AS document_id,
        fa.analysis_description AS document,
        fa.windowless_count, fa.balcony_ratio, fa.living_room_ratio,
        fa.bathroom_ratio, fa.kitchen_ratio,
        fa.structure_type, fa.bay_count, fa.room_count, fa.bathroom_count,
        fa.compliance_grade, fa.ventilation_quality,
        fa.has_special_space, fa.has_etc_space,
        (1 - (fa.embedding <=> %s::vector)) AS similarity
    FROM floorplan_analysis fa
    JOIN floorplan f ON fa.floorplan_id = f.id
"""


def search_similar(
    conn,
    description: str,
    filters: dict[str, Any],
    top_k: int = 3,
) -> dict[str, Any]:
    """
    이미지 분석 결과로 유사 도면 검색.

    Args:
        conn: psycopg2 DB 연결
        description: 검색 쿼리 텍스트 (메트릭 요약 + Overall summary)
        filters: CV 메트릭 기반 필터 (structure_type, room_count 등)
        top_k: 반환할 도면 수
    Returns:
        {"docs": [...], "total_count": int}
    """
    logger.info("유사 도면 검색 시작 (top_k=%d)", top_k)
    logger.info("  필터: %s", filters)
    logger.info("  쿼리: %s", description[:100])

    embedding = embed_text(description)
    embedding_vector = "[" + ",".join(map(str, embedding)) + "]"

    # 1차: 필터 + 임베딩 유사도
    docs = _search_with_filters(conn, embedding_vector, filters, top_k)

    # 2차: 필터 완화 (결과 부족 시)
    if len(docs) < top_k and filters:
        for relaxed in relax_filters(filters):
            dropped = [k for k in filters if k not in relaxed]
            logger.info("  필터 완화: %s 제거 → 남은 필터: %s", dropped, list(relaxed.keys()))
            docs = _search_with_filters(conn, embedding_vector, relaxed, top_k)
            if len(docs) >= top_k:
                break

    # 3차: 필터 전부 제거 (여전히 부족 시)
    if len(docs) < top_k:
        logger.info("  필터 없이 임베딩만으로 검색")
        no_filter_docs = _search_with_filters(conn, embedding_vector, {}, top_k)
        existing_ids = {row[0] for row in docs}
        for row in no_filter_docs:
            if row[0] not in existing_ids:
                docs.append(row)
                existing_ids.add(row[0])
            if len(docs) >= top_k:
                break

    logger.info("유사 도면 검색 완료: %d개 반환", len(docs))
    return {
        "docs": docs[:top_k],
        "total_count": len(docs),
    }


def _search_with_filters(
    conn,
    embedding_vector: str,
    filters: dict[str, Any],
    top_k: int,
) -> list:
    """필터 + 임베딩 코사인 유사도 검색 실행"""
    where_sql, filter_params = build_filter_where(filters)
    params = [embedding_vector, *filter_params, top_k]

    sql = f"""
        {_BASE_SELECT}
        WHERE {where_sql}
        ORDER BY similarity DESC
        LIMIT %s
    """

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    except Exception:
        conn.rollback()
        logger.exception("검색 쿼리 실행 실패 (filters=%s)", list(filters.keys()))
        return []
