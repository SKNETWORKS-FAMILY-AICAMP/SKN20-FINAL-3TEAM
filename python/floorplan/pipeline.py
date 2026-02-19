import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
import psycopg2
from openai import OpenAI

from CV.rag_system.embeddings import EmbeddingManager


@dataclass
class AnswerValidationResult:
    ok: bool
    has_document_id_token: bool
    has_metadata_summary: bool
    has_layout_summary: bool
    missing_fields: list[str] = field(default_factory=list)


class ArchitecturalHybridRAG:
    ALLOWED_FILTER_COLUMNS = [
        "windowless_count",
        "balcony_ratio",
        "living_room_ratio",
        "bathroom_ratio",
        "kitchen_ratio",
        "structure_type",
        "bay_count",
        "room_count",
        "bathroom_count",
        "compliance_grade",
        "ventilation_grade",
        "has_special_space",
        "has_etc_space",
    ]

    FILTER_ALIASES = {
        "ventilation_quality": "ventilation_grade",
    }

    # floorplan_analysis 실제 DB 컬럼명 매핑 (내부명 → DB 컬럼명)
    _DB_COLUMN_MAP = {
        "ventilation_grade": "ventilation_quality",
    }

    INT_FILTERS = {"bay_count", "room_count", "bathroom_count", "windowless_count"}
    FLOAT_FILTERS = {
        "balcony_ratio",
        "living_room_ratio",
        "bathroom_ratio",
        "kitchen_ratio",
    }
    BOOL_FILTERS = {"has_special_space", "has_etc_space"}
    VALID_RATIO_OPERATORS = {"이상", "이하", "초과", "미만", "동일"}
    FLOORPLAN_IMAGE_NAME_RE = re.compile(
        r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:png|jpg|jpeg|bmp|tif|tiff|webp)$",
        re.IGNORECASE,
    )
    DOCUMENT_SIGNAL_KEY_ALIASES = {
        "lighting": ("lighting", "채광"),
        "ventilation": ("ventilation", "환기"),
        "family_harmony": ("family_harmony", "가족 융화", "가족융화"),
        "storage": ("storage", "수납공간", "수납 공간"),
    }
    DOCUMENT_SIGNAL_KR_LABELS = {
        "lighting": "채광",
        "ventilation": "환기",
        "family_harmony": "가족 융화",
        "storage": "수납공간",
    }
    POSITIVE_SIGNAL_WORDS = ("우수", "적정", "적합", "양호", "충분", "넉넉")
    NEGATIVE_SIGNAL_WORDS = ("미흡", "부족", "부적합", "불합격", "미달", "없음")
    SIGNAL_POSITIVE_DISPLAY = {
        "lighting": "좋음",
        "ventilation": "좋음",
        "family_harmony": "적합",
        "storage": "넉넉함",
    }
    SIGNAL_NEGATIVE_DISPLAY = {
        "lighting": "부족함",
        "ventilation": "부족함",
        "family_harmony": "미흡함",
        "storage": "부족함",
    }
    DOCUMENT_ID_LINE_RE = re.compile(r"(?m)^1\.\s*검색된 도면 id:\s*(.+)\s*$")
    GENERAL_ID_TOKEN_RE = re.compile(r"검색된\s*도면\s*id", re.IGNORECASE)
    METADATA_SECTION_TOKEN = "2. 도면 기본 정보"
    LAYOUT_SECTION_TOKEN = "3. 도면 공간 구성 설명"
    NO_MATCH_COUNT_LINE_RE = re.compile(
        r"조건을\s*만족하는\s*도면\s*총\s*개수\s*:\s*0",
        re.IGNORECASE,
    )
    NO_MATCH_ID_LINE_RE = re.compile(
        r"검색된\s*도면\s*id\s*:\s*없음",
        re.IGNORECASE,
    )
    NO_MATCH_MESSAGE_TOKEN = "요청 조건과 일치하는 도면이 존재하지 않습니다."
    BALCONY_POSITIVE_HINT_RE = re.compile(
        r"(활용도\s*높|활용\s*가능|외부\s*공간.*활용|연결.*원활|채광.*좋|넓)",
        re.IGNORECASE,
    )
    BALCONY_NEGATIVE_HINT_RE = re.compile(
        r"(활용도\s*낮|활용\s*어려|연결.*불편|채광.*부족|좁|없음)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        db_config,
        openai_api_key,
        embedding_model: str = "Qwen/Qwen3-Embedding-0.6B",
        embedding_dimensions: int = 1024,
        vector_weight: float = 0.8,
        text_weight: float = 0.2,
        answer_validation_enabled: bool = True,
        answer_validation_retry_max: int = 1,
        answer_validation_safe_fallback: bool = True,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.WARNING,
                format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            )

        self.conn = psycopg2.connect(**db_config)
        self._ensure_ratio_cmp_function()
        self.client = OpenAI(api_key=openai_api_key)
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self.embedding_manager = EmbeddingManager(model_name=embedding_model)
        self.vector_weight, self.text_weight = self._normalize_hybrid_weights(
            vector_weight, text_weight
        )
        self.answer_validation_enabled = bool(answer_validation_enabled)
        self.answer_validation_retry_max = max(0, int(answer_validation_retry_max))
        self.answer_validation_safe_fallback = bool(answer_validation_safe_fallback)
        self.word_dict: dict[str, Any] = {}
        word_path = Path(__file__).resolve().parent / "data" / "word.json"
        try:
            with word_path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.word_dict = loaded if isinstance(loaded, dict) else {}
        except Exception as exc:  
            self.word_dict = {}
            self.logger.warning("Failed to load word dictionary (%s): %s", word_path, exc)

    def _log_event(self, event: str, level: int = logging.INFO, **fields: Any) -> None:
        if not self.logger.isEnabledFor(level):
            return
        try:
            payload = json.dumps(fields, ensure_ascii=False, sort_keys=True, default=str)
        except Exception:
            payload = str(fields)
        self.logger.log(level, "event=%s data=%s", event, payload)

    @staticmethod
    def _compress_compound_space_label(label: str) -> str:
        tokens = [token.strip() for token in str(label).split("/") if token.strip()]
        if len(tokens) < 2:
            return label

        first = re.fullmatch(r"(.+?)(\d+)$", tokens[0])
        if not first:
            return label

        base = first.group(1).strip()
        numbers = [first.group(2)]
        if not base:
            return label

        for token in tokens[1:]:
            if token.isdigit():
                numbers.append(token)
                continue
            match = re.fullmatch(r"(.+?)(\d+)$", token)
            if not match or match.group(1).strip() != base:
                return label
            numbers.append(match.group(2))

        return f"{base}{'/'.join(numbers)}"

    def _normalize_space_section_labels(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return text

        def _replace(match: re.Match[str]) -> str:
            prefix = match.group("prefix")
            label = match.group("label")
            sep = match.group("sep")
            body = match.group("body")
            compacted = self._compress_compound_space_label(label)
            return f"{prefix}{compacted}{sep}{body}"

        return re.sub(
            r"(?m)^(?P<prefix>\s*■\s*)(?P<label>[^:\n]+?)(?P<sep>\s*:\s*)(?P<body>.*)$",
            _replace,
            text,
        )

    def _normalize_summary_signal_sentence(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return text

        text = re.sub(
            r"\(\s*(?:근거\s*없음|근거\s*미확인|근거\s*불명|확인\s*필요)\s*\)",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"[ \t]+,", ",", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        # Normalize parenthetical evidence and collapse accidental adjacent duplicates.
        text = re.sub(
            r"\(\s*([^()]*?)\s*\)",
            lambda m: f"({re.sub(r'\\s+', ' ', m.group(1)).strip()})",
            text,
        )
        text = re.sub(r"(\([^()]+\))(?:\s*\1)+", r"\1", text)

        def _rewrite(match: re.Match[str]) -> str:
            prefix = match.group("prefix") or ""
            bay = match.group("bay").strip()
            structure = re.sub(r"\s+", " ", match.group("structure")).strip()
            rest = re.sub(r"\s+", " ", match.group("rest")).strip()
            return f"{prefix}{bay}Bay {structure} 구조입니다.\n{prefix}{rest}"

        return re.sub(
            r"(?m)^(?P<prefix>\s*)도면은\s*(?P<bay>\d+)\s*Bay\s+(?P<structure>[^,\n]+?)\s*구조(?:이며|로),\s*(?P<rest>채광\s*:\s*[^\n]+?으로\s*정리됩니다\.)\s*$",
            _rewrite,
            text,
        )

    def _normalize_meta_expressions(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return text

        # "외기창이 필요하다고 기재되어 있습니다." -> "외기창이 필요합니다."
        text = re.sub(
            r"([^\n.,:;]+?)하다고\s*(?:기재|언급|서술|표기|표시)되어 있습니다",
            r"\1합니다",
            text,
        )
        # "창문이 없다고 기재되어 있습니다." -> "창문이 없습니다."
        text = re.sub(
            r"([^\n.,:;]+?)다고\s*(?:기재|언급|서술|표기|표시)되어 있습니다",
            r"\1입니다",
            text,
        )
        text = re.sub(
            r"(?:라고|다고)\s*(?:기재|언급|서술|표기|표시)되어 있습니다",
            "",
            text,
        )
        return re.sub(r"[ \t]{2,}", " ", text)

    def _normalize_generated_answer(self, answer: str) -> str:
        return self._normalize_meta_expressions(
            self._normalize_summary_signal_sentence(
                self._normalize_space_section_labels(answer)
            )
        )

    def _validate_answer_format(
        # LLM 답변 형식이 지켜졌는가 
        self,
        answer: str,
        mode: str,
        expected_document_id: Optional[str] = None,
    ) -> AnswerValidationResult:
        text = str(answer or "")
        missing_fields: list[str] = []

        is_non_empty = bool(text.strip())
        if not is_non_empty:
            missing_fields.append("non_empty_answer")

        normalized_mode = mode.strip().lower()
        if normalized_mode == "no_match":
            has_metadata_summary = bool(self.NO_MATCH_COUNT_LINE_RE.search(text))
            has_document_id_token = bool(self.NO_MATCH_ID_LINE_RE.search(text))
            has_layout_summary = self.NO_MATCH_MESSAGE_TOKEN in text
            if not has_metadata_summary:
                missing_fields.append("no_match_count")
            if not has_document_id_token:
                missing_fields.append("document_id_none")
            if not has_layout_summary:
                missing_fields.append("no_match_message")
            ok = (
                is_non_empty
                and has_document_id_token
                and has_metadata_summary
                and has_layout_summary
            )
            return AnswerValidationResult(
                ok=ok,
                has_document_id_token=has_document_id_token,
                has_metadata_summary=has_metadata_summary,
                has_layout_summary=has_layout_summary,
                missing_fields=missing_fields,
            )

        has_metadata_summary = self.METADATA_SECTION_TOKEN in text
        if not has_metadata_summary:
            missing_fields.append("metadata_summary")

        has_layout_summary = self.LAYOUT_SECTION_TOKEN in text
        if not has_layout_summary:
            missing_fields.append("layout_summary")

        if normalized_mode == "document_id":
            expected = (expected_document_id or "").strip()
            has_document_id_token = bool(
                re.search(
                    rf"(?m)^1\.\s*검색된 도면 id:\s*{re.escape(expected)}\s*$",
                    text,
                )
            )
        elif normalized_mode == "general":
            has_document_id_token = bool(self.GENERAL_ID_TOKEN_RE.search(text))
        else:
            raise ValueError(f"Unsupported validation mode: {mode}")

        if not has_document_id_token:
            missing_fields.append("document_id_token")

        ok = (
            is_non_empty
            and has_document_id_token
            and has_metadata_summary
            and has_layout_summary
        )
        return AnswerValidationResult(
            ok=ok,
            has_document_id_token=has_document_id_token,
            has_metadata_summary=has_metadata_summary,
            has_layout_summary=has_layout_summary,
            missing_fields=missing_fields,
        )

    def _build_safe_default_answer(
        self, mode: str, expected_document_id: Optional[str] = None
    ) -> str:
        normalized_mode = mode.strip().lower()
        if normalized_mode == "document_id":
            document_id = (expected_document_id or "정보 생성 불가").strip() or "정보 생성 불가"
            return (
                f"1. 검색된 도면 id: {document_id}\n\n"
                "2. 도면 기본 정보 📊\n"
                "- 응답 형식 검증 실패로 요약 생성 불가\n\n"
                "3. 도면 공간 구성 설명 🧩\n"
                "- 응답 형식 검증 실패로 설명 생성 불가"
            )
        if normalized_mode == "general":
            return (
                "1. 검색된 도면 id: 정보 생성 불가\n\n"
                "2. 도면 기본 정보 📊\n"
                "- 응답 형식 검증 실패로 요약 생성 불가\n\n"
                "3. 도면 공간 구성 설명 🧩\n"
                "- 응답 형식 검증 실패로 설명 생성 불가"
            )
        if normalized_mode == "no_match":
            return (
                "조건을 만족하는 도면 총 개수: 0\n"
                "검색된 도면 id: 없음\n"
                "요청 조건과 일치하는 도면이 존재하지 않습니다."
            )
        raise ValueError(f"Unsupported validation mode: {mode}")

    def _run_validated_generation(
        self,
        mode: str,
        generate_fn: Callable[[], str],
        expected_document_id: Optional[str] = None,
    ) -> str:
        try:
            answer = self._normalize_generated_answer(generate_fn())
        except Exception:
            self.logger.exception("answer_generation_exception mode=%s attempt=0", mode)
            if self.answer_validation_safe_fallback:
                fallback = self._build_safe_default_answer(
                    mode=mode,
                    expected_document_id=expected_document_id,
                )
                self.logger.warning(
                    "answer_validation_fallback mode=%s retries=%d reason=generation_error",
                    mode,
                    self.answer_validation_retry_max,
                )
                return fallback
            raise
        if not self.answer_validation_enabled:
            return answer

        validation_start = time.perf_counter()
        try:
            result = self._validate_answer_format(
                answer=answer,
                mode=mode,
                expected_document_id=expected_document_id,
            )
        except Exception:
            self.logger.exception("answer_validation_exception mode=%s attempt=0", mode)
            return answer
        validation_ms = int((time.perf_counter() - validation_start) * 1000)

        if result.ok:
            self.logger.info(
                "answer_validation_pass mode=%s attempt=0 latency_ms=%d",
                mode,
                validation_ms,
            )
            return answer

        self.logger.warning(
            "answer_validation_fail mode=%s attempt=0 missing_fields=%s latency_ms=%d",
            mode,
            ",".join(result.missing_fields) or "none",
            validation_ms,
        )

        last_answer = answer
        for attempt in range(1, self.answer_validation_retry_max + 1):
            self.logger.warning("answer_validation_retry mode=%s attempt=%d", mode, attempt)
            try:
                last_answer = self._normalize_generated_answer(generate_fn())
            except Exception:
                self.logger.exception("answer_generation_exception mode=%s attempt=%d", mode, attempt)
                continue
            retry_validation_start = time.perf_counter()
            try:
                retry_result = self._validate_answer_format(
                    answer=last_answer,
                    mode=mode,
                    expected_document_id=expected_document_id,
                )
            except Exception:
                self.logger.exception(
                    "answer_validation_exception mode=%s attempt=%d", mode, attempt
                )
                continue
            retry_validation_ms = int((time.perf_counter() - retry_validation_start) * 1000)
            if retry_result.ok:
                self.logger.info(
                    "answer_validation_pass mode=%s attempt=%d latency_ms=%d",
                    mode,
                    attempt,
                    retry_validation_ms,
                )
                return last_answer
            self.logger.warning(
                "answer_validation_fail mode=%s attempt=%d missing_fields=%s latency_ms=%d",
                mode,
                attempt,
                ",".join(retry_result.missing_fields) or "none",
                retry_validation_ms,
            )

        if self.answer_validation_safe_fallback:
            fallback = self._build_safe_default_answer(
                mode=mode,
                expected_document_id=expected_document_id,
            )
            self.logger.warning(
                "answer_validation_fallback mode=%s retries=%d",
                mode,
                self.answer_validation_retry_max,
            )
            return fallback
        return last_answer

    def _normalize_hybrid_weights(
        self, vector_weight: float, text_weight: float
    ) -> tuple[float, float]:
        vector = float(vector_weight)
        text = float(text_weight)
        if vector < 0 or text < 0:
            raise ValueError("vector_weight and text_weight must be non-negative.")
        total = vector + text
        if total == 0:
            raise ValueError("At least one hybrid weight must be greater than zero.")
        return vector / total, text / total

    def _analyze_query(self, query: str) -> dict:
        """ 
        LLM: query -> JSON (filters, documents)
        """
        word_rules_text = json.dumps(self.word_dict, ensure_ascii=False, indent=2)
        system_prompt = (
            "You are a query analyzer for architectural floorplan retrieval.\n"
            "Return ONLY valid JSON in this exact schema:\n"
            "{\n"
            '  "filters": {\n'
            '    "windowless_count": {"op": "이상|이하|초과|미만|동일", "val": "integer"} (optional),\n'
            '    "balcony_ratio": {"op": "이상|이하|초과|미만|동일", "val": "number"} (optional),\n'
            '    "living_room_ratio": {"op": "이상|이하|초과|미만|동일", "val": "number"} (optional),\n'
            '    "bathroom_ratio": {"op": "이상|이하|초과|미만|동일", "val": "number"} (optional),\n'
            '    "kitchen_ratio": {"op": "이상|이하|초과|미만|동일", "val": "number"} (optional),\n'
            '    "structure_type": "string(optional)",\n'
            '    "bay_count": "integer(optional)",\n'
            '    "room_count": "integer(optional)",\n'
            '    "bathroom_count": "integer(optional)",\n'
            '    "compliance_grade": "string(optional)",\n'
            '    "ventilation_grade": "string(optional)",\n'
            '    "has_special_space": "boolean(optional)",\n'
            '    "has_etc_space": "boolean(optional)"\n'
            "  },\n"
            '  "documents": "string(required)"\n'
            "}\n"
            "Map explicit, structured constraints to filters.\n"
            "Put abstract or descriptive intent into documents.\n"
            "If no filter applies, use an empty filters object.\n"
            "Synonym and classification rules (JSON):\n"
            f"{word_rules_text}\n"
            "Prompt rules:\n"
            "1) Normalization Rule: When interpreting the user's query, map terms to standardized space names using normalization_rules.\n"
            "2) Etc. Space Classification: If a mapped/mentioned space is in special_classification['기타공간'] "
            "(or equivalent category_groups['기타공간']), include \"has_etc_space\": true in filters.\n"
            "3) Special Space Classification: If a mapped/mentioned space is in special_classification['특화공간'] "
            "(or equivalent category_groups['특화공간']), include \"has_special_space\": true in filters.\n"
            "Only include these boolean fields when the condition is met."
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                response_format={"type": "json_object"},
            )
            raw_text = (response.choices[0].message.content or "").strip()
            if not raw_text:
                raise ValueError("Analyzer returned empty content")

            cleaned = raw_text.replace("```json", "").replace("```", "").strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start == -1 or end == -1 or start > end:
                raise ValueError("Analyzer JSON object not found")
            parsed = json.loads(cleaned[start : end + 1])

            raw_filters = parsed.get("filters", {})
            if not isinstance(raw_filters, dict):
                raise ValueError("Invalid analyzer JSON schema")

            documents = (
                parsed.get("documents")
                or parsed.get("search_text")
                or parsed.get("context")
                or query
            )
            documents = str(documents).strip()
            if not documents:
                documents = query
            documents = self._augment_documents_from_query(query, documents)

            filters = self._normalize_filters(raw_filters)
            filters = self._augment_filters_from_query(query, filters)
            filters = self._drop_implicit_ratio_filters(query, filters)
            return {"filters": filters, "documents": documents, "raw_query": query}
        except (json.JSONDecodeError, ValueError, KeyError, TypeError, IndexError):
            self.logger.warning(
                "Analyzer JSON parsing failed. Falling back to keyword-only search."
            )
            return {"filters": {}, "documents": query, "raw_query": query}

    def _normalize_filters(self, raw_filters: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in raw_filters.items():
            canonical_key = self.FILTER_ALIASES.get(key, key)
            if canonical_key not in self.ALLOWED_FILTER_COLUMNS:
                continue
            coerced = self._coerce_filter_value(canonical_key, value)
            if coerced is not None:
                normalized[canonical_key] = coerced

        for ratio_key in self.FLOAT_FILTERS:
            if ratio_key in normalized:
                continue
            op = raw_filters.get(f"{ratio_key}_op", raw_filters.get(f"{ratio_key}_operator"))
            val = raw_filters.get(f"{ratio_key}_val", raw_filters.get(f"{ratio_key}_value"))
            if op is None and val is None:
                continue
            coerced = self._coerce_filter_value(ratio_key, {"op": op, "val": val})
            if coerced is not None:
                normalized[ratio_key] = coerced
        return normalized

    def _coerce_filter_value(self, key: str, value: Any) -> Any:
        if value is None:
            return None

        if key in self.INT_FILTERS:
            if isinstance(value, bool):
                return None
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str):
                match = re.search(r"-?\d+", value)
                if match:
                    return int(match.group())
            return None

        if key in self.FLOAT_FILTERS:
            ratio_filter = self._coerce_ratio_filter(value)
            if ratio_filter is not None:
                return ratio_filter
            return None

        if key in self.BOOL_FILTERS:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                v = value.strip().lower()
                if v in {"true", "1", "yes"}:
                    return True
                if v in {"false", "0", "no"}:
                    return False
            return None

        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned if cleaned else None
        return str(value)

    def _coerce_ratio_filter(self, value: Any) -> Optional[dict[str, Any]]:
        if value is None or isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            return {"op": "동일", "val": float(value)}

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            op_match = re.search(r"(이상|이하|초과|미만|동일)", text)
            num_match = re.search(r"-?\d+(\.\d+)?", text)
            if num_match:
                op = self._normalize_ratio_operator(op_match.group(1) if op_match else None)
                return {"op": op or "동일", "val": float(num_match.group())}
            return None

        if isinstance(value, dict):
            raw_op = value.get("op", value.get("operator"))
            raw_val = value.get("val", value.get("value"))
            val = self._parse_float(raw_val)
            op = self._normalize_ratio_operator(raw_op)
            if raw_op is None and val is None:
                return None
            return {"op": op, "val": val}

        return None

    def _normalize_ratio_operator(self, op: Any) -> Optional[str]:
        if not isinstance(op, str):
            return None
        cleaned = op.strip()
        return cleaned if cleaned in self.VALID_RATIO_OPERATORS else None

    def _parse_float(self, value: Any) -> Optional[float]:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"-?\d+(\.\d+)?", value)
            if match:
                return float(match.group())
        return None

    def _ensure_ratio_cmp_function(self) -> None:
        sql = """
        CREATE OR REPLACE FUNCTION public.ratio_cmp(
            field_val double precision,
            op text,
            val double precision
        ) RETURNS boolean
        LANGUAGE sql
        IMMUTABLE
        AS $$
        SELECT CASE
            WHEN op IS NULL OR val IS NULL THEN TRUE
            WHEN op = '이상' THEN field_val >= val
            WHEN op = '이하' THEN field_val <= val
            WHEN op = '초과' THEN field_val > val
            WHEN op = '미만' THEN field_val < val
            WHEN op = '동일' THEN field_val = val
            ELSE TRUE
        END
        $$;
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            self.logger.exception("Failed to create ratio_cmp function.")

    def _augment_filters_from_query(
        self, query: str, filters: dict[str, Any]
    ) -> dict[str, Any]:
        augmented = dict(filters)

        if "structure_type" not in augmented:
            if "판상형" in query:
                augmented["structure_type"] = "판상형"
            elif "타워형" in query:
                augmented["structure_type"] = "타워형"
            elif "혼합형" in query:
                augmented["structure_type"] = "혼합형"
            elif "복도형" in query:
                augmented["structure_type"] = "복도형"

        if "bay_count" not in augmented:
            match = re.search(r"(\d+)\s*베이", query)
            if match:
                augmented["bay_count"] = int(match.group(1))

        if "room_count" not in augmented:
            match = re.search(r"방\s*(\d+)\s*개", query) or re.search(
                r"(\d+)\s*개\s*방", query
            )
            if match:
                augmented["room_count"] = int(match.group(1))

        if "bathroom_count" not in augmented:
            match = re.search(r"(욕실|화장실)\s*(\d+)\s*개", query) or re.search(
                r"(\d+)\s*개\s*(욕실|화장실)", query
            )
            if match:
                numeric = re.search(r"\d+", match.group(0))
                if numeric:
                    augmented["bathroom_count"] = int(numeric.group())

        if "ventilation_grade" not in augmented and "환기" in query:
            if "우수" in query:
                augmented["ventilation_grade"] = "우수"
            elif "보통" in query:
                augmented["ventilation_grade"] = "보통"
            elif "미흡" in query:
                augmented["ventilation_grade"] = "미흡"

        return augmented

    def _drop_implicit_ratio_filters(
        self, query: str, filters: dict[str, Any]
    ) -> dict[str, Any]:
        
        if re.search(r"(%|퍼센트|비율|ratio|이상|이하|초과|미만|동일)", query, flags=re.IGNORECASE):
            return filters

        sanitized = dict(filters)
        for key in self.FLOAT_FILTERS:
            sanitized.pop(key, None)
        return sanitized

    def _is_floorplan_image_name(self, query: str) -> bool:
        return bool(self.FLOORPLAN_IMAGE_NAME_RE.fullmatch(query.strip()))

    def _augment_documents_from_query(self, query: str, documents: str) -> str:
        base = str(documents or "").strip()
        text = str(query or "")
        if not base:
            return base

        if not re.search(r"(발코니|베란다)", text, flags=re.IGNORECASE):
            return base

        if not re.search(
            r"(활용|활용도|연결|채광|좋|우수|양호|넓)",
            text,
            flags=re.IGNORECASE,
        ):
            return base

        intent_terms = [
            "발코니 활용 가능",
            "발코니 활용도가 높",
            "외부 공간으로 활용",
            "외부 공간과의 연결이 원활",
            "발코니 채광이 좋",
            "발코니는 넓고",
        ]
        joined = " OR ".join(f'"{term}"' for term in intent_terms)
        return f"({base}) OR ({joined})"

    def _extract_document_signals(self, document: str) -> list[dict[str, str]]:
        text = str(document or "")
        if not text.strip():
            return []

        signals: list[dict[str, str]] = []
        for canonical_key, aliases in self.DOCUMENT_SIGNAL_KEY_ALIASES.items():
            match_value: Optional[str] = None
            match_source: Optional[str] = None
            for alias in aliases:
                pattern = rf"{re.escape(alias)}\s*은\(는\)\s*([^\n.]+)"
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    match_value = re.sub(r"\s+", " ", match.group(1)).strip()
                    match_source = re.sub(r"\s+", " ", match.group(0)).strip()
                    break
            if match_value:
                normalized_value = self._normalize_signal_value_for_display(
                    canonical_key, match_value
                )
                signals.append(
                    {
                        "key": canonical_key,
                        "label": self.DOCUMENT_SIGNAL_KR_LABELS[canonical_key],
                        "value": match_value,
                        "display_value": normalized_value,
                        "source": match_source or "",
                    }
                )
        return signals

    def _infer_signal_polarity(self, value: str) -> Optional[str]:
        normalized = re.sub(r"\s+", "", str(value or ""))
        if not normalized:
            return None
        if any(token in normalized for token in self.NEGATIVE_SIGNAL_WORDS):
            return "negative"
        if any(token in normalized for token in self.POSITIVE_SIGNAL_WORDS):
            return "positive"
        return None

    def _normalize_signal_value_for_display(self, key: str, value: str) -> str:
        polarity = self._infer_signal_polarity(value)
        if polarity == "positive":
            return self.SIGNAL_POSITIVE_DISPLAY.get(key, "좋음")
        if polarity == "negative":
            return self.SIGNAL_NEGATIVE_DISPLAY.get(key, "부족함")
        cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
        return cleaned if cleaned else "확인 필요"

    def _extract_query_signal_preferences(self, query: str) -> dict[str, str]:
        text = str(query or "")
        if not text.strip():
            return {}

        positive_hint = bool(
            re.search(r"(좋|우수|적정|적합|양호|충분|넉넉|밝)", text, flags=re.IGNORECASE)
        )
        negative_hint = bool(
            re.search(r"(나쁘|부족|미흡|부적합|불합격|어둡|없)", text, flags=re.IGNORECASE)
        )
        if not positive_hint and not negative_hint:
            return {}

        preferred = "positive" if positive_hint and not negative_hint else None
        if negative_hint and not positive_hint:
            preferred = "negative"
        if preferred is None:
            return {}

        preferences: dict[str, str] = {}
        if re.search(r"(채광|lighting)", text, flags=re.IGNORECASE):
            preferences["lighting"] = preferred
        if re.search(r"(수납공간|수납|storage)", text, flags=re.IGNORECASE):
            preferences["storage"] = preferred
        if re.search(r"(환기|ventilation)", text, flags=re.IGNORECASE):
            preferences["ventilation"] = preferred
        if re.search(r"(가족\s*융화|family_harmony)", text, flags=re.IGNORECASE):
            preferences["family_harmony"] = preferred
        if re.search(r"(발코니|베란다)", text, flags=re.IGNORECASE):
            preferences["balcony_usage"] = preferred
        return preferences

    def _infer_balcony_utilization_polarity(self, document: str) -> Optional[str]:
        text = str(document or "")
        if not text.strip():
            return None

        segments = re.split(r"[.\n]", text)
        balcony_segments = [
            segment for segment in segments if re.search(r"(발코니|베란다)", segment, re.IGNORECASE)
        ]
        if not balcony_segments:
            return None

        balcony_text = " ".join(segment.strip() for segment in balcony_segments if segment.strip())
        normalized = re.sub(r"\s+", " ", balcony_text)
        if self.BALCONY_NEGATIVE_HINT_RE.search(normalized):
            return "negative"
        if self.BALCONY_POSITIVE_HINT_RE.search(normalized):
            return "positive"
        return None

    def _rerank_by_query_signal_preferences(
        self, docs: list[tuple[Any, ...]], query: str
    ) -> list[tuple[Any, ...]]:
        preferences = self._extract_query_signal_preferences(query)
        if not preferences or not docs:
            return docs

        rescored_docs: list[tuple[float, tuple[Any, ...]]] = []
        for row in docs:
            base_score = float(row[16] if len(row) > 16 and row[16] is not None else 0.0)
            document_text = str(row[2] if len(row) > 2 else "")
            signals = self._extract_document_signals(document_text)
            signal_map = {signal["key"]: signal["value"] for signal in signals}

            bonus = 0.0
            for key, desired in preferences.items():
                if key == "balcony_usage":
                    polarity = self._infer_balcony_utilization_polarity(document_text)
                    if polarity == desired:
                        bonus += 0.08
                    elif polarity and polarity != desired:
                        bonus -= 0.04
                    continue
                value = signal_map.get(key)
                if not value:
                    continue
                polarity = self._infer_signal_polarity(value)
                if polarity == desired:
                    bonus += 0.08
                elif polarity and polarity != desired:
                    bonus -= 0.04

            adjusted_row = (*row[:-1], base_score + bonus) if len(row) > 0 else row
            rescored_docs.append((base_score + bonus, adjusted_row))

        rescored_docs.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in rescored_docs]

    def _retrieve_by_document_id(self, document_id: str) -> Optional[tuple]:
        sql = """
            SELECT f.id AS floorplan_id, f.name AS document_id,
            fa.analysis_description AS document,
            fa.windowless_count, fa.balcony_ratio, fa.living_room_ratio, fa.bathroom_ratio, fa.kitchen_ratio,
            fa.structure_type, fa.bay_count, fa.room_count, fa.bathroom_count,
            fa.compliance_grade, fa.ventilation_quality AS ventilation_grade,
            fa.has_special_space, fa.has_etc_space,
            1.0::double precision AS similarity
            FROM floorplan_analysis fa
            JOIN floorplan f ON fa.floorplan_id = f.id
            WHERE LOWER(f.name) = LOWER(%s)
            LIMIT 1
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (document_id.strip(),))
            return cur.fetchone()

    def _row_to_candidate(self, row: tuple[Any, ...], rank: int) -> dict[str, Any]:
        (
            floorplan_id,
            document_id,
            document,
            windowless_count,
            balcony_ratio,
            living_room_ratio,
            bathroom_ratio,
            kitchen_ratio,
            structure_type,
            bay_count,
            room_count,
            bathroom_count,
            compliance_grade,
            ventilation_grade,
            has_special_space,
            has_etc_space,
            similarity,
        ) = row
        return {
            "rank": rank,
            "floorplan_id": floorplan_id,
            "document_id": document_id,
            "metadata": {
                "room_count": room_count,
                "bathroom_count": bathroom_count,
                "bay_count": bay_count,
                "living_room_ratio": living_room_ratio,
                "kitchen_ratio": kitchen_ratio,
                "bathroom_ratio": bathroom_ratio,
                "balcony_ratio": balcony_ratio,
                "windowless_count": windowless_count,
                "structure_type": structure_type,
                "ventilation_quality": ventilation_grade,
                "has_special_space": has_special_space,
                "has_etc_space": has_etc_space,
                "compliance_grade": compliance_grade,
            },
            "document": document,
            "document_signals": self._extract_document_signals(document),
            "similarity": similarity,
        }

    def _generate_document_id_answer(self, document_id: str, doc: tuple[Any, ...]) -> str:
        candidate = self._row_to_candidate(doc, rank=1)
        candidate_json = json.dumps(candidate, ensure_ascii=False, indent=2)

        system_prompt = """ You are a **specialized sLLM for architectural floor plan retrieval**.

Your role is to, for each retrieved floor plan:
1. Explain **why this floor plan was selected**,
2. Describe the **metadata of the floor plan in a neutral manner**, and
3. Summarize each floor plan’s **document content clearly and concisely**, without interpretation.

You must **never perform judgment, evaluation, recommendation, or interpretation**.

**Absolute Prohibitions**
- Do not judge the suitability, quality, or problems of the floor plan.
- Do not provide design advice or suggestions for improvement.
- Do not interpret legal regulations or permit/approval feasibility.
- Do not repeat evaluation results already present in the metadata within the document summary.

========================
Output Format (Must Be Preserved, Repeated for Each Floor Plan)
- All content must be written in Korean.
========================

1. 검색된 도면 id: {document_id}

2. 도면 기본 정보 📊
■ 공간 구성 여부의 값은 다음 표현으로 고정한다.
- true → 존재
- false → 없음

출력 형식(고정):
■ 공간 개수
    - 방 개수: {room_count}
    - 화장실 개수: {bathroom_count}
    - Bay 개수: {bay_count}
    - 무창 공간 개수: {windowless_count}
■ 전체 면적 대비 공간 비율 (%)
    - 거실 공간: {living_room_ratio}
    - 주방 공간: {kitchen_ratio}
    - 욕실 공간: {bathroom_ratio}
    - 발코니 공간: {balcony_ratio}
■ 구조 및 성능
    - 건물 구조 유형: {structure_type}
    - 환기: {ventilation_quality}
■ 공간 구성 여부
    - 특화 공간: {has_special_space}
    - 기타 공간: {has_etc_space}
■ 종합 평가
    - 평가 결과: {compliance_grade}

3. 도면 공간 구성 설명 🧩
Since the document is **internal evaluation text**,
it must be restructured into a form that is easy for users to read according to the rules below.

**Organization Rules:**
* Use **only factual information** contained in the original text.
* Remove document-meta expressions such as *“is stated,” “is mentioned,”* or *“is described.”*
* Do not use Korean meta expressions like "기재되어 있습니다", "언급되어 있습니다", "서술되어 있습니다".
* Remove **only** result-oriented judgment expressions such as internal criteria, suitability determinations, or pass/fail statements.
* Sentences that describe a **state or condition**, such as *“insufficient”* or *“improvement is needed,”* are considered factual descriptions and are **allowed**.
* Merge sentences with the same meaning into one.
* Sentences may be rephrased into natural English **without changing their meaning**.
* Do **not** include advice, criteria comparisons, or design suggestions.
* If the original document contains content related to the following items, that content **must be included in the overall summary sentence*.
  • storage -> 수납공간
  • lighting -> 채광
  • family_harmony -> 가족 융화
* If `document_signals` are provided, all of them must be included in the first overall summary sentence using Korean labels and values.
* Do not drop value polarity. Keep positive/negative wording from `document_signals` (e.g., 우수, 적정, 부족, 미흡, 부적합, 불합격).
* Prefer `display_value` for user-facing wording (e.g., 채광: 좋음, 수납공간: 넉넉함).
* The overall summary must start with these two fixed lines:
  {bay_count}Bay {structure_type} 구조입니다.
  채광: {display_value}{(근거)}, 환기: {display_value}{(근거)}, 가족 융화: {display_value}, 수납공간: {display_value}{(근거)}으로 정리됩니다.
* Add evidence parentheses only when explicit evidence exists in the original document. If no explicit evidence exists, omit parentheses.
* Never output placeholder evidence text such as "근거 없음" or "확인 필요".
* In each evidence parentheses, write only concise evidence text (e.g., 안방 외기창 미확보). Do not include prefixes like "적합:" or "부적합:".
* Do not repeat the same fact twice. If the same evidence appears in the summary sentence, do not repeat it in later sentences.
* The second summary sentence should include only additional non-duplicate facts that are not already stated in the first summary sentence.

**Output Format:**
* Overall summary: 1–2 sentences (describing overall spatial characteristics only)
* Followed by space-by-space descriptions
* One sentence per space
* If multiple spaces have exactly the same description, merge them into one line using slash-joined labels.
* When merged labels share the same base name, keep the base only once.
  Example: `침실1/침실2` -> `침실1/2`, `기타1/기타2/기타3` -> `기타1/2/3`.
  Example: `기타1/2/3/4/5/6: 기타 공간은 기능이 명확하지 않으며, 창문이 없어 채광이 부족합니다.`

출력 예시 형식:
3Bay 판상형 구조입니다.
채광: 부족함(안방 외기창 미확보), 환기: 좋음(주방 환기창 확보), 가족 융화: 적합, 수납공간: 부족함(수납공간 비율 10% 미만)으로 정리됩니다.
안방 외기창이 없고, 욕실 환기창이 없습니다.
■ 거실: 중앙에 위치하여 가족이 모일 수 있는 공간으로 적합합니다.
■ 침실: 개인적인 공간으로 분리되어 적절하게 배치되어 있습니다.
■ 주방/식당: 환기창이 있어 환기가 우수합니다.
■ 화장실: 환기창이 없어 환기 측면에서 개선이 필요합니다.
■ 발코니: 외부 공간으로의 활용도가 높습니다.
"""

        user_content = (
            f"입력 document_id:\n{document_id.strip()}\n\n"
            f"도면 데이터(JSON):\n{candidate_json}\n\n"
            "JSON의 `document_signals` 항목은 3번의 전체 요약 문장에 반드시 모두 반영하세요.\n"
            "신호 값은 `display_value`를 우선 사용해 사용자 친화적으로 표현하세요.\n"
            "요약 시작은 `NBay 구조입니다.` 다음 줄 `채광/환기/가족 융화/수납공간` 고정 템플릿을 따르세요.\n"
            "`근거 없음`, `확인 필요` 같은 자리표시자 표현은 절대 사용하지 마세요.\n"
            "요약 2번째 줄에서 언급한 근거는 다음 문장에서 중복해서 반복하지 마세요.\n"
            "출력은 반드시 1, 2, 3번 섹션만 포함하고 추가 문장을 절대 출력하지 마세요.\n"
            "반드시 단일 도면 기준으로만 출력하고, "
            f"첫 줄은 정확히 `1. 검색된 도면 id: {document_id.strip()}` 형식을 사용하세요."
        )

        def _call_llm() -> str:
            response = self.client.chat.completions.create(
                model="gpt-5.2-2025-12-11",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
            )
            return (response.choices[0].message.content or "").strip()

        return self._run_validated_generation(
            mode="document_id",
            generate_fn=_call_llm,
            expected_document_id=document_id.strip(),
        )

    def _build_filter_where_parts(self, filters: dict[str, Any]) -> tuple[str, list[Any]]:
        where_clauses = []
        params: list[Any] = []

        for column in self.ALLOWED_FILTER_COLUMNS:
            value = filters.get(column)
            if value is None:
                continue
            db_col = f"fa.{self._DB_COLUMN_MAP.get(column, column)}"
            if column in self.FLOAT_FILTERS:
                op = value.get("op") if isinstance(value, dict) else None
                val = value.get("val") if isinstance(value, dict) else None
                where_clauses.append(f"ratio_cmp({db_col}::double precision, %s, %s)")
                params.extend([op, val])
            else:
                where_clauses.append(f"{db_col} = %s")
                params.append(value)

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        return where_sql, params

    def _retrieve_hybrid(self, query_json: dict, top_k: int = 50) -> list:
        """
        Generate embedding -> build query -> execute DB query -> return results
        """
        filters = query_json.get("filters", {}) or {}
        documents = query_json.get("documents", "") or ""
        raw_query = query_json.get("raw_query", "") or ""
        semantic_query = f"{documents} {raw_query}".strip() or raw_query or documents
        text_query = str(documents).strip() or str(raw_query).strip()

        embedding = self.embedding_manager.embed_text(semantic_query)
        embedding_vector = "[" + ",".join(map(str, embedding)) + "]"

        where_sql, filter_params = self._build_filter_where_parts(filters)
        params = [
            embedding_vector,
            text_query,
            *filter_params,
            self.vector_weight,
            self.text_weight,
            top_k,
        ]

        sql = f"""
            WITH scored AS (
                SELECT f.id AS floorplan_id, f.name AS document_id,
                fa.analysis_description AS document,
                fa.windowless_count, fa.balcony_ratio, fa.living_room_ratio, fa.bathroom_ratio, fa.kitchen_ratio,
                fa.structure_type, fa.bay_count, fa.room_count, fa.bathroom_count,
                fa.compliance_grade, fa.ventilation_quality AS ventilation_grade,
                fa.has_special_space, fa.has_etc_space,
                (1 - (fa.embedding <=> %s::vector)) AS vector_similarity,
                ts_rank_cd(
                    to_tsvector('simple', COALESCE(fa.analysis_description, '')),
                    websearch_to_tsquery('simple', %s)
                ) AS text_score
                FROM floorplan_analysis fa
                JOIN floorplan f ON fa.floorplan_id = f.id
                WHERE {where_sql}
            )
            SELECT floorplan_id, document_id, document,
            windowless_count, balcony_ratio, living_room_ratio, bathroom_ratio, kitchen_ratio,
            structure_type, bay_count, room_count, bathroom_count,
            compliance_grade, ventilation_grade, has_special_space, has_etc_space,
            (%s * vector_similarity + %s * text_score) AS similarity
            FROM scored
            ORDER BY similarity DESC
            LIMIT %s
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        except Exception as exc:
            self.conn.rollback()
            if text_query:
                self._log_event(
                    event="retrieve_text_query_fallback",
                    level=logging.WARNING,
                    reason="text_query_parse_or_rank_error",
                    text_query=text_query,
                    filter_count=len(filter_params),
                    error=str(exc),
                )
                fallback_params = [
                    embedding_vector,
                    *filter_params,
                    self.vector_weight,
                    self.text_weight,
                    top_k,
                ]
                fallback_sql = f"""
                    WITH scored AS (
                        SELECT f.id AS floorplan_id, f.name AS document_id,
                        fa.analysis_description AS document,
                        fa.windowless_count, fa.balcony_ratio, fa.living_room_ratio, fa.bathroom_ratio, fa.kitchen_ratio,
                        fa.structure_type, fa.bay_count, fa.room_count, fa.bathroom_count,
                        fa.compliance_grade, fa.ventilation_quality AS ventilation_grade,
                        fa.has_special_space, fa.has_etc_space,
                        (1 - (fa.embedding <=> %s::vector)) AS vector_similarity,
                        0.0::double precision AS text_score
                        FROM floorplan_analysis fa
                        JOIN floorplan f ON fa.floorplan_id = f.id
                        WHERE {where_sql}
                    )
                    SELECT floorplan_id, document_id, document,
                    windowless_count, balcony_ratio, living_room_ratio, bathroom_ratio, kitchen_ratio,
                    structure_type, bay_count, room_count, bathroom_count,
                    compliance_grade, ventilation_grade, has_special_space, has_etc_space,
                    (%s * vector_similarity + %s * text_score) AS similarity
                    FROM scored
                    ORDER BY similarity DESC
                    LIMIT %s
                """
                with self.conn.cursor() as cur:
                    cur.execute(fallback_sql, fallback_params)
                    return cur.fetchall()
            raise

    def _count_matches(self, filters: dict[str, Any], documents: str = "") -> int:
        where_sql, params = self._build_filter_where_parts(filters)

        normalized_documents = str(documents or "").strip()
        if normalized_documents:
            where_sql = (
                f"{where_sql} AND "
                "to_tsvector('simple', COALESCE(fa.analysis_description, '')) @@ websearch_to_tsquery('simple', %s)"
            )
            params = [*params, normalized_documents]
        sql = f"SELECT COUNT(*) FROM floorplan_analysis fa JOIN floorplan f ON fa.floorplan_id = f.id WHERE {where_sql}"
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                matched_count = int(cur.fetchone()[0])
            if normalized_documents and matched_count == 0 and filters:
                self._log_event(
                    event="count_matches_zero_text_fallback",
                    level=logging.INFO,
                    reason="strict_text_zero_match",
                    text_query=normalized_documents,
                    filter_count=len(filters),
                )
                fallback_where_sql, fallback_params = self._build_filter_where_parts(filters)
                fallback_sql = f"SELECT COUNT(*) FROM floorplan_analysis fa JOIN floorplan f ON fa.floorplan_id = f.id WHERE {fallback_where_sql}"
                with self.conn.cursor() as cur:
                    cur.execute(fallback_sql, fallback_params)
                    return int(cur.fetchone()[0])
            return matched_count
        except Exception as exc:
            self.conn.rollback()
            if normalized_documents:
                self._log_event(
                    event="count_matches_text_query_fallback",
                    level=logging.WARNING,
                    reason="text_query_parse_error",
                    text_query=normalized_documents,
                    error=str(exc),
                )
                fallback_where_sql, fallback_params = self._build_filter_where_parts(filters)
                fallback_sql = f"SELECT COUNT(*) FROM floorplan_analysis fa JOIN floorplan f ON fa.floorplan_id = f.id WHERE {fallback_where_sql}"
                with self.conn.cursor() as cur:
                    cur.execute(fallback_sql, fallback_params)
                    return int(cur.fetchone()[0])
            raise

    def _generate_answer(
        self, query: str, query_json: dict, docs: list, total_match_count: int
    ) -> str:
        """
        Format retrieved docs as documents and send to the LLM to generate the answer
        """
        if not docs:
            return self._generate_validated_no_match_answer(
                total_match_count=total_match_count
            )

        filters_json = json.dumps(query_json.get("filters", {}), ensure_ascii=False, indent=2)
        retrieved_ids = [row[1] for row in docs]
        id_list_text = ", ".join(str(rid) for rid in retrieved_ids)
        top_docs = docs[:3]

        representative_ids = [row[1] for row in top_docs]
        representative_title = "대표 도면 id(상위 3개)"
        candidates = [self._row_to_candidate(row, rank) for rank, row in enumerate(top_docs, start=1)]
        candidates_json = json.dumps(candidates, ensure_ascii=False, indent=2)

        system_prompt = """You are a **specialized sLLM for architectural floor plan retrieval**.

Your role is to, for each retrieved floor plan:

1. Explain **why this floor plan was selected**,
2. Describe the **metadata of the floor plan in a neutral manner**, and
3. Summarize each floor plan’s **document content clearly and concisely**, without interpretation.

You must **never perform judgment, evaluation, recommendation, or interpretation**.

**Absolute Prohibitions**
- Do not judge the suitability, quality, or problems of the floor plan.
- Do not provide design advice or suggestions for improvement.
- Do not interpret legal regulations or permit/approval feasibility.
- Do not repeat evaluation results already present in the metadata within the document summary.

========================
Output Format (Must Be Preserved, Repeated for Each Floor Plan)
- All content must be written in Korean.
========================

조건을 만족하는 도면 총 개수: {total_count}
검색된 도면 id: {id_list}

Repeat the format below **for each representative floor plan**.
[도면 #{rank}] {document_id}

1. 도면 선택 근거 🔍
This section outputs **only the correspondence between the user’s search conditions and the floor plan information**.

**[General Rules]**
* All item labels must be written in **Korean**.
* **Internal field names** (e.g., `bay_count`) must **never** be output.
* Do **not** abbreviate or summarize values.
* Do **not** use meta expressions such as “request,” “preference,” or “treated as a condition.”
* Do **not** generate any additional explanatory sentences.

**[Rules for Writing “Search Conditions”]**
* “Search Conditions” must list the user’s input query, refined while preserving its original meaning.
* Conditions that are not explicitly stated in the user’s query must **never** be added to “Search Conditions.”

**[Rules for Generating “Matched Conditions”]**
* “Matched Conditions” must include each user-specified condition that satisfies **at least one** of the following:
  1. It can be directly verified from the floor plan metadata.
  2. An identical or semantically equivalent expression is explicitly stated in the document description.
* Conditions supported by the document may be included **even if no corresponding metadata field exists**.

* Examples of **document-based conditions**:
  • "발코니 활용 가능" ↔ "외부 공간으로 활용", "활용도가 높음"
  • "주방 환기창 존재" ↔ "주방/식당에 환기창이 있음"

출력 형식(고정):
- 찾는 조건: {사용자 조건을 한국어 표현으로 나열}
- 일치 조건: {도면 메타데이터 및 document에서 확인된 일치 항목을 한국어 항목명=값 형태로 나열}

2. 도면 기본 정보 📊
■ 공간 구성 여부의 값은 다음 표현으로 고정한다.
- true → 존재
- false → 없음

출력 형식(고정):
■ 공간 개수
    - 방 개수: {room_count}
    - 화장실 개수: {bathroom_count}
    - Bay 개수: {bay_count}
    - 무창 공간 개수: {windowless_count}
■ 전체 면적 대비 공간 비율 (%)
    - 거실 공간: {living_room_ratio}
    - 주방 공간: {kitchen_ratio}
    - 욕실 공간: {bathroom_ratio}
    - 발코니 공간: {balcony_ratio}
■ 구조 및 성능
    - 건물 구조 유형: {structure_type}
    - 환기: {ventilation_quality}
■ 공간 구성 여부
    - 특화 공간: {has_special_space}
    - 기타 공간: {has_etc_space}
■ 종합 평가
    - 평가 결과: {compliance_grade}

3. 도면 공간 구성 설명 🧩
Since the document is **internal evaluation text**,
it must be restructured into a form that is easy for users to read according to the rules below.

**Organization Rules:**
* Use **only factual information** contained in the original text.
* Remove document-meta expressions such as *“is stated,” “is mentioned,”* or *“is described.”*
* Do not use Korean meta expressions like "기재되어 있습니다", "언급되어 있습니다", "서술되어 있습니다".
* Remove **only** result-oriented judgment expressions such as internal criteria, suitability determinations, or pass/fail statements.
* Sentences that describe a **state or condition**, such as *“insufficient”* or *“improvement is needed,”* are considered factual descriptions and are **allowed**.
* Merge sentences with the same meaning into one.
* Sentences may be rephrased into natural English **without changing their meaning**.
* Do **not** include advice, criteria comparisons, or design suggestions.
* If the original document contains content related to the following items, that content **must be included in the overall summary sentence*.
  • storage -> 수납공간
  • lighting -> 채광
  • family_harmony -> 가족 융화
* If `document_signals` exist for each floor plan, include all of them in the first overall summary sentence for that floor plan.
* Do not drop value polarity. Keep positive/negative wording from `document_signals` (e.g., 우수, 적정, 부족, 미흡, 부적합, 불합격).
* Prefer `display_value` for user-facing wording (e.g., 채광: 좋음, 수납공간: 넉넉함).
* The overall summary must start with these two fixed lines:
  {bay_count}Bay {structure_type} 구조입니다.
  채광: {display_value}{(근거)}, 환기: {display_value}{(근거)}, 가족 융화: {display_value}, 수납공간: {display_value}{(근거)}으로 정리됩니다.
* Add evidence parentheses only when explicit evidence exists in the original document. If no explicit evidence exists, omit parentheses.
* Never output placeholder evidence text such as "근거 없음" or "확인 필요".
* In each evidence parentheses, write only concise evidence text (e.g., 안방 외기창 미확보). Do not include prefixes like "적합:" or "부적합:".
* Do not repeat the same fact twice. If the same evidence appears in the summary sentence, do not repeat it in later sentences.
* The second summary sentence should include only additional non-duplicate facts that are not already stated in the first summary sentence.

**Output Format:**
* Overall summary: 1–2 sentences (describing overall spatial characteristics only)
* Followed by space-by-space descriptions
* One sentence per space
* If multiple spaces have exactly the same description, merge them into one line using slash-joined labels.
* When merged labels share the same base name, keep the base only once.
  Example: `침실1/침실2` -> `침실1/2`, `기타1/기타2/기타3` -> `기타1/2/3`.
  Example: `기타1/2/3/4/5/6: 기타 공간은 기능이 명확하지 않으며, 창문이 없어 채광이 부족합니다.`

출력 예시 형식:
3Bay 판상형 구조입니다.
채광: 부족함(안방 외기창 미확보), 환기: 좋음(주방 환기창 확보), 가족 융화: 적합, 수납공간: 부족함(수납공간 비율 10% 미만)으로 정리됩니다.
안방 외기창이 없고, 욕실 환기창이 없습니다.
■ 거실: 중앙에 위치하여 가족이 모일 수 있는 공간으로 적합합니다.
■ 침실: 개인적인 공간으로 분리되어 적절하게 배치되어 있습니다.
■ 주방/식당: 환기창이 있어 환기가 우수합니다.
■ 화장실: 환기창이 없어 환기 측면에서 개선이 필요합니다. 
■ 발코니: 외부 공간으로의 활용도가 높습니다.
"""

        user_content = (
            f"검색된 도면 id(조회 결과 목록):\n{id_list_text}\n\n"
            f"{representative_title}:\n{', '.join(representative_ids)}\n\n"
            f"조건 일치 전체 건수(total_count):\n{total_match_count}\n\n"
            f"사용자가 설정한 검색 조건:\n{filters_json}\n\n"
            f"대표 도면 데이터(순위/메타데이터/document/similarity):\n{candidates_json}\n\n"
            "각 도면의 `document_signals`는 3번의 전체 요약 문장에 반드시 모두 반영하세요.\n\n"
            "신호 값은 `display_value`를 우선 사용해 사용자 친화적으로 표현하세요.\n\n"
            "요약 시작은 `NBay 구조입니다.` 다음 줄 `채광/환기/가족 융화/수납공간` 고정 템플릿을 따르세요.\n\n"
            "`근거 없음`, `확인 필요` 같은 자리표시자 표현은 절대 사용하지 마세요.\n\n"
            "요약 2번째 줄에서 언급한 근거는 다음 문장에서 중복해서 반복하지 마세요.\n\n"
            f"사용자 질의 원문:\n{query}"
        )

        def _call_llm() -> str:
            response = self.client.chat.completions.create(
                model="gpt-5.2-2025-12-11",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
            )
            return (response.choices[0].message.content or "").strip()

        return self._run_validated_generation(mode="general", generate_fn=_call_llm)

    def _generate_no_match_answer(self, total_match_count: int = 0) -> str:
        return (
            f"조건을 만족하는 도면 총 개수: {int(total_match_count)}\n"
            "검색된 도면 id: 없음\n"
            "요청 조건과 일치하는 도면이 존재하지 않습니다."
        )

    def _generate_validated_no_match_answer(self, total_match_count: int = 0) -> str:
        answer = self._generate_no_match_answer(total_match_count=total_match_count)
        if not self.answer_validation_enabled:
            return answer
        try:
            result = self._validate_answer_format(answer=answer, mode="no_match")
        except Exception:
            self.logger.exception("answer_validation_exception mode=no_match attempt=0")
            return answer
        if result.ok:
            self.logger.info("answer_validation_pass mode=no_match attempt=0 latency_ms=0")
            return answer
        self.logger.warning(
            "answer_validation_fail mode=no_match attempt=0 missing_fields=%s latency_ms=0",
            ",".join(result.missing_fields) or "none",
        )
        if self.answer_validation_safe_fallback:
            fallback = self._build_safe_default_answer(mode="no_match")
            self.logger.warning("answer_validation_fallback mode=no_match retries=0")
            return fallback
        return answer


# ----------------------------------------------------------------------------------------------
    def run(self, query: str, email: str = "") -> dict[str, Any]:
        request_start = time.perf_counter()
        query_id = uuid.uuid4().hex[:12]
        normalized_query = query.strip()
        self._log_event(
            event="query_received",
            query_id=query_id,
            query_len=len(normalized_query),
            query_preview=normalized_query[:120],
        )
        if not normalized_query:
            self._log_event(
                event="query_completed",
                query_id=query_id,
                result="empty_query",
                latency_ms=int((time.perf_counter() - request_start) * 1000),
            )
            return {"answer": "Try searching again.", "floorplan_ids": []}

        try:
            if self._is_floorplan_image_name(normalized_query):
                doc_lookup_start = time.perf_counter()
                doc = self._retrieve_by_document_id(normalized_query)
                self._log_event(
                    event="doc_lookup_complete",
                    query_id=query_id,
                    latency_ms=int((time.perf_counter() - doc_lookup_start) * 1000),
                    found=bool(doc),
                )
                if not doc:
                    answer = f"요청한 도면 id를 찾지 못했습니다: {normalized_query}"
                    self._log_event(
                        event="query_completed",
                        query_id=query_id,
                        mode="document_id",
                        result="not_found",
                        latency_ms=int((time.perf_counter() - request_start) * 1000),
                    )
                    return {"answer": answer, "floorplan_ids": []}
                generate_start = time.perf_counter()
                answer = self._generate_document_id_answer(normalized_query, doc)
                self._log_event(
                    event="generate_complete",
                    query_id=query_id,
                    mode="document_id",
                    latency_ms=int((time.perf_counter() - generate_start) * 1000),
                )
                self._log_event(
                    event="query_completed",
                    query_id=query_id,
                    mode="document_id",
                    result="ok",
                    latency_ms=int((time.perf_counter() - request_start) * 1000),
                )
                return {"answer": answer, "floorplan_ids": [doc[0]]}

            analyze_start = time.perf_counter()
            query_json = self._analyze_query(normalized_query)
            self._log_event(
                event="analyze_complete",
                query_id=query_id,
                latency_ms=int((time.perf_counter() - analyze_start) * 1000),
                filter_count=len(query_json.get("filters", {}) or {}),
                documents_len=len(str(query_json.get("documents", "") or "")),
            )

            count_start = time.perf_counter()
            total_match_count = self._count_matches(
                query_json.get("filters", {}) or {},
                query_json.get("documents", "") or "",
            )
            self._log_event(
                event="count_complete",
                query_id=query_id,
                latency_ms=int((time.perf_counter() - count_start) * 1000),
                total_match_count=total_match_count,
            )
            if total_match_count <= 0:
                answer = self._generate_validated_no_match_answer(total_match_count=0)
                self._log_event(
                    event="query_completed",
                    query_id=query_id,
                    mode="general",
                    result="no_match",
                    latency_ms=int((time.perf_counter() - request_start) * 1000),
                )
                return {"answer": answer, "floorplan_ids": []}
            retrieve_k = min(max(total_match_count, 3), 50)

            retrieve_start = time.perf_counter()
            docs = self._retrieve_hybrid(query_json, top_k=retrieve_k)
            self._log_event(
                event="retrieve_complete",
                query_id=query_id,
                latency_ms=int((time.perf_counter() - retrieve_start) * 1000),
                retrieve_k=retrieve_k,
                retrieved_count=len(docs),
            )

            rerank_start = time.perf_counter()
            docs = self._rerank_by_query_signal_preferences(docs, normalized_query)
            self._log_event(
                event="rerank_complete",
                query_id=query_id,
                latency_ms=int((time.perf_counter() - rerank_start) * 1000),
                reranked_count=len(docs),
            )

            floorplan_ids = [row[0] for row in docs[:3]]

            generate_start = time.perf_counter()
            answer = self._generate_answer(
                normalized_query, query_json, docs, total_match_count
            )
            self._log_event(
                event="generate_complete",
                query_id=query_id,
                mode="general",
                latency_ms=int((time.perf_counter() - generate_start) * 1000),
            )
            self._log_event(
                event="query_completed",
                query_id=query_id,
                mode="general",
                result="ok",
                total_match_count=total_match_count,
                latency_ms=int((time.perf_counter() - request_start) * 1000),
            )
            return {"answer": answer, "floorplan_ids": floorplan_ids}
        except Exception as exc:
            self._log_event(
                event="query_failed",
                level=logging.ERROR,
                query_id=query_id,
                error=str(exc),
                latency_ms=int((time.perf_counter() - request_start) * 1000),
            )
            raise