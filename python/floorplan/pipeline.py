import json
import logging
import re
import time
import uuid
import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
import psycopg2
from openai import OpenAI


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
    FLOORPLAN_IMAGE_STEM_RE = re.compile(
        r"^(?=.*\d)[A-Za-z0-9][A-Za-z0-9_.-]*_[A-Za-z0-9_.-]+$",
        re.IGNORECASE,
    )
    DOCUMENT_SIGNAL_KEY_ALIASES = {
        "lighting": ("lighting", "daylight", "daylighting", "daylightling", "채광"),
        "ventilation": ("ventilation", "환기"),
        "family_harmony": ("family_harmony", "family_community", "가족 융화", "가족융화"),
        "storage": ("storage", "수납공간", "수납 공간", "수납"),
    }
    DOCUMENT_SIGNAL_KR_LABELS = {
        "lighting": "채광",
        "ventilation": "환기",
        "family_harmony": "가족 융화",
        "storage": "수납",
    }
    POSITIVE_SIGNAL_WORDS = ("우수", "적정", "적합", "양호", "충분", "넉넉")
    NEGATIVE_SIGNAL_WORDS = ("미흡", "부족", "부적합", "불합격", "미달", "없음")
    SIGNAL_POSITIVE_DISPLAY = {
        "lighting": "좋습니다",
        "ventilation": "좋습니다",
        "family_harmony": "적합",
        "storage": "넉넉합니다",
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
    DOCUMENT_LAYOUT_REQUIRED_HEADERS = (
        "종합 등급",
        "핵심 설계 평가",
        "주요 공간별 상세 분석",
    )
    DOCUMENT_LAYOUT_REQUIRED_LINE_PATTERNS = (
        (
            "layout_compliance_grade_line",
            re.compile(r"(?m)^\s*■\s*(?:\*\*)?\s*종합\s*등급\s*(?:\*\*)?\s*:\s*.+$"),
        ),
        (
            "layout_fit_items_line",
            re.compile(r"(?m)^\s*(?:[-•]\s*)?적합\s*항목\s*:\s*.+$"),
        ),
        (
            "layout_unfit_items_line",
            re.compile(r"(?m)^\s*(?:[-•]\s*)?부적합\s*항목\s*:\s*.+$"),
        ),
    )
    FORBIDDEN_LAYOUT_META_EXPRESSIONS = (
        "기재되어 있습니다",
        "언급되어 있습니다",
        "서술되어 있습니다",
        "표기되어 있습니다",
        "표시되어 있습니다",
    )
    FORBIDDEN_LAYOUT_LABEL_PATTERNS = (
        re.compile(r"(?m)^\s*(?:[-•]\s*)?채광\s*및\s*쾌적성\s*\([^)\n]*\)\s*:\s*.+$"),
        re.compile(r"(?m)^\s*(?:[-•]\s*)?환기\s*\([^)\n]*\)\s*:\s*.+$"),
        re.compile(r"(?m)^\s*(?:[-•]\s*)?가족\s*융화\s*\([^)\n]*\)\s*:\s*.+$"),
        re.compile(r"(?m)^\s*(?:[-•]\s*)?수납\s*\([^)\n]*\)\s*:\s*.+$"),
        re.compile(r"(?m)^\s*(?:[-•]\s*)?(?:\[)?주방및식당(?:\])?(?:\s*:\s*|\s+).+$"),
        re.compile(r"(?m)^\s*(?:[-•]\s*)?(?:\[)?현관및기타(?:공간)?(?:\])?(?:\s*:\s*|\s+).+$"),
        re.compile(r"(?m)^\s*(?:[-•]\s*)?(?:\[)?(?:드레|스룸)(?:\])?(?:\s*:\s*|\s+).+$"),
    )
    FORBIDDEN_LAYOUT_TECHNICAL_PATTERNS = (
        re.compile(r"\d+\s*Bay\s*\([^)\n]*(?:통계|bay_count|count)[^)\n]*\)", re.IGNORECASE),
        re.compile(r"환기창\s*\(\s*창호\s*\)", re.IGNORECASE),
        re.compile(r"연결\s*\(\s*door\s*/\s*window\s*\)", re.IGNORECASE),
        re.compile(
            r"\([^)\n]*(?:bay_count|room_count|bathroom_count|windowless_count|balcony_ratio|living_room_ratio|bathroom_ratio|kitchen_ratio|door/window|window/door)[^)\n]*\)",
            re.IGNORECASE,
        ),
    )
    BALCONY_POSITIVE_HINT_RE = re.compile(
        r"(활용도\s*높|활용\s*가능|외부\s*공간.*활용|연결.*원활|채광.*좋|넓)",
        re.IGNORECASE,
    )
    BALCONY_NEGATIVE_HINT_RE = re.compile(
        r"(활용도\s*낮|활용\s*어려|연결.*불편|채광.*부족|좁|없음)",
        re.IGNORECASE,
    )
    MORE_RESULTS_COUNT_REQUEST_RE = re.compile(
        r"^\s*(?P<count>\d+)\s*개\s*더(?:\s*(?:찾아(?:줘|주세요|줘요)?|줘|주세요|줘요|보내(?:줘|주세요|줘요)?|보여(?:줘|주세요|줘요)?))?\s*[.!?]?\s*$",
        re.IGNORECASE,
    )
    MORE_RESULTS_DEFAULT_REQUEST_RE = re.compile(
        r"^\s*더(?:\s*(?:찾아(?:줘|주세요|줘요)?|줘|주세요|줘요|보내(?:줘|주세요|줘요)?|보여(?:줘|주세요|줘요)?))?\s*[.!?]?\s*$",
        re.IGNORECASE,
    )
    FLOORPLAN_BLOCK_HEADER_RE = re.compile(
        r"(?m)^\s*(?:#{1,6}\s*)?\[도면\s*#\d+\]\s*(?P<document_id>[^\n]+?)\s*$"
    )

    def __init__(
        self,
        db_config,
        openai_api_key,
        embedding_model: str = "text-embedding-3-small",
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
        self.vector_weight, self.text_weight = self._normalize_hybrid_weights(
            vector_weight, text_weight
        )
        self.answer_validation_enabled = bool(answer_validation_enabled)
        self.answer_validation_retry_max = max(0, int(answer_validation_retry_max))
        self.answer_validation_safe_fallback = bool(answer_validation_safe_fallback)
        self.chat_history: list[dict[str, Any]] = []
        self.max_chat_history: int = 50
        self.current_offset: int = 0
        self._last_query_json_for_more: Optional[dict[str, Any]] = None
        self._last_query_text_for_more: str = ""
        self._last_total_match_count_for_more: int = 0
        self._returned_floorplan_ids_for_more: set[int] = set()
        self._returned_floorplan_names_for_more: set[str] = set()
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

    def _normalize_storage_alias_terms(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return text
        text = re.sub(r"드레\s*[\+/]\s*스룸", "드레스룸", text)
        text = re.sub(r"드레\s*(?:와|및)\s*스룸", "드레스룸", text)
        text = re.sub(r"(?m)^(\s*-\s*)(?:드레|스룸)\s*:\s*", r"\1드레스룸: ", text)
        text = re.sub(r"(?<!드레스)드레(?!스룸)", "드레스룸", text)
        text = re.sub(r"(?<!드레)스룸(?![가-힣])", "드레스룸", text)
        return text

    def _merge_duplicate_storage_lines(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return text
        lines = text.splitlines()
        merged_lines: list[str] = []
        dressing_room_texts: list[str] = []
        insert_idx: Optional[int] = None
        line_prefix = "- "

        for line in lines:
            match = re.match(r"^(?P<prefix>\s*-\s*)드레스룸\s*:\s*(?P<body>.+?)\s*$", line)
            if match:
                if insert_idx is None:
                    insert_idx = len(merged_lines)
                    line_prefix = match.group("prefix")
                body = re.sub(r"\s+", " ", match.group("body")).strip()
                if body and body not in dressing_room_texts:
                    dressing_room_texts.append(body)
                continue
            merged_lines.append(line)

        if dressing_room_texts:
            merged_line = f"{line_prefix}드레스룸: {' '.join(dressing_room_texts)}"
            if insert_idx is None:
                merged_lines.append(merged_line)
            else:
                merged_lines.insert(insert_idx, merged_line)
        return "\n".join(merged_lines)

    def _normalize_space_bullet_labels(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return text
        normalized = re.sub(
            r"(?m)^(\s*(?:[-•]\s*)?)주방\s*/\s*식당\s*:\s*",
            r"\1주방/식당: ",
            text,
        )
        normalized = re.sub(
            r"(?m)^(\s*(?:[-•]\s*)?)주방\s*및\s*식당\s*:\s*",
            r"\1주방/식당: ",
            normalized,
        )
        normalized = re.sub(
            r"(?m)^(\s*(?:[-•]\s*)?)주방및식당\s*:\s*",
            r"\1주방/식당: ",
            normalized,
        )
        normalized = re.sub(
            r"(?m)^(\s*(?:[-•]\s*)?)현관\s*/\s*기타(?:\s*공간)?\s*:\s*",
            r"\1현관/기타: ",
            normalized,
        )
        normalized = re.sub(
            r"(?m)^(\s*(?:[-•]\s*)?)현관\s*및\s*기타(?:\s*공간)?\s*:\s*",
            r"\1현관/기타: ",
            normalized,
        )
        normalized = re.sub(
            r"(?m)^(\s*(?:[-•]\s*)?)현관및기타(?:공간)?\s*:\s*",
            r"\1현관/기타: ",
            normalized,
        )
        return normalized

    @staticmethod
    def _normalize_core_eval_label_for_output(label: str) -> str:
        raw = re.sub(r"\s+", " ", str(label or "")).strip()
        if not raw:
            return ""
        compact = re.sub(r"[\s_\-]+", "", raw).lower()
        if compact in {
            "daylight",
            "daylighting",
            "daylightling",
            "lighting",
            "채광",
            "채광및쾌적성",
        }:
            return "채광"
        if compact in {"ventilation", "환기"}:
            return "환기"
        if compact in {"familycommunity", "familyharmony", "가족융화"}:
            return "가족 융화"
        if compact in {"storage", "수납", "수납공간"}:
            return "수납"
        return raw

    def _normalize_layout_tone_style(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return text

        def _normalize_layout_body(layout_body: str) -> str:
            normalized = layout_body

            core_block_re = re.compile(
                r"(?ms)(?P<header>^\s*■\s*(?:\*\*)?\s*핵심\s*설계\s*평가\s*(?:\*\*)?\s*\n)"
                r"(?P<body>.*?)(?=^\s*■\s*(?:\*\*)?\s*주요\s*공간별\s*상세\s*분석\s*(?:\*\*)?\s*$|\Z)"
            )

            def _normalize_core_block(match: re.Match[str]) -> str:
                header = match.group("header")
                body = match.group("body")
                normalized_lines: list[str] = []
                for line in body.splitlines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    line_match = re.match(r"^\s*(?:[-•]\s*)?([^:\n]+)\s*:\s*(.+?)\s*$", line)
                    if line_match:
                        label = self._normalize_core_eval_label_for_output(line_match.group(1))
                        content = re.sub(r"\s+", " ", line_match.group(2)).strip()
                        if label and content:
                            normalized_lines.append(f"• {label}: {content}")
                        continue
                    normalized_lines.append(stripped)
                block_body = "\n".join(normalized_lines).strip()
                if not block_body:
                    return header
                return f"{header}{block_body}\n"

            normalized = core_block_re.sub(_normalize_core_block, normalized)
            normalized = re.sub(r"\n{3,}", "\n\n", normalized)

            detail_header_re = re.compile(
                r"(?m)^(\s*■\s*(?:\*\*)?\s*주요\s*공간별\s*상세\s*분석\s*(?:\*\*)?\s*)$"
            )
            detail_match = detail_header_re.search(normalized)
            if detail_match:
                detail_start = detail_match.end()
                detail_body = normalized[detail_start:]

                def _bracketize(match: re.Match[str]) -> str:
                    prefix = match.group("prefix")
                    bracket_label = match.group("bracket_label")
                    plain_label = match.group("plain_label")
                    body = match.group("body")
                    raw_label = bracket_label if bracket_label is not None else plain_label
                    canonical_label = self._normalize_space_label_for_output(raw_label or "")
                    canonical_label = canonical_label or re.sub(r"\s+", " ", str(raw_label or "")).strip()
                    return f"{prefix}[{canonical_label}] {body}"

                detail_body = re.sub(
                    r"(?m)^(?P<prefix>\s*)(?:[-•]\s*)?(?:\[(?P<bracket_label>[^\]\n]+)\]|(?P<plain_label>[^:\n\[\]]+))"
                    r"(?:\s*:\s*|\s+)(?P<body>.+)\s*$",
                    _bracketize,
                    detail_body,
                )
                normalized = f"{normalized[:detail_start]}{detail_body}"
            return normalized

        section_pattern = re.compile(
            r"(?s)(?P<header>3\.\s*도면\s*공간\s*구성\s*설명\s*🧩\s*)(?P<body>.*?)(?=\n(?:#{1,6}\s*)?\[\s*도면\s*#|\Z)"
        )

        return section_pattern.sub(
            lambda m: f"{m.group('header')}{_normalize_layout_body(m.group('body'))}",
            text,
        )

    def _normalize_technical_parenthetical_phrasing(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return text
        normalized = re.sub(
            r"(\d+\s*Bay)\s*\(\s*[^)\n]*(?:통계|bay_count|count)[^)\n]*\)",
            r"\1",
            text,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(r"환기창\s*\(\s*창호\s*\)", "환기창", normalized, flags=re.IGNORECASE)
        normalized = re.sub(
            r"연결\s*\(\s*door\s*/\s*window\s*\)",
            "연결",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"\(\s*[^)\n]*(?:bay_count|room_count|bathroom_count|windowless_count|balcony_ratio|living_room_ratio|bathroom_ratio|kitchen_ratio|door/window|window/door)\s*[^)\n]*\)",
            "",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(r"[ \t]{2,}", " ", normalized)
        normalized = re.sub(r"\s+([.,])", r"\1", normalized)
        return normalized

    def _normalize_signal_tone_phrasing(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return text
        text = re.sub(r"넉넉함입니다(?P<tail>[.!?]?)", r"넉넉합니다\g<tail>", text)
        text = re.sub(r"좋음입니다(?P<tail>[.!?]?)", r"좋습니다\g<tail>", text)
        return text

    def _normalize_floorplan_block_breaks(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return text
        # Ensure each "[도면 #N]" or "### [도면 #N]" marker starts on a new line.
        text = re.sub(r"(?<!^)(?<!\n)\s*((?:#{1,6}\s*)?\[\s*도면\s*#\d+\])", r"\n\1", text)
        # Keep one blank line before each marker for readability.
        text = re.sub(r"(?m)([^\n])\n((?:#{1,6}\s*)?\[\s*도면\s*#\d+\])", r"\1\n\n\2", text)
        return re.sub(r"\n{3,}((?:#{1,6}\s*)?\[\s*도면\s*#\d+\])", r"\n\n\1", text)

    def _normalize_generated_answer(self, answer: str) -> str:
        return self._normalize_floorplan_block_breaks(
            self._merge_duplicate_storage_lines(
            self._normalize_storage_alias_terms(
            self._normalize_meta_expressions(
                self._normalize_summary_signal_sentence(
                    self._normalize_signal_tone_phrasing(
                    self._normalize_layout_tone_style(
                        self._normalize_space_bullet_labels(
                            self._normalize_technical_parenthetical_phrasing(
                                self._normalize_space_section_labels(answer)
                            )
                        )
                    )
                    )
                )
            )
            )
        ))

    def _extract_layout_section_text(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return ""
        match = re.search(
            r"(?s)3\.\s*도면\s*공간\s*구성\s*설명\s*🧩\s*(?P<section>.*)$",
            text,
        )
        if not match:
            return ""
        return match.group("section").strip()

    def _extract_all_layout_sections(self, answer: str) -> list[str]:
        text = str(answer or "")
        if not text:
            return []
        matches = re.finditer(
            r"(?s)3\.\s*도면\s*공간\s*구성\s*설명\s*🧩\s*(?P<section>.*?)(?=\n(?:#{1,6}\s*)?\[\s*도면\s*#|\Z)",
            text,
        )
        sections = [m.group("section").strip() for m in matches]
        return [section for section in sections if section]

    def _has_layout_core_eval_items(self, layout_text: str) -> bool:
        match = re.search(
            r"(?ms)^\s*■\s*(?:\*\*)?\s*핵심\s*설계\s*평가\s*(?:\*\*)?\s*$\n?"
            r"(?P<body>.*?)(?=^\s*■\s*(?:\*\*)?\s*주요\s*공간별\s*상세\s*분석\s*(?:\*\*)?\s*$|\Z)",
            layout_text,
        )
        if not match:
            return False
        body = match.group("body")
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r"^(?:[-•·]\s*)?[^:\n]+:\s*.+$", stripped):
                return True
        return False

    def _has_layout_space_detail_items(self, layout_text: str) -> bool:
        match = re.search(
            r"(?ms)^\s*■\s*(?:\*\*)?\s*주요\s*공간별\s*상세\s*분석\s*(?:\*\*)?\s*$\n?"
            r"(?P<body>.*)$",
            layout_text,
        )
        if not match:
            return False
        body = match.group("body")
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r"^(?:[-•·]\s*)?\[[^\]\n]+\](?:\s*:\s*|\s+).+$", stripped):
                return True
        return False

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
            has_document_id_token = True
            has_layout_summary = self.NO_MATCH_MESSAGE_TOKEN in text
            if not has_metadata_summary:
                missing_fields.append("no_match_count")
            if not has_layout_summary:
                missing_fields.append("no_match_message")
            ok = (
                is_non_empty
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
            # 모든 모드에서 "검색된 도면 id" 토큰 검증은 수행하지 않는다.
            has_document_id_token = True
        elif normalized_mode == "general":
            # General mode follows the multi-floorplan format:
            # "조건을 만족하는 도면 총 개수" + repeated "[도면 #N] {document_id}" blocks.
            has_document_id_token = True
            if not re.search(
                r"(?m)^\s*조건을\s*만족하는\s*도면\s*총\s*개수\s*:\s*\d+\s*$",
                text,
                flags=re.IGNORECASE,
            ):
                missing_fields.append("general_total_count_line")

            # Each floorplan marker must start on a new line, not be attached to prior text.
            for _line in text.splitlines():
                _stripped = _line.strip()
                if re.search(r"\[\s*도면\s*#\d+\]", _stripped):
                    if not re.match(r"(?:#{1,6}\s*)?\[\s*도면\s*#\d+\]", _stripped):
                        missing_fields.append("general_doc_header_linebreak")
                        break

            general_blocks = list(
                re.finditer(
                    r"(?ms)^\s*(?:#{1,6}\s*)?\[도면\s*#\d+\]\s*[^\n]+\n(?P<body>.*?)(?=^\s*(?:#{1,6}\s*)?\[도면\s*#\d+\]\s*[^\n]+\n|\Z)",
                    text,
                )
            )
            if not general_blocks:
                missing_fields.append("general_doc_header")
            else:
                for idx, block_match in enumerate(general_blocks, start=1):
                    block_body = block_match.group("body")
                    if not re.search(
                        r"(?m)^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*1\.\s*도면\s*선택\s*근거(?:\s*🔍)?\s*(?:\*\*)?\s*$",
                        block_body,
                    ):
                        missing_fields.append(f"general_section1_doc{idx}")
                    if not re.search(
                        r"(?m)^\s*(?:[-•·]\s*)?찾는\s*조건\s*:\s*.+$",
                        block_body,
                    ):
                        missing_fields.append(f"general_find_conditions_doc{idx}")
                    if not re.search(
                        r"(?m)^\s*(?:[-•·]\s*)?일치\s*조건\s*:\s*.+$",
                        block_body,
                    ):
                        missing_fields.append(f"general_match_conditions_doc{idx}")
                    if self.METADATA_SECTION_TOKEN not in block_body:
                        missing_fields.append(f"general_section2_doc{idx}")
                    if self.LAYOUT_SECTION_TOKEN not in block_body:
                        missing_fields.append(f"general_section3_doc{idx}")
        else:
            raise ValueError(f"Unsupported validation mode: {mode}")

        if normalized_mode in {"document_id", "general"}:
            if normalized_mode == "document_id":
                layout_text = self._extract_layout_section_text(text)
                layout_sections = [layout_text] if layout_text else []
            else:
                layout_sections = self._extract_all_layout_sections(text)

            if not layout_sections:
                missing_fields.append("layout_section_body")
            else:
                for section_idx, layout_text in enumerate(layout_sections, start=1):
                    suffix = "" if normalized_mode == "document_id" else f"_doc{section_idx}"
                    for idx, header in enumerate(self.DOCUMENT_LAYOUT_REQUIRED_HEADERS, start=1):
                        if header not in layout_text:
                            missing_fields.append(f"layout_header_{idx}{suffix}")
                    for field_name, pattern in self.DOCUMENT_LAYOUT_REQUIRED_LINE_PATTERNS:
                        if not pattern.search(layout_text):
                            missing_fields.append(f"{field_name}{suffix}")
                    if not self._has_layout_core_eval_items(layout_text):
                        missing_fields.append(f"layout_core_eval_line{suffix}")
                    if not self._has_layout_space_detail_items(layout_text):
                        missing_fields.append(f"layout_space_detail_line{suffix}")
                    if any(expr in layout_text for expr in self.FORBIDDEN_LAYOUT_META_EXPRESSIONS):
                        missing_fields.append(f"layout_meta_expression{suffix}")
                    if any(pattern.search(layout_text) for pattern in self.FORBIDDEN_LAYOUT_LABEL_PATTERNS):
                        missing_fields.append(f"layout_label_parentheses{suffix}")
                    if any(pattern.search(layout_text) for pattern in self.FORBIDDEN_LAYOUT_TECHNICAL_PATTERNS):
                        missing_fields.append(f"layout_technical_notation{suffix}")
                    if re.search(r"(?<!드레스)드레(?!스룸)|(?<!드레)스룸(?![가-힣])", layout_text):
                        missing_fields.append(f"layout_storage_alias{suffix}")
                    if re.search(r"(근거\s*없음|확인\s*필요)", layout_text, flags=re.IGNORECASE):
                        missing_fields.append(f"layout_placeholder_text{suffix}")

        ok = is_non_empty and not missing_fields
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
                "■ 종합 등급: 응답 형식 검증 실패로 설명 생성 불가\n"
                "- 적합 항목: 응답 형식 검증 실패로 설명 생성 불가\n"
                "- 부적합 항목: 응답 형식 검증 실패로 설명 생성 불가\n\n"
                "■ 핵심 설계 평가\n"
                "• 채광 및 쾌적성: 응답 형식 검증 실패로 설명 생성 불가\n"
                "• 가족 융화: 응답 형식 검증 실패로 설명 생성 불가\n"
                "• 수납: 응답 형식 검증 실패로 설명 생성 불가\n\n"
                "■ 주요 공간별 상세 분석\n"
                "[공간 정보] 응답 형식 검증 실패로 설명 생성 불가"
            )
        if normalized_mode == "general":
            return (
                "1. 검색된 도면 id: 정보 생성 불가\n\n"
                "2. 도면 기본 정보 📊\n"
                "- 응답 형식 검증 실패로 요약 생성 불가\n\n"
                "3. 도면 공간 구성 설명 🧩\n"
                "■ 종합 등급: 응답 형식 검증 실패로 설명 생성 불가\n"
                "- 적합 항목: 응답 형식 검증 실패로 설명 생성 불가\n"
                "- 부적합 항목: 응답 형식 검증 실패로 설명 생성 불가\n\n"
                "■ 핵심 설계 평가\n"
                "• 채광 및 쾌적성: 응답 형식 검증 실패로 설명 생성 불가\n"
                "• 가족 융화: 응답 형식 검증 실패로 설명 생성 불가\n"
                "• 수납: 응답 형식 검증 실패로 설명 생성 불가\n\n"
                "■ 주요 공간별 상세 분석\n"
                "[공간 정보] 응답 형식 검증 실패로 설명 생성 불가"
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
            bounds = self._parse_ratio_conditions_from_text(text)
            if len(bounds) >= 2:
                return {"bounds": bounds}
            if len(bounds) == 1:
                return bounds[0]
            num_match = re.search(r"-?\d+(\.\d+)?", text)
            if num_match:
                return {"op": "동일", "val": float(num_match.group())}
            return None

        if isinstance(value, dict):
            bounds = self._ratio_filter_to_bounds(value)
            if len(bounds) >= 2:
                return {"bounds": bounds}
            if len(bounds) == 1:
                return bounds[0]
            raw_op = value.get("op", value.get("operator"))
            raw_val = value.get("val", value.get("value"))
            val = self._parse_float(raw_val)
            op = self._normalize_ratio_operator(raw_op)
            if val is None:
                return None
            return {"op": op or "동일", "val": val}

        return None

    def _parse_ratio_conditions_from_text(self, text: str) -> list[dict[str, Any]]:
        raw = str(text or "")
        if not raw.strip():
            return []

        candidates: list[tuple[int, str, float]] = []
        occupied_spans: list[tuple[int, int]] = []
        # Range phrases (e.g., "10%에서 20% 사이", "10~20%") are treated as inclusive bounds.
        for match in re.finditer(
            r"(-?\d+(?:\.\d+)?)\s*%?\s*(?:에서|부터|~|〜|∼|-)\s*(-?\d+(?:\.\d+)?)\s*%?\s*(?:사이|구간|범위)?",
            raw,
        ):
            first = float(match.group(1))
            second = float(match.group(2))
            lower = min(first, second)
            upper = max(first, second)
            start = match.start()
            candidates.append((start, "이상", lower))
            candidates.append((start + 1, "이하", upper))
            occupied_spans.append((match.start(), match.end()))

        for match in re.finditer(
            r"(-?\d+(?:\.\d+)?)\s*%?\s*(?:와|및)\s*(-?\d+(?:\.\d+)?)\s*%?\s*사이",
            raw,
        ):
            first = float(match.group(1))
            second = float(match.group(2))
            lower = min(first, second)
            upper = max(first, second)
            start = match.start()
            candidates.append((start, "이상", lower))
            candidates.append((start + 1, "이하", upper))
            occupied_spans.append((match.start(), match.end()))

        for match in re.finditer(r"(-?\d+(?:\.\d+)?)\s*%?\s*(이상|이하|초과|미만|동일)", raw):
            op = self._normalize_ratio_operator(match.group(2))
            if op is not None:
                candidates.append((match.start(), op, float(match.group(1))))
                occupied_spans.append((match.start(), match.end()))

        for match in re.finditer(r"(이상|이하|초과|미만|동일)\s*(-?\d+(?:\.\d+)?)\s*%?", raw):
            start = match.start()
            end = match.end()
            if any(start < span_end and end > span_start for span_start, span_end in occupied_spans):
                continue
            op = self._normalize_ratio_operator(match.group(1))
            if op is not None:
                candidates.append((start, op, float(match.group(2))))

        if not candidates:
            return []

        candidates.sort(key=lambda item: item[0])
        bounds: list[dict[str, Any]] = []
        seen: set[tuple[str, float]] = set()
        for _, op, val in candidates:
            key = (op, val)
            if key in seen:
                continue
            seen.add(key)
            bounds.append({"op": op, "val": val})
        return bounds

    def _ratio_filter_to_bounds(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, dict):
            return []

        bounds: list[dict[str, Any]] = []

        raw_bounds = value.get("bounds")
        if isinstance(raw_bounds, list):
            for item in raw_bounds:
                if not isinstance(item, dict):
                    continue
                op = self._normalize_ratio_operator(item.get("op", item.get("operator")))
                val = self._parse_float(item.get("val", item.get("value")))
                if op is not None and val is not None:
                    bounds.append({"op": op, "val": val})

        min_val = self._parse_float(value.get("min", value.get("lower")))
        max_val = self._parse_float(value.get("max", value.get("upper")))
        min_op = self._normalize_ratio_operator(value.get("min_op")) or ("이상" if min_val is not None else None)
        max_op = self._normalize_ratio_operator(value.get("max_op")) or ("이하" if max_val is not None else None)
        if min_op is not None and min_val is not None:
            bounds.append({"op": min_op, "val": min_val})
        if max_op is not None and max_val is not None:
            bounds.append({"op": max_op, "val": max_val})

        op = self._normalize_ratio_operator(value.get("op", value.get("operator")))
        val = self._parse_float(value.get("val", value.get("value")))
        if op is not None and val is not None:
            bounds.append({"op": op, "val": val})

        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, float]] = set()
        for bound in bounds:
            key = (bound["op"], float(bound["val"]))
            if key in seen:
                continue
            seen.add(key)
            deduped.append({"op": bound["op"], "val": float(bound["val"])})
        return deduped

    def _merge_ratio_filters(self, current: Any, inferred: Any) -> Optional[dict[str, Any]]:
        merged_bounds: list[dict[str, Any]] = []
        for bound in self._ratio_filter_to_bounds(current):
            merged_bounds.append(bound)
        for bound in self._ratio_filter_to_bounds(inferred):
            if any(b["op"] == bound["op"] and float(b["val"]) == float(bound["val"]) for b in merged_bounds):
                continue
            merged_bounds.append(bound)

        if not merged_bounds:
            return None
        if len(merged_bounds) == 1:
            return {"op": merged_bounds[0]["op"], "val": merged_bounds[0]["val"]}
        return {"bounds": merged_bounds}

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
            match = re.search(r"(\d+)\s*(?:베이|bay)", query, flags=re.IGNORECASE)
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

        ratio_query_targets = {
            "balcony_ratio": r"(발코니|베란다)",
            "living_room_ratio": r"(거실)",
            "bathroom_ratio": r"(욕실|화장실)",
            "kitchen_ratio": r"(주방|식당)",
        }
        for ratio_key, keyword_pattern in ratio_query_targets.items():
            if not re.search(keyword_pattern, query, flags=re.IGNORECASE):
                continue
            if not re.search(
                r"(%|퍼센트|비율|ratio|이상|이하|초과|미만|동일)",
                query,
                flags=re.IGNORECASE,
            ):
                continue
            inferred = self._coerce_ratio_filter(query)
            if inferred is None:
                continue
            merged = self._merge_ratio_filters(augmented.get(ratio_key), inferred)
            if merged is not None:
                augmented[ratio_key] = merged

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
        normalized = query.strip()
        return bool(
            self.FLOORPLAN_IMAGE_NAME_RE.fullmatch(normalized)
            or self.FLOORPLAN_IMAGE_STEM_RE.fullmatch(normalized)
        )

    def _augment_documents_from_query(self, query: str, documents: str) -> str:
        base = str(documents or "").strip()
        text = str(query or "")
        if not base:
            return base

        preferences = self._extract_query_signal_preferences(text)
        if preferences.get("storage") == "positive":
            storage_terms = [
                "수납은(는) 우수",
                "수납은(는) 보통",
                "storage은(는) 우수",
                "storage은(는) 보통",
                "드레스룸",
                "팬트리",
                "수납 공간",
            ]
            joined = " OR ".join(f'"{term}"' for term in storage_terms)
            base = f"({base}) OR ({joined})"

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
                # Accept variants such as "수납은(는) ...", "수납 공간: ...", "storage = ...".
                pattern = (
                    rf"{re.escape(alias)}"
                    r"\s*(?:은\(는\)|은|는|이|가|:|=)\s*([^\n.,]+)"
                )
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

    @staticmethod
    def _normalize_space_label_for_output(label: str) -> str:
        raw = re.sub(r"\s+", " ", str(label or "")).strip()
        if not raw:
            return ""
        compact = re.sub(r"\s+", "", raw)
        if re.fullmatch(r"주방(?:및)?식당|주방/식당", compact):
            return "주방/식당"
        if re.fullmatch(r"현관(?:및)?기타(?:공간)?|현관/기타(?:공간)?", compact):
            return "현관/기타"
        return raw

    def _extract_space_labels_from_document(self, document: str) -> list[str]:
        text = str(document or "")
        if not text.strip():
            return []

        labels: list[str] = []
        for match in re.finditer(r"(?m)^[ \t]*(?:■|-)\s*([^\n:]{1,40})\s*:", text):
            normalized = self._normalize_space_label_for_output(match.group(1))
            if not normalized:
                continue
            if normalized in {
                "핵심 설계 평가",
                "주요 공간별 상세 분석",
                "종합 등급",
                "적합 항목",
                "부적합 항목",
                "채광 및 쾌적성",
                "환기",
                "가족 융화",
                "수납",
            }:
                continue
            if normalized not in labels:
                labels.append(normalized)
        return labels

    def _infer_signal_polarity(self, value: str) -> Optional[str]:
        normalized = re.sub(r"\s+", "", str(value or ""))
        if not normalized:
            return None
        if any(token in normalized for token in self.NEGATIVE_SIGNAL_WORDS):
            return "negative"
        if any(token in normalized for token in self.POSITIVE_SIGNAL_WORDS):
            return "positive"
        return None

    def _storage_positive_rank(self, value: str) -> int:
        normalized = re.sub(r"\s+", "", str(value or ""))
        if not normalized:
            return 0
        if any(token in normalized for token in self.NEGATIVE_SIGNAL_WORDS):
            return -1
        if any(token in normalized for token in ("우수", "최상", "탁월", "넉넉", "풍부", "여유")):
            return 2
        if any(token in normalized for token in ("보통", "양호", "적정", "적합", "충분")):
            return 1
        if any(token in normalized for token in self.POSITIVE_SIGNAL_WORDS):
            return 1
        return 0

    def _normalize_signal_value_for_display(self, key: str, value: str) -> str:
        polarity = self._infer_signal_polarity(value)
        if polarity == "positive":
            return self.SIGNAL_POSITIVE_DISPLAY.get(key, "좋습니다")
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

    def _extract_ratio_proximity_target(
        self, query: str, filters: Optional[dict[str, Any]] = None
    ) -> Optional[tuple[str, float, str]]:
        if not filters:
            return None

        ratio_query_targets = {
            "balcony_ratio": r"(발코니|베란다)",
            "living_room_ratio": r"(거실)",
            "bathroom_ratio": r"(욕실|화장실)",
            "kitchen_ratio": r"(주방|식당)",
        }

        candidates: list[str] = []
        for key, pattern in ratio_query_targets.items():
            if key not in filters:
                continue
            if re.search(pattern, query or "", flags=re.IGNORECASE):
                candidates.append(key)
        if not candidates:
            candidates = [key for key in self.FLOAT_FILTERS if key in filters]

        for key in candidates:
            bounds = self._ratio_filter_to_bounds(filters.get(key))
            if len(bounds) != 1:
                continue
            op = self._normalize_ratio_operator(bounds[0].get("op"))
            target = self._parse_float(bounds[0].get("val"))
            if op in {"이상", "초과", "이하", "미만"} and target is not None:
                return key, float(target), op
        return None

    def _ratio_proximity_distance(
        self, actual: Any, target: float, op: str
    ) -> float:
        value = self._parse_float(actual)
        if value is None:
            return float("inf")

        if op == "이상" and value < target:
            return float("inf")
        if op == "초과" and value <= target:
            return float("inf")
        if op == "이하" and value > target:
            return float("inf")
        if op == "미만" and value >= target:
            return float("inf")
        return abs(value - target)

    def _rerank_by_query_signal_preferences(
        self,
        docs: list[tuple[Any, ...]],
        query: str,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[tuple[Any, ...]]:
        preferences = self._extract_query_signal_preferences(query)
        ratio_proximity = self._extract_ratio_proximity_target(query, filters or {})
        if (not preferences and ratio_proximity is None) or not docs:
            return docs

        storage_priority = preferences.get("storage") == "positive"
        ratio_col_index = {
            "balcony_ratio": 4,
            "living_room_ratio": 5,
            "bathroom_ratio": 6,
            "kitchen_ratio": 7,
        }
        rescored_docs: list[tuple[float, int, float, tuple[Any, ...]]] = []
        for row in docs:
            base_score = float(row[16] if len(row) > 16 and row[16] is not None else 0.0)
            document_text = str(row[2] if len(row) > 2 else "")
            signals = self._extract_document_signals(document_text)
            signal_map = {signal["key"]: signal["value"] for signal in signals}

            bonus = 0.0
            storage_rank = 0
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
                if key == "storage" and desired == "positive":
                    storage_rank = self._storage_positive_rank(value)
                    if storage_rank >= 2:
                        bonus += 0.12
                    elif storage_rank == 1:
                        bonus += 0.06
                    elif storage_rank < 0:
                        bonus -= 0.08
                    continue
                polarity = self._infer_signal_polarity(value)
                if polarity == desired:
                    bonus += 0.08
                elif polarity and polarity != desired:
                    bonus -= 0.04

            adjusted_score = base_score + bonus
            adjusted_row = (*row[:-1], adjusted_score) if len(row) > 0 else row

            proximity_distance = float("inf")
            if ratio_proximity is not None:
                ratio_key, target, op = ratio_proximity
                ratio_idx = ratio_col_index.get(ratio_key)
                ratio_value = row[ratio_idx] if ratio_idx is not None and len(row) > ratio_idx else None
                proximity_distance = self._ratio_proximity_distance(ratio_value, target, op)

            rescored_docs.append((adjusted_score, storage_rank, proximity_distance, adjusted_row))

        if storage_priority and ratio_proximity is not None:
            rescored_docs.sort(key=lambda item: (-item[1], item[2], -item[0]))
        elif storage_priority:
            # 수납 선호 질의는 수납 우수(2) > 보통(1) > 미확인(0) > 미흡(-1) 순을 우선한다.
            rescored_docs.sort(key=lambda item: (item[1], item[0]), reverse=True)
        elif ratio_proximity is not None:
            # 비율 조건 질의는 기준값에 더 가까운 도면을 우선 노출한다.
            rescored_docs.sort(key=lambda item: (item[2], -item[0]))
        else:
            rescored_docs.sort(key=lambda item: item[0], reverse=True)
        return [row for _, _, _, row in rescored_docs]

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
               OR LOWER(regexp_replace(f.name, '\\.(png|jpg|jpeg|bmp|tif|tiff|webp)$', '', 'i')) = LOWER(%s)
            LIMIT 1
        """
        normalized = document_id.strip()
        with self.conn.cursor() as cur:
            cur.execute(sql, (normalized, normalized))
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
        space_labels_hint = self._extract_space_labels_from_document(document)
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
            "space_labels_hint": space_labels_hint,
            "similarity": similarity,
        }

    def _generate_document_id_answer(self, document_id: str, doc: tuple[Any, ...]) -> str:
        candidate = self._row_to_candidate(doc, rank=1)
        candidate_json = json.dumps(candidate, ensure_ascii=False, indent=2)

        system_prompt = """ You are a specialized assistant for architectural floor plan retrieval.
Purpose:
1) Sections 1 and 2 must follow the fixed format exactly, and
2) Section 3 should be rewritten into a user-friendly version of the original internal evaluation.

Important rules:
- Do not invent any new facts that are not present in the original text or the JSON.
- You may keep the evaluation wording(ex: 미흡, 부족, 우수) that already appears in the original text.
- The model must not add its own judgments, design suggestions, or improvement recommendations.
- Do not repeat the same facts redundantly.
- Rewrite the sentences in natural Korean.

Output Format (Must Be Preserved, Repeated for Each Floor Plan)
- All content must be written in Korean.

### 1. 검색된 도면 id: {document_id}

### 2. 도면 기본 정보 📊
■ 공간 구성 여부의 값은 다음 표현으로 고정한다.
true → 존재, false → 없음

출력 형식(고정):
■ **공간 개수**
• 방: {room_count}
• 화장실: {bathroom_count}
• Bay: {bay_count}
• 무창 공간: {windowless_count}
■ **전체 면적 대비 공간 비율 (%)**
• 거실: {living_room_ratio}
• 주방: {kitchen_ratio}
• 욕실: {bathroom_ratio}
• 발코니: {balcony_ratio}
■ **구조 및 성능**
• 건물 구조 유형: {structure_type}
• 환기: {ventilation_quality}
■ **공간 구성 여부**
• 특화 공간: {has_special_space}
• 기타 공간: {has_etc_space}

### 3. 도면 공간 구성 설명 🧩
Reformat the original internal evaluation into a user-friendly version, but strictly output it in the fixed format below.

구성 규칙:
* 원문과 JSON(document, document_signals)에 있는 사실만 사용한다.
* "기재되어 있습니다", "언급되어 있습니다", "서술되어 있습니다" 같은 메타 표현은 제거한다.
* "채광은(는)"처럼 어색한 조사 표기는 자연스러운 한국어로 정리한다.
* 모든 설명 문장은 존댓말(합니다/습니다 체)로 작성하고, 반말 종결(예: ~다, ~이다)은 사용하지 않는다.
* 수납 용어는 반드시 `드레스룸`으로 통일한다. `드레`, `스룸`, `드레+스룸` 같은 분리 표기는 금지한다.
* 기술 메모형 괄호 표기(예: `4Bay(통계 bay_count=4)`, `환기창(창호)`, `연결(door/window)`)는 절대 쓰지 않는다.
* 판단 근거가 불충분한 항목은 "정보가 부족해 판단이 어렵습니다"처럼 간결하게 표현한다.
* 같은 의미의 문장은 합치고, 중복 사실은 반복하지 않는다.
* `document_signals`가 있으면 해당 라벨과 일치하는 상태를 우선 반영한다.
* 비교 기준(예: 권장 30~40%, 30% 이하) 정보가 원문에 있을 때만 포함한다.
* 사실 범위를 벗어나는 단정은 금지한다.

출력 형식(고정):
■ 종합 등급: {compliance_grade}
• 적합 항목: {적합한 공간/요소를 콤마(,)로 나열, 없으면 없음}
• 부적합 항목: {부적합한 공간/요소를 콤마(,)로 나열, 없으면 없음}
■ **핵심 설계 평가**
• [평가 항목명]: ...
• [평가 항목명]: ...
■ **주요 공간별 상세 분석**
[공간명] ...
[공간명] ...

세부 형식 규칙:
* 제목은 `■ 종합 등급`, `■ 핵심 설계 평가`, `■ 주요 공간별 상세 분석` 세 개를 이 순서로 출력한다.
* `적합 항목`, `부적합 항목`은 반드시 채운다. 해당 없음이면 `없음`으로 출력한다.
* 핵심 설계 평가 라벨은 고정 텍스트를 강제하지 않고 `analysis_description` 기반으로 작성한다.
* 항목 라벨 뒤 괄호 상태 표기(예: `(좋음)`, `(미흡)`)를 쓰지 않는다.
* 공간 라벨은 `space_labels_hint`가 있으면 우선 반영하고, 없으면 원문 근거 기반으로 작성한다.
* 공간 라벨은 존재하는 항목만 작성하고, 각 줄을 `[공간명] 내용` 형식으로 쓴다.
* 라벨 표기는 `주방/식당`, `현관/기타` 형식으로 통일하고, `주방및식당`, `현관및기타공간` 표기는 금지한다.
* 동일 성격의 공간은 합쳐서 표기할 수 있다(예: 기타 7~10).
* 각 항목은 2~3문장으로 작성할 수 있다.
"""

        space_labels_hint_text = ", ".join(candidate.get("space_labels_hint", [])) or "없음"
        user_content = (
            f"입력 document_id:\n{document_id.strip()}\n\n"
            f"도면 데이터(JSON):\n{candidate_json}\n\n"
            f"허용 공간 라벨(space_labels_hint):\n{space_labels_hint_text}\n\n"
            "system_prompt의 출력 형식과 규칙을 정확히 지켜 단일 도면 기준으로 작성하세요.\n"
            f"첫 줄은 `1. 검색된 도면 id: {document_id.strip()}` 형식을 사용하세요."
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
                ratio_filter = self._coerce_ratio_filter(value)
                bounds = self._ratio_filter_to_bounds(ratio_filter)
                if not bounds:
                    continue
                for bound in bounds:
                    where_clauses.append(f"ratio_cmp({db_col}::double precision, %s, %s)")
                    params.extend([bound["op"], bound["val"]])
            else:
                where_clauses.append(f"{db_col} = %s")
                params.append(value)

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        return where_sql, params

    def _retrieve_hybrid(self, query_json: dict, top_k: int = 50, offset: int = 0) -> list:
        """
        Generate embedding -> build query -> execute DB query -> return results
        """
        filters = query_json.get("filters", {}) or {}
        documents = query_json.get("documents", "") or ""
        raw_query = query_json.get("raw_query", "") or ""
        semantic_query = f"{documents} {raw_query}".strip() or raw_query or documents
        text_query = str(documents).strip() or str(raw_query).strip()

        embedding_resp = self.client.embeddings.create(
            model=self.embedding_model,
            input=semantic_query,
            dimensions=self.embedding_dimensions,
        )
        embedding = embedding_resp.data[0].embedding
        embedding_vector = "[" + ",".join(map(str, embedding)) + "]"

        where_sql, filter_params = self._build_filter_where_parts(filters)
        params = [
            embedding_vector,
            text_query,
            *filter_params,
            self.vector_weight,
            self.text_weight,
            top_k,
            max(0, int(offset)),
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
            OFFSET %s
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
                    max(0, int(offset)),
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
                    OFFSET %s
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
        self,
        query: str,
        query_json: dict,
        docs: list,
        total_match_count: int,
        representative_limit: int = 3,
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
        top_n = max(1, int(representative_limit))
        top_docs = docs[:top_n]

        representative_ids = [row[1] for row in top_docs]
        representative_title = f"대표 도면 id(상위 {len(top_docs)}개)"
        candidates = [self._row_to_candidate(row, rank) for rank, row in enumerate(top_docs, start=1)]
        candidates_json = json.dumps(candidates, ensure_ascii=False, indent=2)

        system_prompt = """You are a specialized assistant for architectural floor plan retrieval.
Purpose:
1) Sections 1 and 2 must follow the fixed format exactly, and
2) Section 3 should be rewritten into a user-friendly version of the original internal evaluation.

Important rules:
- Do not invent any new facts that are not present in the original text or the JSON.
- You may keep the evaluation wording(ex: 미흡, 부족, 우수) that already appears in the original text.
- The model must not add its own judgments, design suggestions, or improvement recommendations.
- Do not repeat the same facts redundantly.
- Rewrite the sentences in natural Korean.

Output Format (Must Be Preserved, Repeated for Each Floor Plan)
- All content must be written in Korean.

조건을 만족하는 도면 총 개수: {total_count}

Repeat the format below **for each representative floor plan**.
### [도면 #{rank}] {document_id}

### 1. 도면 선택 근거 🔍
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
• 찾는 조건: {사용자 조건을 한국어 표현으로 나열}
• 일치 조건: {도면 메타데이터 및 document에서 확인된 일치 항목을 한국어 항목명=값 형태로 나열}

### 2. 도면 기본 정보 📊
■ 공간 구성 여부의 값은 다음 표현으로 고정한다.
true → 존재, false → 없음

출력 형식(고정):
■ 공간 개수
• 방: {room_count}
• 화장실: {bathroom_count}
• Bay: {bay_count}
• 무창 공간: {windowless_count}
■ 전체 면적 대비 공간 비율 (%)
• 거실: {living_room_ratio}
• 주방: {kitchen_ratio}
• 욕실: {bathroom_ratio}
• 발코니: {balcony_ratio}
■ 구조 및 성능
• 건물 구조 유형: {structure_type}
• 환기: {ventilation_quality}
■ 공간 구성 여부
• 특화 공간: {has_special_space}
• 기타 공간: {has_etc_space}

### 3. 도면 공간 구성 설명 🧩
Reformat the original internal evaluation into a user-friendly version, but strictly output it in the fixed format below.

구성 규칙:
* 원문과 JSON(document, document_signals)에 있는 사실만 사용한다.
* "기재되어 있습니다", "언급되어 있습니다", "서술되어 있습니다" 같은 메타 표현은 제거한다.
* "채광은(는)"처럼 어색한 조사 표기는 자연스러운 한국어로 정리한다.
* 모든 설명 문장은 존댓말(합니다/습니다 체)로 작성하고, 반말 종결(예: ~다, ~이다)은 사용하지 않는다.
* 수납 용어는 반드시 `드레스룸`으로 통일한다. `드레`, `스룸`, `드레+스룸` 같은 분리 표기는 금지한다.
* 기술 메모형 괄호 표기(예: `4Bay(통계 bay_count=4)`, `환기창(창호)`, `연결(door/window)`)는 절대 쓰지 않는다.
* 판단 근거가 불충분한 항목은 "정보가 부족해 판단이 어렵습니다"처럼 간결하게 표현한다.
* 같은 의미의 문장은 합치고, 중복 사실은 반복하지 않는다.
* `document_signals`가 있으면 해당 라벨과 일치하는 상태를 우선 반영한다.
* 비교 기준(예: 권장 30~40%, 30% 이하) 정보가 원문에 있을 때만 포함한다.
* 사실 범위를 벗어나는 단정은 금지한다.

출력 형식(고정):
■ 종합 등급: {compliance_grade}
• 적합 항목: {적합한 공간/요소를 콤마(,)로 나열, 없으면 없음}
• 부적합 항목: {부적합한 공간/요소를 콤마(,)로 나열, 없으면 없음}
■ 핵심 설계 평가
• [평가 항목명]: ...
• [평가 항목명]: ...
■ 주요 공간별 상세 분석
[공간명] ...
[공간명] ...

세부 형식 규칙:
* 제목은 `■ 종합 등급`, `■ 핵심 설계 평가`, `■ 주요 공간별 상세 분석` 세 개를 이 순서로 출력한다.
* `적합 항목`, `부적합 항목`은 반드시 채운다. 해당 없음이면 `없음`으로 출력한다.
* 핵심 설계 평가 라벨은 고정 텍스트를 강제하지 않고 `analysis_description` 기반으로 작성한다.
* 항목 라벨 뒤 괄호 상태 표기(예: `(좋음)`, `(미흡)`)를 쓰지 않는다.
* 공간 라벨은 `space_labels_hint`가 있으면 우선 반영하고, 없으면 원문 근거 기반으로 작성한다.
* 공간 라벨은 존재하는 항목만 작성하고, 각 줄을 `[공간명] 내용` 형식으로 쓴다.
* 라벨 표기는 `주방/식당`, `현관/기타` 형식으로 통일하고, `주방및식당`, `현관및기타공간` 표기는 금지한다.
* 동일 성격의 공간은 합쳐서 표기할 수 있다(예: 기타 7~10).
* 각 항목은 2~3문장으로 작성할 수 있다.
"""

        user_content = (
            f"검색된 도면 id(조회 결과 목록):\n{id_list_text}\n\n"
            f"{representative_title}:\n{', '.join(representative_ids)}\n\n"
            f"조건 일치 전체 건수(total_count):\n{total_match_count}\n\n"
            f"사용자가 설정한 검색 조건:\n{filters_json}\n\n"
            f"대표 도면 데이터(순위/메타데이터/document/similarity):\n{candidates_json}\n\n"
            "system_prompt의 출력 형식과 규칙을 정확히 지켜 각 대표 도면을 작성하세요.\n\n"
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

    def _reset_more_results_state(self) -> None:
        self.current_offset = 0
        self._last_query_json_for_more = None
        self._last_query_text_for_more = ""
        self._last_total_match_count_for_more = 0
        self._returned_floorplan_ids_for_more = set()
        self._returned_floorplan_names_for_more = set()

    def _append_chat_history(self, entry: dict[str, Any]) -> None:
        self.chat_history.append(entry)
        overflow = len(self.chat_history) - max(1, int(self.max_chat_history))
        if overflow > 0:
            del self.chat_history[:overflow]

    def _get_latest_more_context_from_history(self) -> Optional[dict[str, Any]]:
        for entry in reversed(self.chat_history):
            if entry.get("type") == "more_context":
                return entry
        return None

    def _sync_more_context_to_state(self, context: dict[str, Any]) -> None:
        self.current_offset = max(0, int(context.get("current_offset", 0) or 0))
        self._last_query_json_for_more = copy.deepcopy(context.get("query_json") or {})
        self._last_query_text_for_more = str(context.get("query_text") or "").strip()
        self._last_total_match_count_for_more = max(
            0, int(context.get("total_match_count", 0) or 0)
        )
        self._returned_floorplan_ids_for_more = {
            int(v) for v in (context.get("returned_floorplan_ids") or []) if v is not None
        }
        self._returned_floorplan_names_for_more = {
            str(v).strip()
            for v in (context.get("returned_floorplan_names") or [])
            if v is not None and str(v).strip()
        }

    def _build_more_context_from_state(self) -> Optional[dict[str, Any]]:
        if self._last_query_json_for_more is None:
            return None
        return {
            "type": "more_context",
            "query_json": copy.deepcopy(self._last_query_json_for_more),
            "query_text": self._last_query_text_for_more,
            "total_match_count": int(self._last_total_match_count_for_more),
            "current_offset": int(self.current_offset),
            "returned_floorplan_ids": sorted(self._returned_floorplan_ids_for_more),
            "returned_floorplan_names": sorted(self._returned_floorplan_names_for_more),
            "updated_at": time.time(),
        }

    def _drop_more_context_from_history(self) -> None:
        self.chat_history = [entry for entry in self.chat_history if entry.get("type") != "more_context"]

    def _fetch_recent_chat_history_rows(
        self, chat_room_id: int, limit: int = 40
    ) -> list[tuple[str, str]]:
        sql = """
            SELECT question, answer
            FROM chat_history
            WHERE chatroom_id = %s
            ORDER BY id DESC
            LIMIT %s
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (int(chat_room_id), int(limit)))
                rows = cur.fetchall()
            return [(str(r[0] or ""), str(r[1] or "")) for r in rows]
        except Exception as exc:
            self.conn.rollback()
            self._log_event(
                event="chat_history_read_failed",
                level=logging.WARNING,
                chat_room_id=chat_room_id,
                error=str(exc),
            )
            return []

    def _extract_document_ids_from_answer(self, answer: str) -> list[str]:
        text = str(answer or "")
        if not text:
            return []
        ids: list[str] = []
        for match in self.FLOORPLAN_BLOCK_HEADER_RE.finditer(text):
            doc_id = re.sub(r"\s+", " ", match.group("document_id")).strip()
            if doc_id and doc_id not in ids:
                ids.append(doc_id)
        return ids

    def _build_more_context_from_chat_history(
        self, chat_room_id: Optional[int]
    ) -> Optional[dict[str, Any]]:
        if chat_room_id is None:
            return None

        rows = self._fetch_recent_chat_history_rows(chat_room_id=chat_room_id, limit=50)
        if not rows:
            return None

        total_shown = 0
        base_query = ""
        returned_doc_names: list[str] = []

        for question, answer in rows:
            q = str(question or "").strip()
            doc_ids = self._extract_document_ids_from_answer(answer)
            shown = len(doc_ids)
            is_more_query = self._parse_more_results_request_count(q) is not None

            if shown <= 0:
                if is_more_query:
                    continue
                break

            total_shown += shown
            for doc_name in doc_ids:
                if doc_name not in returned_doc_names:
                    returned_doc_names.append(doc_name)

            if is_more_query:
                continue

            base_query = q
            break

        if not base_query or total_shown <= 0:
            return None

        query_json = self._analyze_query(base_query)
        try:
            total_match_count = self._count_matches(
                query_json.get("filters", {}) or {},
                query_json.get("documents", "") or "",
            )
        except Exception:
            total_match_count = total_shown

        context = {
            "type": "more_context",
            "query_text": base_query,
            "query_json": query_json,
            "total_match_count": max(total_shown, int(total_match_count)),
            "current_offset": int(total_shown),
            "returned_floorplan_ids": [],
            "returned_floorplan_names": returned_doc_names,
            "updated_at": time.time(),
        }
        self._log_event(
            event="chat_history_more_context_loaded",
            chat_room_id=chat_room_id,
            base_query=base_query[:120],
            current_offset=int(total_shown),
            loaded_doc_count=len(returned_doc_names),
        )
        return context

    def _parse_more_results_request_count(self, query: str) -> Optional[int]:
        text = str(query or "").strip()
        if not text:
            return None
        count_match = self.MORE_RESULTS_COUNT_REQUEST_RE.fullmatch(text)
        if count_match:
            count_text = count_match.group("count")
            try:
                count = int(count_text)
            except Exception:
                return None
            return max(1, count)
        default_match = self.MORE_RESULTS_DEFAULT_REQUEST_RE.fullmatch(text)
        if default_match:
            return 3
        return None

    def _remember_more_results_context(
        self,
        query_text: str,
        query_json: dict[str, Any],
        total_match_count: int,
        initial_docs: list[tuple[Any, ...]],
    ) -> None:
        context = {
            "type": "more_context",
            "query_text": str(query_text or "").strip(),
            "query_json": copy.deepcopy(query_json),
            "total_match_count": max(0, int(total_match_count)),
            "current_offset": len(initial_docs or []),
            "returned_floorplan_ids": [
                int(row[0]) for row in (initial_docs or []) if row and row[0] is not None
            ],
            "returned_floorplan_names": [
                str(row[1]).strip()
                for row in (initial_docs or [])
                if row and row[1] is not None and str(row[1]).strip()
            ],
            "updated_at": time.time(),
        }
        self._append_chat_history(context)
        self._sync_more_context_to_state(context)

    def _handle_more_results_request(
        self, requested_count: int, chat_room_id: Optional[int] = None
    ) -> dict[str, Any]:
        if requested_count <= 0:
            return {"answer": "[]", "floorplan_ids": []}

        context = self._get_latest_more_context_from_history()
        if context is None:
            context = self._build_more_context_from_state()
            if context is None:
                context = self._build_more_context_from_chat_history(chat_room_id)
                if context is not None:
                    self._append_chat_history(context)
            if context is None:
                return {"answer": "[]", "floorplan_ids": []}
        self._sync_more_context_to_state(context)

        selected_docs: list[tuple[Any, ...]] = []
        floorplan_ids: list[int] = []
        local_offset = max(0, int(self.current_offset))
        seen_ids = set(self._returned_floorplan_ids_for_more or set())
        seen_names = set(self._returned_floorplan_names_for_more or set())
        rounds = 0

        while len(selected_docs) < requested_count:
            rounds += 1
            if rounds > 20:
                break
            remaining = requested_count - len(selected_docs)
            batch_limit = max(remaining, 1)
            docs = self._retrieve_hybrid(
                query_json=self._last_query_json_for_more,
                top_k=batch_limit,
                offset=local_offset,
            )
            if not docs:
                break
            local_offset += len(docs)

            for row in docs:
                if not row or len(row) < 2:
                    continue
                floorplan_id = row[0]
                floorplan_name = str(row[1] or "").strip()
                if floorplan_id is None or not floorplan_name:
                    continue
                try:
                    floorplan_id_int = int(floorplan_id)
                except Exception:
                    continue
                if floorplan_id_int in seen_ids or floorplan_name in seen_names:
                    continue
                seen_ids.add(floorplan_id_int)
                seen_names.add(floorplan_name)
                selected_docs.append(row)
                floorplan_ids.append(floorplan_id_int)
                if len(selected_docs) >= requested_count:
                    break

            if len(docs) < batch_limit:
                break

        self.current_offset = local_offset
        self._returned_floorplan_ids_for_more = seen_ids
        self._returned_floorplan_names_for_more = seen_names
        context["current_offset"] = self.current_offset
        context["returned_floorplan_ids"] = sorted(self._returned_floorplan_ids_for_more)
        context["returned_floorplan_names"] = sorted(self._returned_floorplan_names_for_more)
        context["updated_at"] = time.time()
        self._sync_more_context_to_state(context)
        query_text = (
            self._last_query_text_for_more
            or str(self._last_query_json_for_more.get("raw_query") or "").strip()
            or str(self._last_query_json_for_more.get("documents") or "").strip()
        )
        answer = self._generate_answer(
            query=query_text,
            query_json=self._last_query_json_for_more,
            docs=selected_docs,
            total_match_count=self._last_total_match_count_for_more,
            representative_limit=requested_count,
        )
        self._append_chat_history(
            {
                "type": "assistant_more_response",
                "requested_count": int(requested_count),
                "returned_count": len(selected_docs),
                "names": [str(row[1]) for row in selected_docs if row and len(row) > 1],
                "answer_preview": answer[:500],
                "updated_at": time.time(),
            }
        )
        return {"answer": answer, "floorplan_ids": floorplan_ids}


# ----------------------------------------------------------------------------------------------
    def run(
        self,
        query: str,
        email: str = "",
        chat_room_id: Optional[int] = None,
    ) -> dict[str, Any]:
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
            self._append_chat_history(
                {"type": "user_query", "query": normalized_query, "updated_at": time.time()}
            )
            more_count = self._parse_more_results_request_count(normalized_query)
            if more_count is not None:
                more_start = time.perf_counter()
                paged = self._handle_more_results_request(
                    requested_count=more_count,
                    chat_room_id=chat_room_id,
                )
                self._log_event(
                    event="query_completed",
                    query_id=query_id,
                    mode="general_more",
                    result="ok",
                    requested_count=more_count,
                    returned_count=len(paged.get("floorplan_ids", []) or []),
                    current_offset=self.current_offset,
                    latency_ms=int((time.perf_counter() - more_start) * 1000),
                )
                return paged

            self._reset_more_results_state()
            self._drop_more_context_from_history()
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
                    self._append_chat_history(
                        {
                            "type": "assistant_response",
                            "mode": "document_id",
                            "answer_preview": answer[:500],
                            "updated_at": time.time(),
                        }
                    )
                    return {"answer": answer, "floorplan_ids": []}
                generate_start = time.perf_counter()
                matched_document_id = str(doc[1] or "").strip() or normalized_query
                answer = self._generate_document_id_answer(matched_document_id, doc)
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
                self._append_chat_history(
                    {
                        "type": "assistant_response",
                        "mode": "document_id",
                        "answer_preview": answer[:500],
                        "updated_at": time.time(),
                    }
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
                self._reset_more_results_state()
                answer = self._generate_validated_no_match_answer(total_match_count=0)
                self._log_event(
                    event="query_completed",
                    query_id=query_id,
                    mode="general",
                    result="no_match",
                    latency_ms=int((time.perf_counter() - request_start) * 1000),
                )
                self._append_chat_history(
                    {
                        "type": "assistant_response",
                        "mode": "general",
                        "answer_preview": answer[:500],
                        "updated_at": time.time(),
                    }
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
            docs = self._rerank_by_query_signal_preferences(
                docs,
                normalized_query,
                query_json.get("filters", {}) or {},
            )
            self._log_event(
                event="rerank_complete",
                query_id=query_id,
                latency_ms=int((time.perf_counter() - rerank_start) * 1000),
                reranked_count=len(docs),
            )

            floorplan_ids = [row[0] for row in docs[:3]]
            self._remember_more_results_context(
                query_text=normalized_query,
                query_json=query_json,
                total_match_count=total_match_count,
                initial_docs=docs[:3],
            )

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
            self._append_chat_history(
                {
                    "type": "assistant_response",
                    "mode": "general",
                    "answer_preview": answer[:500],
                    "returned_floorplan_ids": floorplan_ids,
                    "updated_at": time.time(),
                }
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