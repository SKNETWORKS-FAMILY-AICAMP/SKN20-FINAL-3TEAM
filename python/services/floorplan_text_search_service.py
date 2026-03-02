import json
import logging
import os
import re
import time
import uuid
import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from openai import OpenAI
from services.runpod_client import embed_text_sync


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
        "ventilation_quality",
        "has_special_space",
        "has_etc_space",
    ]

    FILTER_ALIASES = {
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
    DOCUMENT_COMPLIANCE_ITEM_LABEL_RE = re.compile(
        r"(채광(?:\s*및\s*쾌적성)?|daylight(?:ing|ling)?|lighting|환기|ventilation|가족\s*융화|가족융화|family_community|family_harmony|수납(?:\s*공간)?|storage)\s*(?:은\(는\)|은|는|이|가|:|=)\s*",
        re.IGNORECASE,
    )
    DOCUMENT_COMPLIANCE_POSITIVE_RE = re.compile(
        r"(우수|양호|적정|적합|충분|넉넉|충족|확보|부합|범위\s*내|원활|좋|유리|풍부|넓)",
        re.IGNORECASE,
    )
    DOCUMENT_COMPLIANCE_NEGATIVE_RE = re.compile(
        r"(미흡|부족|부적합|불합격|미달|초과|무창|없음|없다|불리|불충분|권장[^,.\n]{0,30}(?:초과|미달)|기준[^,.\n]{0,30}(?:초과|미달))",
        re.IGNORECASE,
    )
    DOCUMENT_COMPLIANCE_UNCERTAIN_RE = re.compile(
        r"(불명확|확실하지\s*않|확정할\s*수\s*없|정보가\s*부족|평가\s*불가|판단\s*불가|미확인|어렵)",
        re.IGNORECASE,
    )
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
    WINDOWLESS_QUERY_ALIAS_RE = re.compile(
        r"(무창\s*공간|무창실|무창|창문이\s*없는(?:\s*공간)?|창문\s*없는(?:\s*공간)?|창\s*없는(?:\s*공간)?|노창)",
        re.IGNORECASE,
    )
    DOC_RATIO_TOKEN_RE = re.compile(
        r"(%|퍼센트|비율|ratio|이상|이하|초과|미만|동일)",
        re.IGNORECASE,
    )
    SEMANTIC_COUNT_SIMILARITY_THRESHOLD = 0.55
    STORAGE_RATIO_QUERY_TARGET_RE = re.compile(
        r"(수납(?:\s*공간)?|storage|드레스룸|팬트리)",
        re.IGNORECASE,
    )
    LDK_RATIO_QUERY_TARGET_RE = re.compile(
        r"(ldk|엘디케이|리빙\s*다이닝\s*키친|living\s*dining\s*kitchen)",
        re.IGNORECASE,
    )
    WINDOWLESS_RATIO_DOC_KEYWORD_RE = re.compile(
        r"(무창(?:\s*공간|\s*실)?|노창|창문(?:이)?\s*없는|창\s*없는)",
        re.IGNORECASE,
    )
    STORAGE_RATIO_DOC_KEYWORD_RE = re.compile(
        r"(수납(?:\s*공간)?|storage|드레스룸|팬트리)",
        re.IGNORECASE,
    )
    LDK_RATIO_DOC_KEYWORD_RE = re.compile(
        r"(ldk|엘디케이|리빙\s*다이닝\s*키친|living\s*dining\s*kitchen)",
        re.IGNORECASE,
    )
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
    MATCH_CONDITION_LIGHTING_PART_RE = re.compile(
        r"^(?:채광(?:\s*및\s*쾌적성)?|daylight(?:ing|ling)?|lighting)\s*(?:=|:)\s*",
        re.IGNORECASE,
    )
    MATCH_CONDITION_VENTILATION_PART_RE = re.compile(
        r"^환기\s*(?:=|:)\s*",
        re.IGNORECASE,
    )
    MATCH_CONDITION_FAMILY_HARMONY_PART_RE = re.compile(
        r"^가족\s*융화\s*(?:=|:)\s*",
        re.IGNORECASE,
    )
    MATCH_CONDITION_STORAGE_PART_RE = re.compile(
        r"^수납(?:\s*공간)?(?:\s*비율)?\s*(?:=|:)\s*",
        re.IGNORECASE,
    )
    SIGNAL_UNCERTAIN_TEXT_RE = re.compile(
        r"(불명확|확실하지\s*않|확정할\s*수\s*없|정보가\s*부족|평가\s*불가|판단\s*불가|미확인|어렵)",
        re.IGNORECASE,
    )
    SIGNAL_UNCERTAIN_LINE_HINTS = {
        "lighting": re.compile(r"(?:\[\s*채광\s*\]|채광|일조|창|창호)", re.IGNORECASE),
        "ventilation": re.compile(r"(?:\[\s*환기\s*\]|환기)", re.IGNORECASE),
        "family_harmony": re.compile(
            r"(?:\[\s*가족\s*융화\s*\]|가족\s*융화|가족융화|family_harmony|family_community)",
            re.IGNORECASE,
        ),
        "storage": re.compile(r"(?:\[\s*수납\s*\]|수납|드레스룸|팬트리)", re.IGNORECASE),
    }
    SIGNAL_CANONICAL_LABEL_TO_KEY = {
        "채광": "lighting",
        "환기": "ventilation",
        "가족 융화": "family_harmony",
        "수납": "storage",
    }
    MATCH_CONDITION_SIGNAL_PART_PATTERNS = {
        "lighting": MATCH_CONDITION_LIGHTING_PART_RE,
        "ventilation": MATCH_CONDITION_VENTILATION_PART_RE,
        "family_harmony": MATCH_CONDITION_FAMILY_HARMONY_PART_RE,
        "storage": MATCH_CONDITION_STORAGE_PART_RE,
    }
    BALCONY_POSITIVE_HINT_RE = re.compile(
        r"(활용도\s*높|활용\s*가능|외부\s*공간.*활용|연결.*원활|채광.*좋|넓)",
        re.IGNORECASE,
    )
    BALCONY_NEGATIVE_HINT_RE = re.compile(
        r"(활용도\s*낮|활용\s*어려|연결.*불편|채광.*부족|좁|없음)",
        re.IGNORECASE,
    )
    LIGHTING_SENTENCE_POSITIVE_RE = re.compile(
        r"(채광|일조|창|창호).{0,45}(우수|양호|좋|밝|풍부|충분|유리|확보)|(우수|양호|좋|밝|풍부|충분|유리|확보).{0,45}(채광|일조|창|창호)",
        re.IGNORECASE,
    )
    LIGHTING_SENTENCE_NEGATIVE_RE = re.compile(
        r"(채광|일조|창|창호).{0,45}(미흡|부족|어둡|불리|나쁘|없음|없다|미확인)|(미흡|부족|어둡|불리|나쁘|없음|없다|미확인).{0,45}(채광|일조|창|창호)",
        re.IGNORECASE,
    )
    LIGHTING_WINDOW_POSITIVE_RE = re.compile(
        r"(창|창호).{0,30}(확보|충분|풍부|넓).{0,30}(채광|일조)",
        re.IGNORECASE,
    )
    LIGHTING_WINDOW_NEGATIVE_RE = re.compile(
        r"(창|창호).{0,30}(없|부족|미확인|불리).{0,30}(채광|일조)",
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
    LOCAL_EMBEDDING_MODEL_MAP = {
        "qwen3-embedding-0.6b": "Qwen/Qwen3-Embedding-0.6B",
        "qwen/qwen3-embedding-0.6b": "Qwen/Qwen3-Embedding-0.6B",
    }

    def __init__(
        self,
        db_config,
        openai_api_key,
        embedding_model: str = "qwen3-embedding-0.6b",
        embedding_dimensions: int = 1024,
        vector_weight: float = 0.8,
        text_weight: float = 0.2,
        answer_validation_enabled: bool = True,
        answer_validation_retry_max: int = 1,
        answer_validation_safe_fallback: bool = True,
        enable_parallel: bool = True,
        parallel_workers: int = 2,
        db_pool_minconn: int = 1,
        db_pool_maxconn: int = 6,
        llm_backend: str = "openai",
        vllm_base_url: str = "",
        vllm_search_model_name: str = "",
        enable_chunk_parallel_generation: bool = True,
        chunk_parallel_workers: int = 3,
        chunk_parallel_min_docs: int = 2,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.WARNING,
                format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            )

        self.conn = psycopg2.connect(**db_config)
        self.enable_parallel = bool(enable_parallel)
        self.parallel_workers = max(1, int(parallel_workers))
        self.db_pool_minconn = max(1, int(db_pool_minconn))
        self.db_pool_maxconn = max(self.db_pool_minconn, int(db_pool_maxconn))
        self.db_pool: Optional[ThreadedConnectionPool] = None
        if self.enable_parallel:
            try:
                self.db_pool = ThreadedConnectionPool(
                    minconn=self.db_pool_minconn,
                    maxconn=self.db_pool_maxconn,
                    **db_config,
                )
            except Exception as exc:
                self.enable_parallel = False
                self.db_pool = None
                self.logger.warning("Failed to initialize DB connection pool: %s", exc)
        self._executor: Optional[ThreadPoolExecutor] = (
            ThreadPoolExecutor(max_workers=self.parallel_workers)
            if self.enable_parallel
            else None
        )
        self.enable_chunk_parallel_generation = bool(enable_chunk_parallel_generation)
        self.chunk_parallel_workers = max(1, int(chunk_parallel_workers))
        self.chunk_parallel_min_docs = max(1, int(chunk_parallel_min_docs))
        self._ensure_ratio_cmp_function()
        self.llm_backend = llm_backend
        if llm_backend == "vllm" and vllm_base_url:
            self.client = OpenAI(api_key="EMPTY", base_url=vllm_base_url)
            self.llm_model_name = vllm_search_model_name or "search_agent"
        else:
            self.client = OpenAI(api_key=openai_api_key)
            self.llm_model_name = "gpt-5.2-2025-12-11"
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

    def _acquire_conn(self) -> tuple[Any, bool]:
        if self.db_pool is None:
            return self.conn, False
        return self.db_pool.getconn(), True

    def _release_conn(self, conn: Any, pooled: bool) -> None:
        if pooled and self.db_pool is not None and conn is not None:
            self.db_pool.putconn(conn)

    def _run_count_task(self, query_json: dict[str, Any]) -> dict[str, int]:
        conn, pooled = self._acquire_conn()
        try:
            filters = query_json.get("filters", {}) or {}
            documents = query_json.get("documents", "") or ""
            return self._count_matches_context(filters, documents, conn=conn)
        finally:
            self._release_conn(conn, pooled)

    def _run_retrieve_task(
        self, query_json: dict[str, Any], retrieve_k_hint: int = 50
    ) -> list:
        conn, pooled = self._acquire_conn()
        try:
            return self._retrieve_hybrid(
                query_json,
                top_k=max(1, int(retrieve_k_hint)),
                conn=conn,
            )
        finally:
            self._release_conn(conn, pooled)

    def _embed_text(self, text: str) -> list[float]:
        """RunPod Serverless를 통한 텍스트 임베딩 (Qwen3-Embedding-0.6B)"""
        embedding = embed_text_sync(text[:8000])
        if len(embedding) != self.embedding_dimensions:
            raise ValueError(
                "Embedding dimension mismatch: "
                f"expected={self.embedding_dimensions}, actual={len(embedding)}"
            )
        return embedding

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
            normalized_label = self._normalize_space_label_for_output(compacted)
            return f"{prefix}{normalized_label}{sep}{body}"

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
        normalized = re.sub(
            r"(?mi)^(\s*(?:[-•]\s*)?)(?:elev\.?\s*홀|elev\.?\s*hall|elevator\s*hall|엘리베이터\s*홀)\s*:\s*",
            r"\1엘리베이터홀: ",
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
                line_by_label: dict[str, str] = {}
                for line in body.splitlines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    bracket_match = re.match(
                        r"^\s*(?:[-•]\s*)?\[(?P<label>[^\]\n]+)\]\s*(?::\s*|\s+)?(?P<content>.+?)\s*$",
                        line,
                    )
                    if bracket_match:
                        label = self._normalize_core_eval_label_for_output(bracket_match.group("label"))
                        if not label:
                            label = re.sub(r"\s+", " ", bracket_match.group("label")).strip()
                        content = re.sub(r"\s+", " ", bracket_match.group("content")).strip()
                        if label and content:
                            existing = line_by_label.get(label)
                            if not existing:
                                line_by_label[label] = content
                            elif content not in existing:
                                line_by_label[label] = f"{existing} {content}"
                        continue
                    line_match = re.match(
                        r"^\s*(?:[-•]\s*)?(?P<label>[^:\n\[\]]+)\s*:\s*(?P<content>.+?)\s*$",
                        line,
                    )
                    if line_match:
                        label = self._normalize_core_eval_label_for_output(line_match.group("label"))
                        if not label:
                            label = re.sub(r"\s+", " ", line_match.group("label")).strip()
                        content = re.sub(r"\s+", " ", line_match.group("content")).strip()
                        if label and content:
                            existing = line_by_label.get(label)
                            if not existing:
                                line_by_label[label] = content
                            elif content not in existing:
                                line_by_label[label] = f"{existing} {content}"
                        continue

                    bare_match = re.match(
                        r"^\s*(?:[-•]\s*)?(?P<label>채광|환기|가족\s*융화|수납)\s+(?P<content>.+?)\s*$",
                        stripped,
                    )
                    if bare_match:
                        label = self._normalize_core_eval_label_for_output(bare_match.group("label"))
                        content = re.sub(r"\s+", " ", bare_match.group("content")).strip()
                        if label and content:
                            existing = line_by_label.get(label)
                            if not existing:
                                line_by_label[label] = content
                            elif content not in existing:
                                line_by_label[label] = f"{existing} {content}"
                        continue

                    normalized_lines.append(stripped)

                for label, content in line_by_label.items():
                    normalized_lines.append(f"[{label}] {content}")
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
            r"(?s)(?P<header>3\.\s*도면\s*공간\s*구성\s*설명(?:\s*🧩)?\s*)(?P<body>.*?)(?=\n(?:#{1,6}\s*)?\[\s*도면\s*#|\Z)"
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

    def _normalize_requested_tone_phrasing(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return text
        text = re.sub(
            r"정보가\s*부족해\s*판단이\s*어렵습니다\.?",
            "정보가 부족합니다.",
            text,
        )
        text = re.sub(
            r"기능을\s*확정하기\s*어렵습니다\.?",
            "기능을 확정할 수 없습니다.",
            text,
        )
        return text

    def _normalize_floorplan_block_breaks(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return text
        text = re.sub(r"(?<!^)(?<!\n)\s*((?:#{1,6}\s*)?\[\s*도면\s*#\d+\])", r"\n\1", text)
        text = re.sub(r"(?m)([^\n])\n((?:#{1,6}\s*)?\[\s*도면\s*#\d+\])", r"\1\n\n\2", text)

        return re.sub(r"\n{3,}((?:#{1,6}\s*)?\[\s*도면\s*#\d+\])", r"\n\n\1", text)

    def _normalize_generated_answer(self, answer: str) -> str:
        return self._normalize_floorplan_block_breaks(
            self._merge_duplicate_storage_lines(
            self._normalize_storage_alias_terms(
            self._normalize_meta_expressions(
                self._normalize_summary_signal_sentence(
                    self._normalize_signal_tone_phrasing(
                    self._normalize_requested_tone_phrasing(
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
            )
        ))

    def _extract_layout_section_text(self, answer: str) -> str:
        text = str(answer or "")
        if not text:
            return ""
        match = re.search(
            r"(?s)3\.\s*도면\s*공간\s*구성\s*설명(?:\s*🧩)?\s*(?P<section>.*)$",
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
            r"(?s)3\.\s*도면\s*공간\s*구성\s*설명(?:\s*🧩)?\s*(?P<section>.*?)(?=\n(?:#{1,6}\s*)?\[\s*도면\s*#|\Z)",
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
            if re.match(r"^(?:[-•·]\s*)?\[[^\]\n]+\](?:\s*:\s*|\s+).+$", stripped):
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
        safe_default_answer = self._build_safe_default_answer(
            mode=normalized_mode,
            expected_document_id=expected_document_id,
        )
        if text.strip() == str(safe_default_answer or "").strip():
            has_document_id_token = True
            has_metadata_summary = True
            has_layout_summary = True
            return AnswerValidationResult(
                ok=is_non_empty,
                has_document_id_token=has_document_id_token,
                has_metadata_summary=has_metadata_summary,
                has_layout_summary=has_layout_summary,
                missing_fields=missing_fields,
            )

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
            has_document_id_token = True
        elif normalized_mode == "general":
            has_document_id_token = True
            if not re.search(
                r"(?m)^\s*조건을\s*만족하는\s*도면\s*총\s*개수\s*:\s*\d+\s*$",
                text,
                flags=re.IGNORECASE,
            ):
                missing_fields.append("general_total_count_line")

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
                f"응답 형식 검증에 실패했습니다. 잠시 후 다시 시도하세요."
            )
        if normalized_mode == "general":
            return (
                "응답 형식 검증에 실패했습니다. 잠시 후 다시 시도하세요."
            )
        if normalized_mode == "no_match":
            return (
                "조건을 만족하는 도면 총 개수: 0\n"
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

    def _normalize_windowless_aliases(self, query: str) -> str:
        text = str(query or "")
        if not text:
            return text
        normalized = self.WINDOWLESS_QUERY_ALIAS_RE.sub("무창 공간", text)
        normalized = re.sub(r"(무창\s*공간)(?:\s*무창\s*공간)+", r"\1", normalized)
        normalized = re.sub(r"\s{2,}", " ", normalized)
        return normalized.strip()

    def _looks_like_analysis_description(self, text: str) -> bool:
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        if len(normalized) < 120:
            return False

        section_patterns = (
            r"\[\s*전체\s*평가\s*\]",
            r"\[\s*설계\s*평가\s*\]",
            r"\[\s*공간\s*분석\s*\]",
        )
        signal_patterns = (
            r"(채광|환기|가족\s*융화|가족융화|수납)은\(는\)",
            r"무창\s*공간\s*비율",
        )

        section_hits = sum(
            1 for pattern in section_patterns if re.search(pattern, normalized, flags=re.IGNORECASE)
        )
        signal_hits = sum(
            1 for pattern in signal_patterns if re.search(pattern, normalized, flags=re.IGNORECASE)
        )

        if section_hits >= 2:
            return True
        return section_hits >= 1 and signal_hits >= 1 and len(normalized) >= 180

    def _analyze_query(self, query: str) -> dict:
        """ 
        LLM: query -> JSON (filters, documents)
        """
        normalized_query = self._normalize_windowless_aliases(query)
        if self._looks_like_analysis_description(normalized_query):
            return {
                "filters": {},
                "documents": normalized_query,
                "raw_query": normalized_query,
            }
        word_rules_text = json.dumps(self.word_dict, ensure_ascii=False, indent=2)
        system_prompt = (
                "You are a query analyzer for architectural floorplan retrieval.\n"
    "Your sole task: parse a Korean-language user query and return a structured JSON object.\n"
    "\n"
    "## OUTPUT REQUIREMENTS\n"
    "- Respond with ONLY valid JSON. No explanation, no markdown, no code fences.\n"
    "- All Korean string values must be preserved as-is (UTF-8).\n"
    "- If no filter condition applies, use an empty object for 'filters'.\n"
    "- 'documents' is ALWAYS required; use an empty string \"\" if no descriptive intent is found.\n"
    "\n"
    
    # --- SCHEMA ---
    "## JSON SCHEMA\n"
    "{\n"
    "  \"filters\": {\n"
    "    \"windowless_count\":  {\"op\": \"이상|이하|초과|미만|동일\", \"val\": <integer>},  // optional\n"
    "    \"balcony_ratio\":     {\"op\": \"이상|이하|초과|미만|동일\", \"val\": <number>},   // optional\n"
    "    \"living_room_ratio\": {\"op\": \"이상|이하|초과|미만|동일\", \"val\": <number>},   // optional\n"
    "    \"bathroom_ratio\":    {\"op\": \"이상|이하|초과|미만|동일\", \"val\": <number>},   // optional\n"
    "    \"kitchen_ratio\":     {\"op\": \"이상|이하|초과|미만|동일\", \"val\": <number>},   // optional\n"
    "    \"structure_type\":    <string>,   // optional\n"
    "    \"bay_count\":         <integer>,  // optional\n"
    "    \"room_count\":        <integer>,  // optional\n"
    "    \"bathroom_count\":    <integer>,  // optional\n"
    "    \"compliance_grade\":  <string>,   // optional\n"
    "    \"ventilation_quality\": <string>,   // optional\n"
    "    \"has_special_space\": <boolean>,  // optional — set ONLY when condition is met\n"
    "    \"has_etc_space\":     <boolean>   // optional — set ONLY when condition is met\n"
    "  },\n"
    "  \"documents\": <string>  // REQUIRED — abstract or descriptive intent from query\n"
    "}\n"
    "\n"
    
    # --- MAPPING RULES ---
    "## MAPPING RULES\n"
    "\n"
    "**Rule 1 — Normalization:**\n"
    "Map all user terms to standardized space names using normalization_rules in the synonym data below.\n"
    "\n"
    "**Rule 2 — 기타공간 Classification:**\n"
    "If a mapped/mentioned space appears in special_classification['기타공간'] "
    "(or category_groups['기타공간']), set \"has_etc_space\": true in filters.\n"
    "\n"
    "**Rule 3 — 특화공간 Classification:**\n"
    "If a mapped/mentioned space appears in special_classification['특화공간'] "
    "(or category_groups['특화공간']), set \"has_special_space\": true in filters.\n"
    "\n"
    "**Rule 4 — Filters vs. Documents split:**\n"
    "- Map explicit, structured constraints (counts, ratios, grades, types) → filters\n"
    "- Map abstract, qualitative, or descriptive intent → documents\n"
    "- A query may populate BOTH filters and documents at the same time.\n"
    "\n"
    
    # --- NEGATIVE RULES ---
    "## DO NOT\n"
    "- Do NOT add has_special_space or has_etc_space unless the space explicitly matches the classification lists.\n"
    "- Do NOT omit the 'documents' field — always include it even if value is \"\".\n"
    "- Do NOT include filters keys with null values — omit the key entirely if not applicable.\n"
    "- Do NOT wrap output in markdown code fences or add any text outside the JSON object.\n"
    "\n"
   
    # --- FEW-SHOT EXAMPLES ─---
    "\n"
    "Input: \"방 3개에 욕실 2개인 평면 찾아줘\"\n"
    "Output: {\"filters\": {\"room_count\": 3, \"bathroom_count\": 2}, \"documents\": \"\"}\n"
    "\n"
    "Input: \"발코니 비율이 15% 이상인 발코니 활용도가 좋은 평면\"\n"
    "Output: {\"filters\": {\"balcony_ratio\": {\"op\": \"이상\", \"val\": 15}}, "
    "\"documents\": \"발코니 활용도가 좋은\"}\n"
    "\n"
    "Input: \"무창실이 10개 미만이고 환기등급이 양호인 구조\"\n"
    "Output: {\"filters\": {\"windowless_count\": {\"op\": \"미만\", \"val\": 10}, "
    "\"ventilation_quality\": \"양호\"}, \"documents\": \"\"}\n"
    "\n"
    "Input: \"채광이 좋고 거실이 넓은 구조\"\n"
    "Output: {\"filters\": {}, \"documents\": \"채광이 좋고 거실이 넓은 개방형 평면\"}\n"
    "\n"
    "Input: \"드레스룸 있는 4베이 판상형 평면\"\n"
    "Output: {\"filters\": {\"bay_count\": 4, \"structure_type\": \"판상형\", "
    "\"has_special_space\": true}, \"documents\": \"드레스룸 있는 평면\"}\n"
    "\n"
    
    # --- SYNONYM / CLASSIFICATION DATA ---
    "## SYNONYM AND CLASSIFICATION RULES (JSON)\n"
    f"{word_rules_text}\n"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.llm_model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": normalized_query},
                ],
                response_format={"type": "json_object"},
            )
            raw_text = response.choices[0].message.content or ""
            raw_text = re.sub(r"<think>[\s\S]*?</think>\s*", "", raw_text)
            raw_text = re.sub(r"</?think>\s*", "", raw_text).strip()
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
                or normalized_query
            )
            documents = str(documents).strip()
            if not documents:
                documents = normalized_query
            documents = self._augment_documents_from_query(normalized_query, documents)

            filters = self._normalize_filters(raw_filters)
            filters = self._augment_filters_from_query(normalized_query, filters)
            filters = self._drop_implicit_ratio_filters(normalized_query, filters)
            return {"filters": filters, "documents": documents, "raw_query": normalized_query}
        except (json.JSONDecodeError, ValueError, KeyError, TypeError, IndexError):
            self.logger.warning(
                "Analyzer JSON parsing failed. Falling back to keyword-only search."
            )
            return {"filters": {}, "documents": normalized_query, "raw_query": normalized_query}

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

    # 비율 필터 "동일" 연산자의 허용 오차 (±)
    RATIO_EQUAL_TOLERANCE = 3.0

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

            if op == "동일":
                tol = self.RATIO_EQUAL_TOLERANCE
                bounds.append({"op": "이상", "val": round(val - tol, 4)})
                bounds.append({"op": "이하", "val": round(val + tol, 4)})
            else:
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

        if "windowless_count" not in augmented and re.search(
            r"무창\s*공간",
            query,
            flags=re.IGNORECASE,
        ):
            match = (
                re.search(r"무창\s*공간(?:이|은|는|을|의)?\s*(\d+)\s*개", query, re.IGNORECASE)
                or re.search(r"(\d+)\s*개\s*무창\s*공간", query, re.IGNORECASE)
                or re.search(r"무창\s*공간(?:이|은|는|을|의)?\s*(\d+)", query, re.IGNORECASE)
            )
            if match:
                augmented["windowless_count"] = int(match.group(1))

        if "ventilation_quality" not in augmented and "환기" in query:
            if "우수" in query:
                augmented["ventilation_quality"] = "우수"
            elif "보통" in query:
                augmented["ventilation_quality"] = "보통"
            elif "미흡" in query:
                augmented["ventilation_quality"] = "미흡"

        ratio_query_targets: dict[str, re.Pattern[str]] = {
            "balcony_ratio": re.compile(r"(발코니|베란다)", re.IGNORECASE),
            "living_room_ratio": re.compile(r"(거실)", re.IGNORECASE),
            "bathroom_ratio": re.compile(r"(욕실|화장실)", re.IGNORECASE),
            "kitchen_ratio": re.compile(r"(주방|식당)", re.IGNORECASE),
        }
        explicit_bathroom_ratio_re = re.compile(
            r"(욕실|화장실)\s*(?:면적\s*)?(?:비율|퍼센트|ratio|%)",
            re.IGNORECASE,
        )
        for ratio_key, target_pattern in ratio_query_targets.items():
            if not target_pattern.search(query):
                continue
            # "화장실 1개" 같은 수량 조건이 bathroom_ratio로 과추출되지 않도록
            # 욕실/화장실 비율이 명시된 경우에만 bathroom_ratio를 보강한다.
            if ratio_key == "bathroom_ratio" and not explicit_bathroom_ratio_re.search(query):
                continue
            bounds = self._extract_ratio_bounds_from_query_by_target(
                query=query,
                target_pattern=target_pattern,
            )
            if not bounds:
                continue
            inferred: dict[str, Any]
            if len(bounds) == 1:
                inferred = {"op": bounds[0]["op"], "val": bounds[0]["val"]}
            else:
                inferred = {"bounds": bounds}
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

    def _extract_ratio_bounds_from_query_by_target(
        self,
        query: str,
        target_pattern: re.Pattern[str],
        normalize_windowless: bool = False,
    ) -> list[dict[str, Any]]:
        text = self._normalize_windowless_aliases(query) if normalize_windowless else str(query or "")
        if not text:
            return []
        if not target_pattern.search(text):
            return []
        if not self.DOC_RATIO_TOKEN_RE.search(text):
            return []

        clauses = [
            clause.strip()
            for clause in re.split(r"(?:,|;|/|그리고|및|이고|이며|또는)", text)
            if clause.strip()
        ]
        target_clauses = [clause for clause in clauses if target_pattern.search(clause)]
        for clause in target_clauses:
            bounds = self._parse_ratio_conditions_from_text(clause)
            if bounds:
                return bounds
            numeric = self._parse_float(clause)
            if numeric is not None:
                return [{"op": "동일", "val": float(numeric)}]

        for match in target_pattern.finditer(text):
            snippet = text[max(0, match.start() - 28) : min(len(text), match.end() + 28)]
            bounds = self._parse_ratio_conditions_from_text(snippet)
            if bounds:
                return bounds
            numeric = self._parse_float(snippet)
            if numeric is not None:
                return [{"op": "동일", "val": float(numeric)}]

        target_mentions = len(list(target_pattern.finditer(text)))
        if target_mentions == 1:
            bounds = self._parse_ratio_conditions_from_text(text)
            if bounds:
                return bounds
            numeric = self._parse_float(text)
            if numeric is not None:
                return [{"op": "동일", "val": float(numeric)}]
        return []

    def _extract_windowless_ratio_bounds_from_query(self, query: str) -> list[dict[str, Any]]:
        return self._extract_ratio_bounds_from_query_by_target(
            query=query,
            target_pattern=re.compile(r"무창\s*공간", re.IGNORECASE),
            normalize_windowless=True,
        )

    def _extract_storage_ratio_bounds_from_query(self, query: str) -> list[dict[str, Any]]:
        return self._extract_ratio_bounds_from_query_by_target(
            query=query,
            target_pattern=self.STORAGE_RATIO_QUERY_TARGET_RE,
        )

    def _extract_ldk_ratio_bounds_from_query(self, query: str) -> list[dict[str, Any]]:
        text = str(query or "")
        if not text:
            return []
        if not self.LDK_RATIO_QUERY_TARGET_RE.search(text):
            return []

        # LDK는 정성 표현("LDK가 큰/넓은")이 많아, 타 항목(예: 발코니)의 비율값을
        # LDK 비율 제약으로 오인하지 않도록 LDK가 포함된 절에서만 비율을 읽는다.
        clauses = [
            clause.strip()
            for clause in re.split(r"(?:,|;|/|그리고|및|이고|이며|또는)", text)
            if clause.strip()
        ]
        target_clauses = [clause for clause in clauses if self.LDK_RATIO_QUERY_TARGET_RE.search(clause)]
        for clause in target_clauses:
            if not self.DOC_RATIO_TOKEN_RE.search(clause):
                continue
            bounds = self._parse_ratio_conditions_from_text(clause)
            if bounds:
                return bounds
            numeric = self._parse_float(clause)
            if numeric is not None:
                return [{"op": "동일", "val": float(numeric)}]
        return []

    def _extract_document_ratio_constraints_from_query(
        self, query: str
    ) -> list[tuple[str, list[dict[str, Any]]]]:
        # analysis_description 기반 비율 파싱 검색은 정확도 이슈로 비활성화.
        # 비율 조건은 DB 정량 컬럼 필터를 우선 사용하고, 문서 문맥은 임베딩으로 검색한다.
        return []

    def _order_document_ratio_targets_by_query(
        self, query: str, present_targets: list[str]
    ) -> list[str]:
        if not present_targets:
            return []

        text = self._normalize_windowless_aliases(str(query or ""))
        if not text:
            return present_targets

        target_pattern_map: dict[str, re.Pattern[str]] = {
            "windowless": re.compile(r"무창\s*공간", re.IGNORECASE),
            "storage": self.STORAGE_RATIO_QUERY_TARGET_RE,
            "ldk": self.LDK_RATIO_QUERY_TARGET_RE,
        }

        scored: list[tuple[int, int, str]] = []
        for default_idx, target in enumerate(present_targets):
            pattern = target_pattern_map.get(target)
            if pattern is None:
                scored.append((10**9, default_idx, target))
                continue
            match = pattern.search(text)
            start = match.start() if match else 10**9
            scored.append((start, default_idx, target))

        scored.sort(key=lambda item: (item[0], item[1]))
        return [target for _, _, target in scored]

    def _document_ratio_match_vector(
        self,
        document: str,
        constraints: list[tuple[str, list[dict[str, Any]]]],
    ) -> list[int]:
        if not constraints:
            return []
        text = str(document or "")
        vector: list[int] = []
        for target, bounds in constraints:
            if target == "windowless":
                values = self._extract_windowless_ratio_values_from_document(text)
            elif target == "storage":
                values = self._extract_storage_ratio_values_from_document(text)
            elif target == "ldk":
                values = self._extract_ldk_ratio_values_from_document(text)
            else:
                values = []
            vector.append(1 if self._ratio_values_match_bounds(values, bounds) else 0)
        return vector

    def _rank_rows_by_document_ratio_constraints(
        self,
        rows: list[tuple[Any, ...]],
        constraints: list[tuple[str, list[dict[str, Any]]]],
    ) -> list[tuple[Any, ...]]:
        if not constraints or not rows:
            return rows
        ranked_rows: list[tuple[int, tuple[int, ...], float, int, tuple[Any, ...]]] = []
        for idx, row in enumerate(rows):
            doc_text = str(row[2] if row and len(row) > 2 else "")
            match_vector = tuple(self._document_ratio_match_vector(doc_text, constraints))
            match_count = sum(match_vector)
            if match_count <= 0:
                continue
            similarity = float(row[16] if len(row) > 16 and row[16] is not None else 0.0)
            ranked_rows.append((match_count, match_vector, similarity, idx, row))
        ranked_rows.sort(
            key=lambda item: (item[0], *item[1], item[2], -item[3]),
            reverse=True,
        )
        return [row for _, _, _, _, row in ranked_rows]

    def _extract_ratio_values_from_document_by_keyword(
        self, document: str, keyword_re: re.Pattern[str]
    ) -> list[float]:
        text = re.sub(r"\s+", " ", str(document or "")).strip()
        if not text:
            return []

        segments = [seg.strip() for seg in re.split(r"\n+", text) if seg.strip()]
        candidate_segments: list[str] = []
        clause_splitter = re.compile(r"(?:,|;|\||그리고|및|이고|이며|또는)")
        for seg in segments:
            clauses = [clause.strip() for clause in clause_splitter.split(seg) if clause.strip()]
            matched_clauses = [clause for clause in clauses if keyword_re.search(clause)]
            if matched_clauses:
                candidate_segments.extend(matched_clauses)
                continue
            if keyword_re.search(seg):
                candidate_segments.append(seg)

        if not candidate_segments:
            for match in keyword_re.finditer(text):
                snippet = text[max(0, match.start() - 36) : min(len(text), match.end() + 36)].strip()
                if snippet:
                    candidate_segments.append(snippet)
        if not candidate_segments and keyword_re.search(text):
            candidate_segments = [text]

        values_with_order: list[tuple[int, float]] = []
        for seg in candidate_segments:
            non_threshold_candidates: list[tuple[int, float]] = []
            for match in re.finditer(r"(-?\d+(?:\.\d+)?)\s*%", seg):
                try:
                    value = float(match.group(1))
                except (TypeError, ValueError):
                    continue
                pre = seg[max(0, match.start() - 10) : match.start()]
                post = seg[match.end() : match.end() + 12]
                if re.search(r"^\s*(이하|이상|미만|초과)", post):
                    continue
                if re.search(r"(권장|기준)[^0-9%]{0,3}$", pre):
                    continue
                non_threshold_candidates.append((match.start(), value))
            if non_threshold_candidates:
                non_threshold_candidates.sort(key=lambda item: item[0])
                values_with_order.extend(non_threshold_candidates)

        if not values_with_order:
            return []

        values_with_order.sort(key=lambda item: item[0])
        values: list[float] = []
        for _, val in values_with_order:
            if val not in values:
                values.append(val)
        return values

    def _extract_windowless_ratio_values_from_document(self, document: str) -> list[float]:
        return self._extract_ratio_values_from_document_by_keyword(
            document=document,
            keyword_re=self.WINDOWLESS_RATIO_DOC_KEYWORD_RE,
        )

    def _extract_storage_ratio_values_from_document(self, document: str) -> list[float]:
        return self._extract_ratio_values_from_document_by_keyword(
            document=document,
            keyword_re=self.STORAGE_RATIO_DOC_KEYWORD_RE,
        )

    def _extract_ldk_ratio_values_from_document(self, document: str) -> list[float]:
        return self._extract_ratio_values_from_document_by_keyword(
            document=document,
            keyword_re=self.LDK_RATIO_DOC_KEYWORD_RE,
        )

    def _extract_windowless_ratio_from_document(self, document: str) -> Optional[float]:
        values = self._extract_windowless_ratio_values_from_document(document)
        return values[0] if values else None

    def _is_ratio_bound_satisfied(self, actual: float, op: str, target: float) -> bool:
        if op == "이상":
            return actual >= target
        if op == "이하":
            return actual <= target
        if op == "초과":
            return actual > target
        if op == "미만":
            return actual < target
        if op == "동일":
            return abs(actual - target) <= self.RATIO_EQUAL_TOLERANCE
        return True

    def _ratio_values_match_bounds(
        self, values: list[float], bounds: list[dict[str, Any]]
    ) -> bool:
        if not values or not bounds:
            return False
        evaluated = False
        for bound in bounds:
            op = self._normalize_ratio_operator(bound.get("op"))
            val = self._parse_float(bound.get("val"))
            if op is None or val is None:
                continue
            evaluated = True
            target = float(val)
            if op in {"이하", "미만"}:
                actual = max(values)
                if not self._is_ratio_bound_satisfied(actual, op, target):
                    return False
                continue
            if op in {"이상", "초과"}:
                actual = min(values)
                if not self._is_ratio_bound_satisfied(actual, op, target):
                    return False
                continue
            if op == "동일":
                if not any(self._is_ratio_bound_satisfied(actual, op, target) for actual in values):
                    return False
                continue
            if not any(self._is_ratio_bound_satisfied(actual, op, target) for actual in values):
                return False
        return evaluated

    def _document_matches_windowless_ratio(
        self, document: str, bounds: list[dict[str, Any]]
    ) -> bool:
        values = self._extract_windowless_ratio_values_from_document(document)
        return self._ratio_values_match_bounds(values, bounds)

    def _document_matches_document_ratio_constraints(
        self,
        document: str,
        constraints: list[tuple[str, list[dict[str, Any]]]],
    ) -> bool:
        if not constraints:
            return True
        return self._document_ratio_match_count(document, constraints) == len(constraints)

    def _document_ratio_match_count(
        self,
        document: str,
        constraints: list[tuple[str, list[dict[str, Any]]]],
    ) -> int:
        return sum(self._document_ratio_match_vector(document, constraints))

    def _count_matches_by_document_ratio_constraints(
        self,
        filters: dict[str, Any],
        constraints: list[tuple[str, list[dict[str, Any]]]],
        min_match_count: int = 1,
        conn: Any = None,
    ) -> int:
        if not constraints:
            return 0
        threshold = max(1, int(min_match_count))
        where_sql, params = self._build_filter_where_parts(filters)
        db_conn = conn or self.conn
        sql = (
            "SELECT fa.analysis_description "
            "FROM floorplan_analysis fa "
            "JOIN floorplan f ON fa.floorplan_id = f.id "
            f"WHERE {where_sql}"
        )
        with db_conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return sum(
            1
            for row in rows
            if self._document_ratio_match_count(
                str(row[0] if row and len(row) > 0 else ""), constraints
            ) >= threshold
        )

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
        if self._looks_like_analysis_description(text):
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

        if preferences.get("lighting") == "positive":
            lighting_terms = [
                "채광 우수",
                "채광 양호",
                "일조 양호",
                "채광이 좋",
                "밝은",
                "창이 확보",
                "주요 거주공간 창 확보",
            ]
            joined = " OR ".join(f'"{term}"' for term in lighting_terms)
            base = f"({base}) OR ({joined})"
        elif preferences.get("lighting") == "negative":
            lighting_terms = [
                "채광 미흡",
                "채광 부족",
                "일조 불리",
                "채광이 어둡",
                "창 부족",
                "창 미확인",
            ]
            joined = " OR ".join(f'"{term}"' for term in lighting_terms)
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

    def _extract_lighting_signal_from_document(
        self, document: str
    ) -> Optional[tuple[str, str]]:
        text = str(document or "")
        if not text.strip():
            return None

        clauses = [
            re.sub(r"\s+", " ", clause).strip()
            for clause in re.split(r"[.\n]", text)
            if clause and clause.strip()
        ]
        for clause in clauses:
            if not re.search(r"(채광|일조|창|창호)", clause, flags=re.IGNORECASE):
                continue
            positive = bool(self.LIGHTING_SENTENCE_POSITIVE_RE.search(clause))
            negative = bool(self.LIGHTING_SENTENCE_NEGATIVE_RE.search(clause))
            if positive and not negative:
                return "양호", clause
            if negative and not positive:
                return "미흡", clause
            if self.LIGHTING_WINDOW_POSITIVE_RE.search(clause):
                return "양호", clause
            if self.LIGHTING_WINDOW_NEGATIVE_RE.search(clause):
                return "미흡", clause
        return None

    def _extract_document_signals(self, document: str) -> list[dict[str, str]]:
        text = str(document or "")
        if not text.strip():
            return []

        signals: list[dict[str, str]] = []
        for canonical_key, aliases in self.DOCUMENT_SIGNAL_KEY_ALIASES.items():
            match_value: Optional[str] = None
            match_source: Optional[str] = None
            for alias in aliases:
                pattern = (
                    rf"{re.escape(alias)}"
                    r"\s*(?:은\(는\)|은|는|이|가|:|=)\s*([^\n.,]+)"
                )
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    match_value = re.sub(r"\s+", " ", match.group(1)).strip()
                    match_source = re.sub(r"\s+", " ", match.group(0)).strip()
                    break
            if not match_value and canonical_key == "lighting":
                inferred = self._extract_lighting_signal_from_document(text)
                if inferred:
                    match_value, match_source = inferred
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
        compact_ascii = re.sub(r"[._/\-]+", "", compact).lower()
        if re.fullmatch(r"주방(?:및)?식당|주방/식당", compact):
            return "주방/식당"
        if re.fullmatch(r"현관(?:및)?기타(?:공간)?|현관/기타(?:공간)?", compact):
            return "현관/기타"
        if compact == "엘리베이터홀" or compact_ascii in {
            "elev홀",
            "elevhall",
            "elevatorhall",
        }:
            return "엘리베이터홀"
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

    @staticmethod
    def _normalize_document_id_for_match(document_id: str) -> str:
        normalized = str(document_id or "").strip().lower()
        if not normalized:
            return ""
        return re.sub(r"\.(png|jpg|jpeg|bmp|tif|tiff|webp)$", "", normalized, flags=re.IGNORECASE)

    def _normalize_compliance_item_label(self, label: str) -> str:
        normalized = self._normalize_core_eval_label_for_output(label)
        compact = re.sub(r"[\s_\-]+", "", normalized).lower()
        if compact in {"채광", "환기", "가족융화", "수납"}:
            if compact == "가족융화":
                return "가족 융화"
            return normalized
        return ""

    def _split_compliance_items_text(self, text: str) -> list[str]:
        raw = re.sub(r"\s+", " ", str(text or "")).strip()
        if not raw:
            return []
        if raw in {"없음", "해당 없음", "없습니다", "none", "None"}:
            return []

        chunks = [chunk.strip() for chunk in re.split(r"[,;·|]", raw) if chunk.strip()]
        items: list[str] = []
        for chunk in chunks:
            cleaned = re.sub(r"^[\-\[\(]+|[\]\)]+$", "", chunk).strip()
            if not cleaned or cleaned in {"없음", "해당 없음", "없습니다"}:
                continue
            normalized = self._normalize_compliance_item_label(cleaned)
            item = normalized or cleaned
            if item not in items:
                items.append(item)
        return items

    def _extract_explicit_compliance_items(
        self, document: str
    ) -> tuple[list[str], list[str]]:
        text = str(document or "")
        if not text.strip():
            return [], []

        fit_items: list[str] = []
        unfit_items: list[str] = []
        patterns = (
            ("적합", fit_items),
            ("부적합", unfit_items),
        )
        for prefix, bucket in patterns:
            for match in re.finditer(
                rf"(?mi)^\s*(?:[-•]\s*)?{prefix}\s*항목\s*:\s*(?P<items>[^\n]+)$",
                text,
            ):
                for item in self._split_compliance_items_text(match.group("items")):
                    if item not in bucket:
                        bucket.append(item)
        return fit_items, unfit_items

    def _infer_document_compliance_polarity(self, text: str) -> Optional[str]:
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        if not normalized:
            return None

        primary_clause = re.split(r"[.!?]", normalized, maxsplit=1)[0].strip()
        if not primary_clause:
            primary_clause = normalized

        total_positive_hits = len(self.DOCUMENT_COMPLIANCE_POSITIVE_RE.findall(normalized))
        total_negative_hits = len(self.DOCUMENT_COMPLIANCE_NEGATIVE_RE.findall(normalized))
        primary_positive_hits = len(self.DOCUMENT_COMPLIANCE_POSITIVE_RE.findall(primary_clause))
        primary_negative_hits = len(self.DOCUMENT_COMPLIANCE_NEGATIVE_RE.findall(primary_clause))
        uncertain_hits = len(self.DOCUMENT_COMPLIANCE_UNCERTAIN_RE.findall(normalized))

        if total_positive_hits == 0 and total_negative_hits == 0:
            return None
        if total_positive_hits > 0 and total_negative_hits == 0:
            return "positive"
        if total_negative_hits > 0 and total_positive_hits == 0:
            return "negative"

        score = (
            (primary_positive_hits * 2)
            + total_positive_hits
            - (primary_negative_hits * 2)
            - total_negative_hits
            + uncertain_hits
        )
        if score >= 0:
            return "positive"
        return "negative"

    def _extract_design_eval_compliance_items(
        self, document: str
    ) -> tuple[list[str], list[str]]:
        text = str(document or "")
        if not text.strip():
            return [], []

        design_match = re.search(
            r"(?is)\[\s*설계\s*평가\s*\](?P<body>.*?)(?=\[\s*(?:공간\s*분석|공간\s*구성\s*분석|핵심\s*평가|주요\s*공간별\s*상세\s*분석|전체\s*평가)\s*\]|\Z)",
            text,
        )
        design_text = design_match.group("body") if design_match else text
        label_matches = list(self.DOCUMENT_COMPLIANCE_ITEM_LABEL_RE.finditer(design_text))
        if not label_matches:
            return [], []

        fit_items: list[str] = []
        unfit_items: list[str] = []
        for idx, match in enumerate(label_matches):
            raw_label = match.group(1)
            label = self._normalize_compliance_item_label(raw_label)
            if not label:
                continue
            start = match.end()
            end = label_matches[idx + 1].start() if idx + 1 < len(label_matches) else len(design_text)
            snippet = re.sub(r"^[\s,.;:]+|[\s,.;:]+$", "", design_text[start:end])
            polarity = self._infer_document_compliance_polarity(snippet)
            if polarity == "positive":
                if label not in fit_items:
                    fit_items.append(label)
                continue
            if polarity == "negative":
                if label not in unfit_items:
                    unfit_items.append(label)
        return fit_items, unfit_items

    def _extract_compliance_items_from_document(self, document: str) -> dict[str, list[str]]:
        fit_items, unfit_items = self._extract_explicit_compliance_items(document)
        parsed_fit, parsed_unfit = self._extract_design_eval_compliance_items(document)

        for item in parsed_fit:
            if item not in fit_items and item not in unfit_items:
                fit_items.append(item)
        for item in parsed_unfit:
            if item not in unfit_items:
                unfit_items.append(item)
            if item in fit_items:
                fit_items = [existing for existing in fit_items if existing != item]

        if not fit_items and not unfit_items:
            for signal in self._extract_document_signals(document):
                label = self._normalize_compliance_item_label(signal.get("label", ""))
                if not label:
                    continue
                polarity = self._infer_signal_polarity(signal.get("value", ""))
                if polarity == "positive" and label not in fit_items and label not in unfit_items:
                    fit_items.append(label)
                elif polarity == "negative" and label not in unfit_items:
                    unfit_items.append(label)
                    if label in fit_items:
                        fit_items = [existing for existing in fit_items if existing != label]

        return {
            "fit_items": fit_items,
            "unfit_items": unfit_items,
        }

    @staticmethod
    def _format_compliance_items_for_output(items: list[str]) -> str:
        return ", ".join(items) if items else "없음"

    def _replace_or_insert_compliance_item_line(
        self, text: str, label: str, value: str
    ) -> str:
        pattern = re.compile(rf"(?m)^(?P<indent>\s*)(?:[-•]\s*)?{label}\s*항목\s*:\s*.+$")
        replacement = rf"\g<indent>• {label} 항목: {value}"
        if pattern.search(text):
            return pattern.sub(replacement, text, count=1)

        grade_line = re.search(
            r"(?m)^(?P<line>\s*■\s*(?:\*\*)?\s*종합\s*등급\s*(?:\*\*)?\s*:\s*.+)$",
            text,
        )
        if not grade_line:
            return text
        insert_at = grade_line.end()
        inserted = f"\n• {label} 항목: {value}"
        return f"{text[:insert_at]}{inserted}{text[insert_at:]}"

    @staticmethod
    def _format_percent_value(value: float) -> str:
        numeric = float(value)
        if numeric.is_integer():
            return str(int(numeric))
        return f"{numeric:.2f}".rstrip("0").rstrip(".")

    def _build_ratio_mentions_for_candidate(
        self, query: str, candidate: Optional[dict[str, Any]]
    ) -> list[tuple[str, str, str]]:
        if not candidate:
            return []
        constraints = self._extract_document_ratio_constraints_from_query(str(query or ""))
        if not constraints:
            return []

        document = str(candidate.get("document", "") or "")
        if not document.strip():
            return []

        mentions: list[tuple[str, str, str]] = []
        for target, bounds in constraints:
            values: list[float] = []
            label = ""
            keyword = ""
            if target == "windowless":
                values = self._extract_windowless_ratio_values_from_document(document)
                label = "채광"
                keyword = "무창 공간 비율"
            elif target == "storage":
                values = self._extract_storage_ratio_values_from_document(document)
                label = "수납"
                keyword = "수납 공간 비율"
            elif target == "ldk":
                values = self._extract_ldk_ratio_values_from_document(document)
                label = "가족 융화"
                keyword = "LDK 비율"
            if not values or not label or not keyword:
                continue

            actual = values[0]
            status_text = ""
            condition_text = ""
            if len(bounds) == 1:
                op = self._normalize_ratio_operator(bounds[0].get("op"))
                target_val = self._parse_float(bounds[0].get("val"))
                if op is not None and target_val is not None:
                    is_ok = self._is_ratio_bound_satisfied(float(actual), op, float(target_val))
                    status_text = "충족" if is_ok else "미충족"
                    target_percent = self._format_percent_value(float(target_val))
                    condition_text = f"{target_percent}% {op} 기준"

            percent = self._format_percent_value(float(actual))
            if status_text and condition_text:
                sentence = f"{keyword}이 {percent}%로 {condition_text}을 {status_text}합니다."
            else:
                sentence = f"{keyword}이 {percent}%로 확인됩니다."
            mentions.append((label, keyword, sentence))
        return mentions

    def _inject_ratio_mentions_into_layout(
        self,
        layout_text: str,
        query: str,
        candidate: Optional[dict[str, Any]],
    ) -> str:
        text = str(layout_text or "")
        if not text.strip():
            return text

        mentions = self._build_ratio_mentions_for_candidate(query=query, candidate=candidate)
        if not mentions:
            return text

        core_block_re = re.compile(
            r"(?ms)(?P<header>^\s*■\s*(?:\*\*)?\s*핵심\s*설계\s*평가\s*(?:\*\*)?\s*\n)"
            r"(?P<body>.*?)(?=^\s*■\s*(?:\*\*)?\s*주요\s*공간별\s*상세\s*분석\s*(?:\*\*)?\s*$|\Z)"
        )
        match = core_block_re.search(text)
        if not match:
            return text

        header = match.group("header")
        body = match.group("body").rstrip("\n")
        original_full = f"{header}{body}"
        updated_body = body

        for label, keyword, sentence in mentions:
            # 이미 해당 비율 문구가 있으면 추가하지 않는다.
            if keyword in original_full or keyword in updated_body:
                continue
            line_pattern = re.compile(
                rf"(?m)^(?P<prefix>\s*\[{re.escape(label)}\]\s*)(?P<content>.+?)\s*$"
            )
            line_match = line_pattern.search(updated_body)
            if line_match:
                prefix = line_match.group("prefix")
                content = line_match.group("content").strip()
                new_line = f"{prefix}{content} {sentence}"
                updated_body = (
                    updated_body[: line_match.start()]
                    + new_line
                    + updated_body[line_match.end() :]
                )
            else:
                if updated_body.strip():
                    updated_body = f"{updated_body}\n[{label}] {sentence}"
                else:
                    updated_body = f"[{label}] {sentence}"

        replaced = f"{header}{updated_body}\n"
        return f"{text[:match.start()]}{replaced}{text[match.end():]}"

    def _enforce_compliance_items_for_single_answer(
        self,
        answer: str,
        candidate: Optional[dict[str, Any]],
        query: str = "",
    ) -> str:
        text = str(answer or "")
        if not text or not candidate:
            return text
        fit_items = candidate.get("compliance_fit_items", []) or []
        unfit_items = candidate.get("compliance_unfit_items", []) or []
        fit_text = self._format_compliance_items_for_output(fit_items)
        unfit_text = self._format_compliance_items_for_output(unfit_items)
        updated = self._replace_or_insert_compliance_item_line(text, "적합", fit_text)
        updated = self._replace_or_insert_compliance_item_line(updated, "부적합", unfit_text)
        updated = self._inject_ratio_mentions_into_layout(updated, query=query, candidate=candidate)
        return updated

    def _enforce_compliance_items_for_general_answer(
        self,
        answer: str,
        candidates: list[dict[str, Any]],
        query: str = "",
    ) -> str:
        text = str(answer or "")
        if not text.strip() or not candidates:
            return text

        candidate_map: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            key = self._normalize_document_id_for_match(candidate.get("document_id", ""))
            if key and key not in candidate_map:
                candidate_map[key] = candidate

        if not candidate_map:
            return text

        block_pattern = re.compile(
            r"(?ms)^(?P<header>\s*(?:#{1,6}\s*)?\[\s*도면\s*#\d+\s*\]\s*(?P<doc>[^\n]+?)\s*\n)(?P<body>.*?)(?=^\s*(?:#{1,6}\s*)?\[\s*도면\s*#\d+\s*\]\s*[^\n]+\n|\Z)"
        )

        def _replace_block(match: re.Match[str]) -> str:
            doc_id = match.group("doc").strip()
            key = self._normalize_document_id_for_match(doc_id)
            candidate = candidate_map.get(key)
            if not candidate:
                return match.group(0)

            fit_items = candidate.get("compliance_fit_items", []) or []
            unfit_items = candidate.get("compliance_unfit_items", []) or []
            fit_text = self._format_compliance_items_for_output(fit_items)
            unfit_text = self._format_compliance_items_for_output(unfit_items)

            body = match.group("body")
            body = self._replace_or_insert_compliance_item_line(body, "적합", fit_text)
            body = self._replace_or_insert_compliance_item_line(body, "부적합", unfit_text)
            body = self._inject_ratio_mentions_into_layout(
                body,
                query=query,
                candidate=candidate,
            )
            return f"{match.group('header')}{body}"

        return block_pattern.sub(_replace_block, text)

    @staticmethod
    def _remove_match_condition_parts(
        match_value_text: str, target_part_patterns: list[re.Pattern[str]]
    ) -> str:
        parts = [segment.strip() for segment in str(match_value_text or "").split(",")]
        kept_parts: list[str] = []
        for part in parts:
            if not part:
                continue
            if any(pattern.search(part) for pattern in target_part_patterns):
                continue
            kept_parts.append(part)
        if not kept_parts:
            return "일치 항목 정보가 부족합니다"
        return ", ".join(kept_parts)

    def _extract_uncertain_signal_keys_from_layout(self, layout_text: str) -> set[str]:
        text = str(layout_text or "")
        if not text.strip():
            return set()

        uncertain_keys: set[str] = set()
        bracket_line_re = re.compile(
            r"^\s*(?:[-•]\s*)?\[(?P<label>[^\]\n]+)\]\s*(?::\s*|\s+)?(?P<body>.+?)\s*$"
        )
        for line in text.splitlines():
            normalized_line = re.sub(r"\s+", " ", str(line or "")).strip()
            if not normalized_line:
                continue
            if not self.SIGNAL_UNCERTAIN_TEXT_RE.search(normalized_line):
                continue

            bracket_match = bracket_line_re.match(normalized_line)
            if bracket_match:
                label = self._normalize_compliance_item_label(bracket_match.group("label"))
                key = self.SIGNAL_CANONICAL_LABEL_TO_KEY.get(label)
                if key:
                    uncertain_keys.add(key)
                    continue

            for key, pattern in self.SIGNAL_UNCERTAIN_LINE_HINTS.items():
                if pattern.search(normalized_line):
                    uncertain_keys.add(key)
        return uncertain_keys

    def _prune_uncertain_signal_match_conditions(self, answer: str) -> str:
        text = str(answer or "")
        if not text.strip():
            return text

        block_pattern = re.compile(
            r"(?ms)^(?P<header>\s*(?:#{1,6}\s*)?\[\s*도면\s*#\d+\s*\]\s*[^\n]+\n)(?P<body>.*?)(?=^\s*(?:#{1,6}\s*)?\[\s*도면\s*#\d+\s*\]\s*[^\n]+\n|\Z)"
        )
        match_line_pattern = re.compile(
            r"(?m)^(?P<prefix>\s*(?:[-•]\s*)?일치\s*조건\s*:\s*)(?P<value>.+)$"
        )

        def _replace_block(match: re.Match[str]) -> str:
            body = match.group("body")
            layout_text = self._extract_layout_section_text(body) or body
            uncertain_keys = self._extract_uncertain_signal_keys_from_layout(layout_text)
            if not uncertain_keys:
                return match.group(0)

            target_patterns = [
                self.MATCH_CONDITION_SIGNAL_PART_PATTERNS[key]
                for key in uncertain_keys
                if key in self.MATCH_CONDITION_SIGNAL_PART_PATTERNS
            ]
            if not target_patterns:
                return match.group(0)

            def _replace_line(line_match: re.Match[str]) -> str:
                prefix = line_match.group("prefix")
                value = line_match.group("value")
                pruned = self._remove_match_condition_parts(
                    value,
                    target_patterns,
                )
                return f"{prefix}{pruned}"

            updated_body, replaced_count = match_line_pattern.subn(
                _replace_line,
                body,
                count=1,
            )
            if replaced_count == 0:
                return match.group(0)
            return f"{match.group('header')}{updated_body}"

        return block_pattern.sub(_replace_block, text)

    def _extract_query_signal_preferences(self, query: str) -> dict[str, str]:
        text = str(query or "")
        if not text.strip():
            return {}

        lighting_requested = bool(
            re.search(
                r"(채광|lighting|daylight(?:ing)?|sunlight|햇빛|햇살|일조)",
                text,
                flags=re.IGNORECASE,
            )
        )
        storage_requested = bool(
            re.search(
                r"(수납(?:\s*공간)?|storage|드레스룸|팬트리)",
                text,
                flags=re.IGNORECASE,
            )
        )
        family_harmony_requested = bool(
            re.search(
                r"(가족\s*융화|가족융화|family_harmony|family_community)",
                text,
                flags=re.IGNORECASE,
            )
        )
        positive_hint = bool(
            re.search(
                r"(좋|우수|적정|적합|양호|충분|넉넉|밝|풍부|잘\s*[드들](?:는|어)?|잘\s*되(?:는|어)?)",
                text,
                flags=re.IGNORECASE,
            )
        )
        negative_hint = bool(
            re.search(
                r"(나쁘|부족|미흡|부적합|불합격|어둡|없|잘\s*안\s*[드들](?:는|어)?|잘\s*안\s*되(?:는|어)?)",
                text,
                flags=re.IGNORECASE,
            )
        )
        if (
            not positive_hint
            and not negative_hint
            and not lighting_requested
            and not storage_requested
            and not family_harmony_requested
        ):
            return {}

        global_preferred = "positive" if positive_hint and not negative_hint else None
        if negative_hint and not positive_hint:
            global_preferred = "negative"

        lighting_preferred = global_preferred
        if lighting_requested and lighting_preferred is None:
            lighting_positive_context = bool(
                re.search(
                    r"(햇빛|햇살|일조|채광).{0,8}(잘\s*[드들]|좋|밝|풍부|충분)|"
                    r"(잘\s*[드들]|좋|밝|풍부|충분).{0,8}(햇빛|햇살|일조|채광)",
                    text,
                    flags=re.IGNORECASE,
                )
            )
            lighting_negative_context = bool(
                re.search(
                    r"(햇빛|햇살|일조|채광).{0,8}(부족|미흡|어둡|나쁘|잘\s*안\s*[드들])|"
                    r"(부족|미흡|어둡|나쁘|잘\s*안\s*[드들]).{0,8}(햇빛|햇살|일조|채광)",
                    text,
                    flags=re.IGNORECASE,
                )
            )
            if lighting_positive_context and not lighting_negative_context:
                lighting_preferred = "positive"
            elif lighting_negative_context and not lighting_positive_context:
                lighting_preferred = "negative"

        storage_preferred = global_preferred
        if storage_requested and storage_preferred is None:
            storage_positive_context = bool(
                re.search(
                    r"(수납(?:\s*공간)?|storage|드레스룸|팬트리).{0,10}(좋|우수|넉넉|충분|풍부|많|여유|잘\s*되|편리)|"
                    r"(좋|우수|넉넉|충분|풍부|많|여유|잘\s*되|편리).{0,10}(수납(?:\s*공간)?|storage|드레스룸|팬트리)",
                    text,
                    flags=re.IGNORECASE,
                )
            )
            storage_negative_context = bool(
                re.search(
                    r"(수납(?:\s*공간)?|storage|드레스룸|팬트리).{0,10}(부족|미흡|불편|좁|없|모자라|잘\s*안\s*되)|"
                    r"(부족|미흡|불편|좁|없|모자라|잘\s*안\s*되).{0,10}(수납(?:\s*공간)?|storage|드레스룸|팬트리)",
                    text,
                    flags=re.IGNORECASE,
                )
            )
            if storage_positive_context and not storage_negative_context:
                storage_preferred = "positive"
            elif storage_negative_context and not storage_positive_context:
                storage_preferred = "negative"

        family_harmony_preferred = global_preferred
        if family_harmony_requested and family_harmony_preferred is None:
            family_positive_context = bool(
                re.search(
                    r"(가족\s*융화|가족융화|family_harmony|family_community).{0,10}(좋|우수|원활|적합|화목|소통|유대|잘\s*되)|"
                    r"(좋|우수|원활|적합|화목|소통|유대|잘\s*되).{0,10}(가족\s*융화|가족융화|family_harmony|family_community)",
                    text,
                    flags=re.IGNORECASE,
                )
            )
            family_negative_context = bool(
                re.search(
                    r"(가족\s*융화|가족융화|family_harmony|family_community).{0,10}(부족|미흡|어려|불리|단절|갈등|불편|잘\s*안\s*되)|"
                    r"(부족|미흡|어려|불리|단절|갈등|불편|잘\s*안\s*되).{0,10}(가족\s*융화|가족융화|family_harmony|family_community)",
                    text,
                    flags=re.IGNORECASE,
                )
            )
            if family_positive_context and not family_negative_context:
                family_harmony_preferred = "positive"
            elif family_negative_context and not family_positive_context:
                family_harmony_preferred = "negative"

        if (
            global_preferred is None
            and lighting_preferred is None
            and storage_preferred is None
            and family_harmony_preferred is None
        ):
            return {}

        preferences: dict[str, str] = {}
        if lighting_requested and lighting_preferred is not None:
            preferences["lighting"] = lighting_preferred
        if storage_requested and storage_preferred is not None:
            preferences["storage"] = storage_preferred
        if global_preferred is not None and re.search(r"(환기|ventilation)", text, flags=re.IGNORECASE):
            preferences["ventilation"] = global_preferred
        if family_harmony_requested and family_harmony_preferred is not None:
            preferences["family_harmony"] = family_harmony_preferred
        if global_preferred is not None and re.search(r"(발코니|베란다)", text, flags=re.IGNORECASE):
            preferences["balcony_usage"] = global_preferred
        return preferences

    def _contains_compliance_label(self, items: list[str], target_label: str) -> bool:
        target = self._normalize_compliance_item_label(target_label)
        if not target:
            return False
        for item in items or []:
            normalized = self._normalize_compliance_item_label(str(item))
            if normalized == target:
                return True
        return False

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

    def _extract_ldk_layout_signal(self, query: str) -> Optional[str]:
        text = str(query or "")
        if not text.strip():
            return None
        if not self.LDK_RATIO_QUERY_TARGET_RE.search(text):
            return None

        wide_hint = bool(
            re.search(
                r"(넓|넓은|넉넉|여유|광활|확장)",
                text,
                flags=re.IGNORECASE,
            )
        )
        narrow_hint = bool(
            re.search(
                r"(좁|협소|답답)",
                text,
                flags=re.IGNORECASE,
            )
        )
        if wide_hint and not narrow_hint:
            return "wide"
        if narrow_hint and not wide_hint:
            return "narrow"
        return None

    def _ldk_ratio_sum_from_row(self, row: tuple[Any, ...]) -> Optional[float]:
        living_ratio = self._parse_float(row[5] if len(row) > 5 else None)
        kitchen_ratio = self._parse_float(row[7] if len(row) > 7 else None)
        if living_ratio is None and kitchen_ratio is None:
            return None
        return float((living_ratio or 0.0) + (kitchen_ratio or 0.0))

    def _rerank_by_query_signal_preferences(
        self,
        docs: list[tuple[Any, ...]],
        query: str,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[tuple[Any, ...]]:
        preferences = self._extract_query_signal_preferences(query)
        ratio_proximity = self._extract_ratio_proximity_target(query, filters or {})
        ldk_layout_signal = self._extract_ldk_layout_signal(query)
        if (not preferences and ratio_proximity is None and ldk_layout_signal is None) or not docs:
            return docs

        storage_priority = preferences.get("storage") == "positive"
        lighting_priority = preferences.get("lighting") == "positive"
        family_harmony_priority = preferences.get("family_harmony") == "positive"
        ratio_col_index = {
            "balcony_ratio": 4,
            "living_room_ratio": 5,
            "bathroom_ratio": 6,
            "kitchen_ratio": 7,
        }
        rescored_docs: list[tuple[float, int, float, Optional[float], tuple[Any, ...]]] = []
        excluded_by_lighting_unfit = 0
        excluded_by_storage_unfit = 0
        excluded_by_family_harmony_unfit = 0
        for row in docs:
            base_score = float(row[16] if len(row) > 16 and row[16] is not None else 0.0)
            document_text = str(row[2] if len(row) > 2 else "")
            signals = self._extract_document_signals(document_text)
            signal_map = {signal["key"]: signal["value"] for signal in signals}
            compliance_items = self._extract_compliance_items_from_document(document_text)
            fit_items = compliance_items.get("fit_items", [])
            unfit_items = compliance_items.get("unfit_items", [])

            # 채광 긍정 질의: '부적합 항목'에 채광이 있으면 해당 도면은 답변 후보에서 제외.
            if lighting_priority and self._contains_compliance_label(unfit_items, "채광"):
                excluded_by_lighting_unfit += 1
                continue
            # 수납 긍정 질의: '부적합 항목'에 수납이 있으면 해당 도면은 답변 후보에서 제외.
            if storage_priority and self._contains_compliance_label(unfit_items, "수납"):
                excluded_by_storage_unfit += 1
                continue
            # 가족 융화 긍정 질의: '부적합 항목'에 가족 융화가 있으면 해당 도면은 답변 후보에서 제외.
            if family_harmony_priority and self._contains_compliance_label(unfit_items, "가족 융화"):
                excluded_by_family_harmony_unfit += 1
                continue

            bonus = 0.0
            storage_rank = 0
            if lighting_priority and self._contains_compliance_label(fit_items, "채광"):
                bonus += 0.16
            if storage_priority and self._contains_compliance_label(fit_items, "수납"):
                bonus += 0.16
            if family_harmony_priority and self._contains_compliance_label(fit_items, "가족 융화"):
                bonus += 0.16
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

            ldk_ratio_sum = self._ldk_ratio_sum_from_row(row)
            rescored_docs.append(
                (adjusted_score, storage_rank, proximity_distance, ldk_ratio_sum, adjusted_row)
            )

        if lighting_priority and excluded_by_lighting_unfit > 0:
            self._log_event(
                event="rerank_lighting_unfit_excluded",
                level=logging.INFO,
                excluded_count=excluded_by_lighting_unfit,
                remaining_count=len(rescored_docs),
            )
        if storage_priority and excluded_by_storage_unfit > 0:
            self._log_event(
                event="rerank_storage_unfit_excluded",
                level=logging.INFO,
                excluded_count=excluded_by_storage_unfit,
                remaining_count=len(rescored_docs),
            )
        if family_harmony_priority and excluded_by_family_harmony_unfit > 0:
            self._log_event(
                event="rerank_family_harmony_unfit_excluded",
                level=logging.INFO,
                excluded_count=excluded_by_family_harmony_unfit,
                remaining_count=len(rescored_docs),
            )

        if storage_priority and ratio_proximity is not None:
            if ldk_layout_signal == "wide":
                rescored_docs.sort(
                    key=lambda item: (
                        -item[1],
                        item[2],
                        1 if item[3] is None else 0,
                        -(item[3] or 0.0),
                        -item[0],
                    )
                )
            elif ldk_layout_signal == "narrow":
                rescored_docs.sort(
                    key=lambda item: (
                        -item[1],
                        item[2],
                        1 if item[3] is None else 0,
                        (item[3] or 0.0),
                        -item[0],
                    )
                )
            else:
                rescored_docs.sort(key=lambda item: (-item[1], item[2], -item[0]))
        elif storage_priority:
            # 수납 선호 질의: 수납 우수(2) > 보통(1) > 미확인(0) > 미흡(-1)
            if ldk_layout_signal == "wide":
                rescored_docs.sort(
                    key=lambda item: (
                        -item[1],
                        1 if item[3] is None else 0,
                        -(item[3] or 0.0),
                        -item[0],
                    )
                )
            elif ldk_layout_signal == "narrow":
                rescored_docs.sort(
                    key=lambda item: (
                        -item[1],
                        1 if item[3] is None else 0,
                        (item[3] or 0.0),
                        -item[0],
                    )
                )
            else:
                rescored_docs.sort(key=lambda item: (item[1], item[0]), reverse=True)
        elif ratio_proximity is not None:
            # 비율 조건 질의: 기준값에 더 가까운 도면을 우선 노출
            if ldk_layout_signal == "wide":
                rescored_docs.sort(
                    key=lambda item: (
                        item[2],
                        1 if item[3] is None else 0,
                        -(item[3] or 0.0),
                        -item[0],
                    )
                )
            elif ldk_layout_signal == "narrow":
                rescored_docs.sort(
                    key=lambda item: (
                        item[2],
                        1 if item[3] is None else 0,
                        (item[3] or 0.0),
                        -item[0],
                    )
                )
            else:
                rescored_docs.sort(key=lambda item: (item[2], -item[0]))
        elif ldk_layout_signal == "wide":
            rescored_docs.sort(
                key=lambda item: (
                    1 if item[3] is None else 0,
                    -(item[3] or 0.0),
                    -item[0],
                )
            )
        elif ldk_layout_signal == "narrow":
            rescored_docs.sort(
                key=lambda item: (
                    1 if item[3] is None else 0,
                    (item[3] or 0.0),
                    -item[0],
                )
            )
        else:
            rescored_docs.sort(key=lambda item: item[0], reverse=True)
        return [row for _, _, _, _, row in rescored_docs]

    def _retrieve_by_document_id(self, document_id: str, conn: Any = None) -> Optional[tuple]:
        sql = """
            SELECT f.id AS floorplan_id, f.name AS document_id,
            fa.analysis_description AS document,
            fa.windowless_count, fa.balcony_ratio, fa.living_room_ratio, fa.bathroom_ratio, fa.kitchen_ratio,
            fa.structure_type, fa.bay_count, fa.room_count, fa.bathroom_count,
            fa.compliance_grade, fa.ventilation_quality AS ventilation_quality,
            fa.has_special_space, fa.has_etc_space,
            1.0::double precision AS similarity
            FROM floorplan_analysis fa
            JOIN floorplan f ON fa.floorplan_id = f.id
            WHERE LOWER(f.name) = LOWER(%s)
               OR LOWER(regexp_replace(f.name, '\\.(png|jpg|jpeg|bmp|tif|tiff|webp)$', '', 'i')) = LOWER(%s)
            LIMIT 1
        """
        normalized = document_id.strip()
        db_conn = conn or self.conn
        with db_conn.cursor() as cur:
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
            ventilation_quality,
            has_special_space,
            has_etc_space,
            similarity,
        ) = row
        space_labels_hint = self._extract_space_labels_from_document(document)
        compliance_items = self._extract_compliance_items_from_document(document)
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
                "ventilation_quality": ventilation_quality,
                "has_special_space": has_special_space,
                "has_etc_space": has_etc_space,
                "compliance_grade": compliance_grade,
            },
            "document": document,
            "document_signals": self._extract_document_signals(document),
            "compliance_fit_items": compliance_items.get("fit_items", []),
            "compliance_unfit_items": compliance_items.get("unfit_items", []),
            "space_labels_hint": space_labels_hint,
            "similarity": similarity,
        }

    def _generate_document_id_answer(self, document_id: str, doc: tuple[Any, ...]) -> str:
        candidate = self._row_to_candidate(doc, rank=1)
        candidate_json = json.dumps(candidate, ensure_ascii=False, indent=2)

        system_prompt = """You are a specialized assistant for architectural floor plan retrieval.

## OUTPUT REQUIREMENTS (Read First)
- Respond ONLY in Korean.
- Follow the fixed output format exactly for every floor plan — do not skip, reorder, or rename any section.
- Section 1 and Section 2 must preserve the exact format structure.
- Section 3 must rewrite the original internal evaluation into natural, user-friendly Korean.
- Never invent facts not present in the original text or JSON.
- Never add design suggestions, improvement recommendations, or your own judgments.
- Always use formal Korean (합니다/습니다 체). Never use 반말 (예: ~다, ~이다).

---

## DO NOT (Negative Rules — Apply to All Sections)
- Do NOT output internal field names (e.g., `bay_count`, `room_count`, `has_special_space`).
- Do NOT add conditions to "찾는 조건" that the user did not explicitly state.
- Do NOT use meta-expressions: "기재되어 있습니다", "언급되어 있습니다", "서술되어 있습니다", "요청", "선호", "조건으로 처리".
- Do NOT use technical memo-style bracket notation: `4Bay(통계 bay_count=4)`, `환기창(창호)`, `연결(door/window)`.
- Do NOT split or hyphenate compound Korean terms: `드레스룸` must always be written as one word — never `드레`, `스룸`, or `드레+스룸`.
- Do NOT use status labels in parentheses after item names: `(좋음)`, `(미흡)` etc. are forbidden.
- Do NOT use alternate label formats: `주방및식당`, `현관및기타공간` — always use `주방/식당`, `현관/기타`.
- Do NOT repeat the same facts across sentences or sections.
- Do NOT make definitive claims that go beyond the source data.

---

## ERROR HANDLING
- If a metadata value is missing or null, output `정보 없음` for that field.
- If a judgment cannot be confirmed, write `기능을 확정할 수 없습니다`.
- If evidence is insufficient for an evaluation item, write `정보가 부족합니다`.
- `적합 항목` and `부적합 항목` must always be filled — write `없음` if none apply.
- `documents` field in Section 3 must always be used if present; do not silently discard it.

---

## FEW-SHOT EXAMPLES

### Example B — Section 2 (공간 구성 여부 값)
has_special_space=true, has_etc_space=false

✅ Correct output:
• 특화 공간: 존재
• 기타 공간: 없음

❌ Wrong output:
• 특화 공간: true  ← boolean 그대로 출력 금지
• 기타 공간: has_etc_space=false  ← 필드명 출력 금지

---

### Example C — Section 3 (핵심 설계 평가 문장 스타일)
Source: "거실 채광 우수. 주방 환기 미흡. 드레스룸 연결 구조."

✅ Correct output:
[채광] 거실의 채광 환경이 우수합니다.
[환기] 주방의 환기 성능이 미흡합니다.
[안방] 드레스룸이 연결된 구조입니다.

❌ Wrong output:
채광은(는) 우수합니다.  ← 어색한 조사 금지
[안방] 드레+스룸이 연결(door/window)되어 있습니다.  ← 분리 표기 및 기술 메모 금지
채광이 우수하므로 남향 배치를 권장합니다.  ← 설계 제안 추가 금지

---

## OUTPUT FORMAT (Fixed — Repeat for Each Floor Plan)

### 1. 검색된 도면 id: {document_id}

### 2. 도면 기본 정보 📊
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
■ 종합 등급: {compliance_grade}
• 적합 항목: {compliance_fit_items를 그대로 사용, 없으면 없음}
• 부적합 항목: {compliance_unfit_items를 그대로 사용, 없으면 없음}
■ 핵심 설계 평가
[평가 항목명] ...
[평가 항목명] ...
■ 주요 공간별 상세 분석
[공간명] ...
[공간명] ...

---

## DETAILED RULES BY SECTION

### Section 3 Rules
- Use only facts from the original text and JSON (document, document_signals).
- If document_signals is present, prioritize those labels and states.
- `적합 항목`과 `부적합 항목`은 query 일치 여부가 아니라 document에서 추출된 `compliance_fit_items`, `compliance_unfit_items`를 그대로 사용한다.
- Include benchmark comparisons (e.g., 권장 30~40%, 30% 이하) ONLY if stated in the source.
- Merge sentences with identical meaning; do not repeat the same fact.
- Each item may be written in 2–3 sentences.
- Section headers must appear in this exact order: ■ 종합 등급 → ■ 핵심 설계 평가 → ■ 주요 공간별 상세 분석
- Space labels: use space_labels_hint if provided; otherwise derive from source text.
- Space labels format: [주방/식당], [현관/기타] — never [주방및식당], [현관및기타공간]
- Spaces of the same character may be grouped (e.g., 기타 7~10).
- 수납 공간은 반드시 `드레스룸`으로 표기한다.
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
                model=self.llm_model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
            )
            raw = response.choices[0].message.content or ""
            raw = re.sub(r"<think>[\s\S]*?</think>\s*", "", raw)
            raw = re.sub(r"</?think>\s*", "", raw)
            return raw.strip()

        answer = self._run_validated_generation(
            mode="document_id",
            generate_fn=_call_llm,
            expected_document_id=document_id.strip(),
        )
        return self._enforce_compliance_items_for_single_answer(answer, candidate)

    def _build_filter_where_parts(self, filters: dict[str, Any]) -> tuple[str, list[Any]]:
        where_clauses = []
        params: list[Any] = []

        for column in self.ALLOWED_FILTER_COLUMNS:
            value = filters.get(column)
            if value is None:
                continue
            db_col = f"fa.{column}"
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

    def _retrieve_hybrid(
        self,
        query_json: dict,
        top_k: int = 50,
        offset: int = 0,
        conn: Any = None,
    ) -> list:
        """
        Generate embedding -> build query -> execute DB query -> return results
        """
        filters = query_json.get("filters", {}) or {}
        documents = query_json.get("documents", "") or ""
        raw_query = query_json.get("raw_query", "") or ""
        db_conn = conn or self.conn
        semantic_query = f"{documents} {raw_query}".strip() or raw_query or documents
        text_query = str(documents).strip() or str(raw_query).strip()
        requested_top_k = max(1, int(top_k))
        effective_top_k = requested_top_k
        # analysis_description 검색은 텍스트 파싱 점수 대신 임베딩 유사도를 우선한다.
        use_text_scoring = False
        vector_weight = 1.0
        text_weight = 0.0
        if text_query:
            self._log_event(
                event="retrieve_embedding_only_mode",
                level=logging.INFO,
                reason="prefer_embedding_over_analysis_description_text_scoring",
                text_query=text_query[:120],
                filter_count=len(filters),
            )

        embedding = self._embed_text(semantic_query)
        embedding_vector = "[" + ",".join(map(str, embedding)) + "]"

        where_sql, filter_params = self._build_filter_where_parts(filters)

        def _exec_hybrid(
            w_sql,
            w_params,
            use_text=True,
            current_vector_weight: Optional[float] = None,
            current_text_weight: Optional[float] = None,
        ):
            """하이브리드 검색 SQL 실행 헬퍼"""
            v_weight = (
                self.vector_weight
                if current_vector_weight is None
                else float(current_vector_weight)
            )
            t_weight = (
                self.text_weight
                if current_text_weight is None
                else float(current_text_weight)
            )
            if use_text:
                p = [embedding_vector, text_query, *w_params,
                     v_weight, t_weight, effective_top_k, max(0, int(offset))]
                ts_expr = "ts_rank_cd(to_tsvector('simple', COALESCE(fa.analysis_description, '')), websearch_to_tsquery('simple', %s))"
            else:
                p = [embedding_vector, *w_params,
                     v_weight, t_weight, effective_top_k, max(0, int(offset))]
                ts_expr = "0.0::double precision"
            q = f"""
                WITH scored AS (
                    SELECT f.id AS floorplan_id, f.name AS document_id,
                    fa.analysis_description AS document,
                    fa.windowless_count, fa.balcony_ratio, fa.living_room_ratio, fa.bathroom_ratio, fa.kitchen_ratio,
                    fa.structure_type, fa.bay_count, fa.room_count, fa.bathroom_count,
                    fa.compliance_grade, fa.ventilation_quality AS ventilation_quality,
                    fa.has_special_space, fa.has_etc_space,
                    (1 - (fa.embedding <=> %s::vector)) AS vector_similarity,
                    {ts_expr} AS text_score
                    FROM floorplan_analysis fa
                    JOIN floorplan f ON fa.floorplan_id = f.id
                    WHERE {w_sql}
                )
                SELECT floorplan_id, document_id, document,
                windowless_count, balcony_ratio, living_room_ratio, bathroom_ratio, kitchen_ratio,
                structure_type, bay_count, room_count, bathroom_count,
                compliance_grade, ventilation_quality, has_special_space, has_etc_space,
                (%s * vector_similarity + %s * text_score) AS similarity
                FROM scored
                ORDER BY similarity DESC
                LIMIT %s
                OFFSET %s
            """
            with db_conn.cursor() as cur:
                cur.execute(q, p)
                return cur.fetchall()

        try:
            results = _exec_hybrid(
                where_sql,
                filter_params,
                use_text=use_text_scoring,
                current_vector_weight=vector_weight,
                current_text_weight=text_weight,
            )

            # 폴백: 결과 0 → 점진적 필터 완화 (평가성 → 비율/부울 → 구조 순 제거)
            if not results and filters:
                for relaxed in self._relax_filters(filters):
                    if len(relaxed) >= len(filters):
                        continue
                    self._log_event(
                        event="retrieve_filter_relaxation",
                        level=logging.INFO,
                        reason="progressive_filter_relaxation",
                        dropped=[k for k in filters if k not in relaxed],
                        remaining=list(relaxed.keys()),
                    )
                    fb_where, fb_params = self._build_filter_where_parts(relaxed)
                    results = _exec_hybrid(
                        fb_where,
                        fb_params,
                        use_text=use_text_scoring,
                        current_vector_weight=vector_weight,
                        current_text_weight=text_weight,
                    )
                    if results:
                        break

            return results[:requested_top_k]
        except Exception as exc:
            db_conn.rollback()
            if text_query:
                self._log_event(
                    event="retrieve_text_query_fallback",
                    level=logging.WARNING,
                    reason="text_query_parse_or_rank_error",
                    text_query=text_query,
                    filter_count=len(filter_params),
                    error=str(exc),
                )
                try:
                    fallback_results = _exec_hybrid(where_sql, filter_params, use_text=False)
                except Exception:
                    db_conn.rollback()
                    # 필터 전체 제거 후 최종 시도
                    fallback_results = _exec_hybrid("TRUE", [], use_text=False)
                return fallback_results[:requested_top_k]
            raise

    def retrieve_by_embedding(
        self,
        embedding: list[float],
        filters: dict[str, Any] | None = None,
        top_k: int = 3,
    ) -> list:
        """
        Pre-computed embedding 기반 유사 도면 검색.
        CV 분석에서 생성된 embedding 벡터를 직접 사용하여 DB에서 유사 도면을 찾는다.

        Args:
            embedding: 1024-dim embedding vector (qwen3-embedding-0.6b)
            filters: 메트릭 기반 필터 (structure_type, room_count 등). None이면 필터 없이 검색.
            top_k: 반환할 최대 도면 수
        Returns:
            list of tuples (_retrieve_hybrid와 동일 형식)
        """
        embedding_vector = "[" + ",".join(map(str, embedding)) + "]"

        where_sql, filter_params = self._build_filter_where_parts(filters or {})
        params = [embedding_vector, *filter_params, top_k]

        sql = f"""
            SELECT f.id AS floorplan_id, f.name AS document_id,
                fa.analysis_description AS document,
                fa.windowless_count, fa.balcony_ratio, fa.living_room_ratio,
                fa.bathroom_ratio, fa.kitchen_ratio,
                fa.structure_type, fa.bay_count, fa.room_count, fa.bathroom_count,
                fa.compliance_grade, fa.ventilation_quality AS ventilation_quality,
                fa.has_special_space, fa.has_etc_space,
                (1 - (fa.embedding <=> %s::vector)) AS similarity
            FROM floorplan_analysis fa
            JOIN floorplan f ON fa.floorplan_id = f.id
            WHERE {where_sql}
            ORDER BY similarity DESC
            LIMIT %s
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                results = cur.fetchall()
        except Exception:
            self.conn.rollback()
            results = []

        if len(results) < top_k and filters:
            fallback_params = [embedding_vector, top_k]
            fallback_sql = """
                SELECT f.id AS floorplan_id, f.name AS document_id,
                    fa.analysis_description AS document,
                    fa.windowless_count, fa.balcony_ratio, fa.living_room_ratio,
                    fa.bathroom_ratio, fa.kitchen_ratio,
                    fa.structure_type, fa.bay_count, fa.room_count, fa.bathroom_count,
                    fa.compliance_grade, fa.ventilation_quality AS ventilation_quality,
                    fa.has_special_space, fa.has_etc_space,
                    (1 - (fa.embedding <=> %s::vector)) AS similarity
                FROM floorplan_analysis fa
                JOIN floorplan f ON fa.floorplan_id = f.id
                ORDER BY similarity DESC
                LIMIT %s
            """
            try:
                with self.conn.cursor() as cur:
                    cur.execute(fallback_sql, fallback_params)
                    fallback_results = cur.fetchall()
                # 기존 결과 ID를 제외하고 부족분 채우기
                existing_ids = {row[0] for row in results}
                for row in fallback_results:
                    if row[0] not in existing_ids:
                        results.append(row)
                        existing_ids.add(row[0])
                    if len(results) >= top_k:
                        break
            except Exception:
                self.conn.rollback()

        return results[:top_k]

    def search_by_description(
        self, description: str, top_k: int = 3,
        explicit_filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        텍스트 설명(document)으로 유사 도면 검색.
        이미지 분석 후 생성된 document를 검색 쿼리로 사용한다.
        run()과 달리 세션/히스토리 부작용 없이 검색+리랭킹만 수행.

        Args:
            description: 자연어 도면 설명 (to_natural_language() 결과)
            top_k: 최종 반환할 도면 수
            explicit_filters: 명시적 필터 (LLM 추출 필터를 덮어씀, 이미지 검색용)
        Returns:
            {"docs": [...], "query_json": {...}, "total_count": int}
        """
        query_json = self._analyze_query(description)
        filters = query_json.get("filters", {}) or {}
        documents = query_json.get("documents", "") or ""

        # 명시적 필터가 있으면 LLM 추출 필터에 병합 (명시적 필터 우선)
        if explicit_filters:
            self.logger.info("[search_by_description] LLM 추출 필터: %s", filters)
            self.logger.info("[search_by_description] 명시적 필터: %s", explicit_filters)
            filters.update(explicit_filters)
            query_json["filters"] = filters

        self.logger.info("[search_by_description] 최종 필터: %s", filters)
        self.logger.info("[search_by_description] documents: %s", documents[:100] if documents else "(없음)")

        count_context = self._count_matches_context(filters, documents)
        total_count = int(count_context.get("display_count", 0) or 0)
        retrieve_count = int(count_context.get("retrieve_count", 0) or 0)
        self.logger.info(
            "[search_by_description] 매칭 도면: display=%d retrieve=%d",
            total_count,
            retrieve_count,
        )

        if retrieve_count <= 0:
            return {"docs": [], "query_json": query_json, "total_count": 0}

        retrieve_k = min(max(retrieve_count, top_k), 50)
        docs = self._retrieve_hybrid(query_json, top_k=retrieve_k)

        docs = self._rerank_by_query_signal_preferences(
            docs, description, filters,
        )

        return {
            "docs": docs[:top_k],
            "query_json": query_json,
            "total_count": total_count,
        }

    def count_by_filters(self, filters: dict[str, Any] | None = None) -> int:
        """필터 조건에 맞는 도면 총 개수 반환 (public wrapper)"""
        return self._count_matches(filters or {})

    def generate_similar_answer(
        self,
        analysis_metrics: dict[str, Any],
        docs: list,
        total_count: int,
    ) -> str:
        """
        유사 도면 검색 결과를 텍스트 검색과 동일한 구조로 생성.
        기존 _generate_answer를 재사용하고 마커를 [유사 도면 #N]으로 변환.

        Args:
            analysis_metrics: CV 분석 메트릭 (room_count, bay_count 등)
            docs: retrieve_by_embedding 결과 (tuple list)
            total_count: 필터 조건에 맞는 전체 도면 수
        Returns:
            [유사 도면 #N] 마커가 포함된 구조화된 답변 문자열
        """
        if not docs:
            return ""

        parts = []
        m = analysis_metrics or {}
        if m.get("structure_type"):
            parts.append(f"{m['structure_type']} 구조")
        if m.get("bay_count"):
            parts.append(f"Bay {m['bay_count']}개")
        if m.get("room_count"):
            parts.append(f"방 {m['room_count']}개")
        if m.get("bathroom_count"):
            parts.append(f"화장실 {m['bathroom_count']}개")
        if m.get("windowless_count") is not None:
            parts.append(f"무창 공간 {m['windowless_count']}개")
        if m.get("living_room_ratio") is not None:
            parts.append(f"거실 비율 {m['living_room_ratio']}%")
        query = ", ".join(parts) + " 구성의 도면과 유사한 도면" if parts else "업로드된 도면과 유사한 도면"

        # query_json 구성 (구조 필터 + 비율 필터)
        filters: dict[str, Any] = {}
        for key in ("structure_type", "room_count", "bay_count", "bathroom_count", "windowless_count"):
            if key in m and m[key] is not None:
                filters[key] = m[key]
        if m.get("living_room_ratio") is not None:
            filters["living_room_ratio"] = {"op": "동일", "val": m["living_room_ratio"]}
        query_json = {"filters": filters, "documents": "", "raw_query": query}

        # 기존 _generate_answer 재사용
        answer = self._generate_answer(query, query_json, docs, total_count)

        # [도면 #N] → [유사 도면 #N] 마커 변환
        answer = re.sub(
            r"(#{1,6}\s*)?\[도면 #(\d+)\]",
            lambda mat: f"{mat.group(1) or ''}[유사 도면 #{mat.group(2)}]",
            answer,
        )
        # "조건을 만족하는 도면 총 개수: N" → "유사 도면 N개"
        answer = re.sub(
            r"조건을 만족하는 도면 총 개수:\s*(\d+)",
            r"유사 도면 \1개",
            answer,
        )
        return answer

    # 점진적 필터 완화 우선순위 (먼저 제거할 필터 → 나중에 제거할 필터)
    # 평가성 필터 → 비율 필터 → 부울 필터 → 구조 필터 순으로 제거
    _FILTER_DROP_PRIORITY = [
        # 1단계: 평가성 필터 (가장 제한적, 먼저 제거)
        {"compliance_grade", "ventilation_quality"},
        # 2단계: 비율 필터 + 부울 필터
        {"balcony_ratio", "living_room_ratio", "bathroom_ratio", "kitchen_ratio",
         "has_special_space", "has_etc_space"},
        # 3단계: 구조 필터 (마지막까지 유지, 최후에 제거)
        {"structure_type", "bay_count", "room_count", "bathroom_count", "windowless_count"},
    ]

    def _relax_filters(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """
        필터를 점진적으로 완화한 후보 목록 반환.
        우선순위가 낮은 필터부터 제거하여 여러 단계의 완화된 필터셋을 생성.
        """
        candidates = []
        current = dict(filters)
        for drop_set in self._FILTER_DROP_PRIORITY:
            keys_to_drop = [k for k in current if k in drop_set]
            if keys_to_drop:
                current = {k: v for k, v in current.items() if k not in drop_set}
                candidates.append(current.copy())
        return candidates

    def _count_matches_by_semantic_similarity(
        self,
        query_text: str,
        filters: dict[str, Any],
        threshold: Optional[float] = None,
        conn: Any = None,
    ) -> int:
        normalized_query = str(query_text or "").strip()
        if not normalized_query:
            return 0

        where_sql, params = self._build_filter_where_parts(filters)
        db_conn = conn or self.conn
        embedding = self._embed_text(normalized_query)
        embedding_vector = "[" + ",".join(map(str, embedding)) + "]"
        similarity_threshold = (
            float(threshold)
            if threshold is not None
            else float(self.SEMANTIC_COUNT_SIMILARITY_THRESHOLD)
        )
        sql = (
            "SELECT COUNT(*) "
            "FROM floorplan_analysis fa "
            "JOIN floorplan f ON fa.floorplan_id = f.id "
            f"WHERE {where_sql} "
            "AND (1 - (fa.embedding <=> %s::vector)) >= %s"
        )
        with db_conn.cursor() as cur:
            cur.execute(sql, [*params, embedding_vector, similarity_threshold])
            return int(cur.fetchone()[0])

    def _count_matches_context(
        self, filters: dict[str, Any], documents: str = "", conn: Any = None
    ) -> dict[str, int]:
        normalized_documents = str(documents or "").strip()
        db_conn = conn or self.conn
        where_sql, params = self._build_filter_where_parts(filters)

        # 설명형 질의(필터 없음): 임베딩 유사도 기반 카운트
        if normalized_documents and not filters:
            try:
                semantic_count = self._count_matches_by_semantic_similarity(
                    query_text=normalized_documents,
                    filters=filters,
                    conn=db_conn,
                )
                self._log_event(
                    event="count_matches_semantic_only",
                    level=logging.INFO,
                    text_query=normalized_documents,
                    similarity_threshold=self.SEMANTIC_COUNT_SIMILARITY_THRESHOLD,
                    semantic_count=semantic_count,
                )
                if semantic_count > 0:
                    return {
                        "display_count": int(semantic_count),
                        "retrieve_count": int(semantic_count),
                        "strict_count": int(semantic_count),
                        "partial_count": int(semantic_count),
                    }
                relaxed_threshold = max(
                    0.15,
                    float(self.SEMANTIC_COUNT_SIMILARITY_THRESHOLD) - 0.20,
                )
                relaxed_count = self._count_matches_by_semantic_similarity(
                    query_text=normalized_documents,
                    filters=filters,
                    threshold=relaxed_threshold,
                    conn=db_conn,
                )
                self._log_event(
                    event="count_matches_semantic_relaxed",
                    level=logging.INFO,
                    text_query=normalized_documents,
                    similarity_threshold=relaxed_threshold,
                    semantic_count=relaxed_count,
                )
                if relaxed_count > 0:
                    return {
                        "display_count": int(relaxed_count),
                        "retrieve_count": int(relaxed_count),
                        "strict_count": int(relaxed_count),
                        "partial_count": int(relaxed_count),
                    }
                self._log_event(
                    event="count_matches_semantic_zero",
                    level=logging.INFO,
                    reason="semantic_zero_result",
                    text_query=normalized_documents,
                )
                return {
                    "display_count": 0,
                    "retrieve_count": 0,
                    "strict_count": 0,
                    "partial_count": 0,
                }
            except Exception as exc:
                db_conn.rollback()
                self._log_event(
                    event="count_matches_semantic_only_fallback",
                    level=logging.WARNING,
                    reason="semantic_count_error",
                    text_query=normalized_documents,
                    error=str(exc),
                )
                fallback_where_sql, fallback_params = self._build_filter_where_parts(filters)
                with db_conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) FROM floorplan_analysis fa JOIN floorplan f ON fa.floorplan_id = f.id WHERE "
                        + fallback_where_sql,
                        fallback_params,
                    )
                    fallback_count = int(cur.fetchone()[0])
                return {
                    "display_count": int(fallback_count),
                    "retrieve_count": int(fallback_count),
                    "strict_count": int(fallback_count),
                    "partial_count": int(fallback_count),
                }
        elif normalized_documents and filters:
            self._log_event(
                event="count_matches_embedding_preferred",
                level=logging.INFO,
                reason="skip_analysis_description_text_filtering",
                text_query=normalized_documents[:120],
                filter_count=len(filters),
            )

        base_sql = "SELECT COUNT(*) FROM floorplan_analysis fa JOIN floorplan f ON fa.floorplan_id = f.id WHERE {}"

        def _exec_count(w_sql, w_params):
            with db_conn.cursor() as cur:
                cur.execute(base_sql.format(w_sql), w_params)
                return int(cur.fetchone()[0])

        try:
            matched_count = _exec_count(where_sql, params)

            # 폴백 1: 텍스트 검색 제거 (필터만)
            if matched_count == 0 and normalized_documents:
                self._log_event(
                    event="count_matches_zero_text_fallback",
                    level=logging.INFO,
                    reason="strict_text_zero_match",
                    text_query=normalized_documents,
                    filter_count=len(filters),
                )
                fb_where, fb_params = self._build_filter_where_parts(filters)
                matched_count = _exec_count(fb_where, fb_params)

            # 폴백 2~N: 점진적 필터 완화 (평가성 → 비율/부울 → 구조 순 제거)
            if matched_count == 0 and filters:
                for relaxed in self._relax_filters(filters):
                    if len(relaxed) >= len(filters):
                        continue
                    self._log_event(
                        event="count_matches_filter_relaxation",
                        level=logging.INFO,
                        reason="progressive_filter_relaxation",
                        dropped=[k for k in filters if k not in relaxed],
                        remaining=list(relaxed.keys()),
                    )
                    fb_where, fb_params = self._build_filter_where_parts(relaxed)
                    matched_count = _exec_count(fb_where, fb_params)
                    if matched_count > 0:
                        break

            return {
                "display_count": int(matched_count),
                "retrieve_count": int(matched_count),
                "strict_count": int(matched_count),
                "partial_count": int(matched_count),
            }
        except Exception as exc:
            db_conn.rollback()
            if normalized_documents:
                self._log_event(
                    event="count_matches_text_query_fallback",
                    level=logging.WARNING,
                    reason="text_query_parse_error",
                    text_query=normalized_documents,
                    error=str(exc),
                )
                fallback_where_sql, fallback_params = self._build_filter_where_parts(filters)
                fallback_count = _exec_count(fallback_where_sql, fallback_params)
                return {
                    "display_count": int(fallback_count),
                    "retrieve_count": int(fallback_count),
                    "strict_count": int(fallback_count),
                    "partial_count": int(fallback_count),
                }
            raise

    def _count_matches(self, filters: dict[str, Any], documents: str = "") -> int:
        context = self._count_matches_context(filters=filters, documents=documents)
        return int(context.get("retrieve_count", 0) or 0)

    @staticmethod
    def _compose_general_answer_text(total_match_count: int, blocks: list[str]) -> str:
        header = f"조건을 만족하는 도면 총 개수: {int(total_match_count)}"
        cleaned_blocks = [str(block or "").strip() for block in blocks if str(block or "").strip()]
        if not cleaned_blocks:
            return header
        return f"{header}\n\n" + "\n\n".join(cleaned_blocks)

    def _normalize_single_general_block(
        self,
        raw_text: str,
        rank: int,
        document_id: str,
    ) -> str:
        normalized = self._normalize_generated_answer(raw_text)
        block_match = re.search(
            r"(?ms)^\s*(?:#{1,6}\s*)?\[도면\s*#\d+\]\s*[^\n]+\n(?P<body>.*?)(?=^\s*(?:#{1,6}\s*)?\[도면\s*#\d+\]\s*[^\n]+\n|\Z)",
            normalized,
        )
        if not block_match:
            raise ValueError("Chunk response does not contain a floorplan block header.")

        block = block_match.group(0).strip()
        header_match = re.search(
            r"(?m)^\s*(?:#{1,6}\s*)?\[도면\s*#\d+\]\s*[^\n]+\s*$",
            block,
        )
        if not header_match:
            raise ValueError("Chunk response does not contain a valid floorplan block header.")

        body = block[header_match.end() :].strip()
        if not body:
            raise ValueError("Chunk response body is empty.")

        safe_rank = max(1, int(rank))
        safe_document_id = str(document_id or "").strip() or "정보 없음"
        header = f"### [도면 #{safe_rank}] {safe_document_id}"
        return f"{header}\n\n{body}"

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

        system_prompt = """
You are a specialized assistant for architectural floor plan retrieval.

## OUTPUT REQUIREMENTS (Read First)
- Respond ONLY in Korean.
- Follow the fixed output format exactly for every floor plan — do not skip, reorder, or rename any section.
- Section 1 and Section 2 must preserve the exact format structure.
- Section 3 must rewrite the original internal evaluation into natural, user-friendly Korean.
- Never invent facts not present in the original text or JSON.
- Never add design suggestions, improvement recommendations, or your own judgments.
- Always use formal Korean (합니다/습니다 체). Never use 반말 (예: ~다, ~이다).
- 조건을 만족하는 도면 총 개수: {total_count}는 처음 한 번만 언급한다. 

---

## DO NOT (Negative Rules — Apply to All Sections)
- Do NOT output internal field names (e.g., `bay_count`, `room_count`, `has_special_space`).
- Do NOT add conditions to "찾는 조건" that the user did not explicitly state.
- Do NOT use meta-expressions: "기재되어 있습니다", "언급되어 있습니다", "서술되어 있습니다", "요청", "선호", "조건으로 처리".
- Do NOT use technical memo-style bracket notation: `4Bay(통계 bay_count=4)`, `환기창(창호)`, `연결(door/window)`.
- Do NOT split or hyphenate compound Korean terms: `드레스룸` must always be written as one word — never `드레`, `스룸`, or `드레+스룸`.
- Do NOT use status labels in parentheses after item names: `(좋음)`, `(미흡)` etc. are forbidden.
- Do NOT use alternate label formats: `주방및식당`, `현관및기타공간` — always use `주방/식당`, `현관/기타`.
- Do NOT repeat the same facts across sentences or sections.
- Do NOT make definitive claims that go beyond the source data.

---

## ERROR HANDLING
- If a metadata value is missing or null, output `정보 없음` for that field.
- If a judgment cannot be confirmed, write `기능을 확정할 수 없습니다`.
- If evidence is insufficient for an evaluation item, write `정보가 부족합니다`.
- `적합 항목` and `부적합 항목` must always be filled — write `없음` if none apply.
- `documents` field in Section 3 must always be used if present; do not silently discard it.

---

## FEW-SHOT EXAMPLES

### Example A — Section 1 (도면 선택 근거)
User query: "방 3개, 발코니 비율 15% 이상, 판상형 구조"
Floor plan metadata: room_count=3, balcony_ratio=18.2, structure_type=판상형

✅ Correct output:
• 찾는 조건: 방 3개, 발코니 비율 15% 이상, 판상형 구조
• 일치 조건: 방 수=3개, 발코니 비율=18.2%, 건물 구조 유형=판상형

❌ Wrong output:
• 찾는 조건: 방 3개, 발코니 비율 15% 이상, 판상형 구조, 남향 배치  ← 사용자가 말하지 않은 조건 추가 금지
• 일치 조건: bay_count=4  ← 내부 필드명 출력 금지

---

### Example B — Section 2 (공간 구성 여부 값)
has_special_space=true, has_etc_space=false

✅ Correct output:
• 특화 공간: 존재
• 기타 공간: 없음

❌ Wrong output:
• 특화 공간: true  ← boolean 그대로 출력 금지
• 기타 공간: has_etc_space=false  ← 필드명 출력 금지

---

### Example C — Section 3 (핵심 설계 평가 문장 스타일)
Source: "거실 채광 우수. 주방 환기 미흡. 드레스룸 연결 구조."

✅ Correct output:
[채광] 거실의 채광 환경이 우수합니다.
[환기] 주방의 환기 성능이 미흡합니다.
[안방] 드레스룸이 연결된 구조입니다.

❌ Wrong output:
채광은(는) 우수합니다.  ← 어색한 조사 금지
[안방] 드레+스룸이 연결(door/window)되어 있습니다.  ← 분리 표기 및 기술 메모 금지
채광이 우수하므로 남향 배치를 권장합니다.  ← 설계 제안 추가 금지

---

## OUTPUT FORMAT (Fixed — Repeat for Each Floor Plan)

조건을 만족하는 도면 총 개수: {total_count}

### [도면 #{rank}] {document_id}

### 1. 도면 선택 근거 🔍
• 찾는 조건: {사용자 조건을 한국어 표현으로 나열}
• 일치 조건: {도면 메타데이터 및 document에서 확인된 일치 항목을 한국어 항목명=값 형태로 나열}

### 2. 도면 기본 정보 📊
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
■ 종합 등급: {compliance_grade}
• 적합 항목: {compliance_fit_items를 그대로 사용, 없으면 없음}
• 부적합 항목: {compliance_unfit_items를 그대로 사용, 없으면 없음}
■ 핵심 설계 평가
[평가 항목명] ...
[평가 항목명] ...
■ 주요 공간별 상세 분석
[공간명] ...
[공간명] ...

---

## DETAILED RULES BY SECTION

### Section 1 Rules
- "찾는 조건": List only what the user explicitly stated, refined in natural Korean.
- "일치 조건": Include each user condition verifiable from metadata OR semantically confirmed in the document description.
  • Document-based examples: "발코니 활용 가능" ↔ "외부 공간으로 활용", "활용도가 높음"
  • "주방 환기창 존재" ↔ "주방/식당에 환기창이 있음"

### Section 3 Rules
- Use only facts from the original text and JSON (document, document_signals).
- If document_signals is present, prioritize those labels and states.
- `적합 항목`과 `부적합 항목`은 query 일치 여부가 아니라 document에서 추출된 `compliance_fit_items`, `compliance_unfit_items`를 그대로 사용한다.
- Include benchmark comparisons (e.g., 권장 30~40%, 30% 이하) ONLY if stated in the source.
- Merge sentences with identical meaning; do not repeat the same fact.
- Each item may be written in 2–3 sentences.
- Section headers must appear in this exact order: ■ 종합 등급 → ■ 핵심 설계 평가 → ■ 주요 공간별 상세 분석
- Space labels: use space_labels_hint if provided; otherwise derive from source text.
- Space labels format: [주방/식당], [현관/기타] — never [주방및식당], [현관및기타공간]
- Spaces of the same character may be grouped (e.g., 기타 7~10).
- 수납 공간은 반드시 `드레스룸`으로 표기한다.
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
                model=self.llm_model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
            )
            raw = response.choices[0].message.content or ""
            raw = re.sub(r"<think>[\s\S]*?</think>\s*", "", raw)
            raw = re.sub(r"</?think>\s*", "", raw)
            return raw.strip()

        chunk_mode_enabled = (
            self.enable_chunk_parallel_generation
            and len(candidates) >= self.chunk_parallel_min_docs
        )

        def _call_llm_chunked() -> str:
            worker_count = min(self.chunk_parallel_workers, len(candidates))
            chunk_prompt = (
                f"{system_prompt.strip()}\n\n"
                "## CHUNK MODE (IMPORTANT)\n"
                "- 정확히 하나의 도면 블록만 작성하세요.\n"
                "- `조건을 만족하는 도면 총 개수:` 라인은 출력하지 마세요.\n"
                "- 도면 헤더는 반드시 `[도면 #N] 도면ID` 형식을 사용하세요.\n"
            )
            self._log_event(
                event="generate_chunk_parallel_start",
                level=logging.INFO,
                candidate_count=len(candidates),
                worker_count=worker_count,
            )
            chunk_start = time.perf_counter()

            def _generate_single_chunk(candidate: dict[str, Any]) -> str:
                candidate_rank = int(candidate.get("rank") or 1)
                candidate_document_id = str(candidate.get("document_id") or "").strip()
                candidate_json = json.dumps(candidate, ensure_ascii=False, indent=2)
                chunk_user_content = (
                    f"검색된 도면 id(조회 결과 목록):\n{id_list_text}\n\n"
                    f"조건 일치 전체 건수(total_count):\n{total_match_count}\n\n"
                    f"사용자가 설정한 검색 조건:\n{filters_json}\n\n"
                    f"작성 대상 도면 데이터(단일):\n{candidate_json}\n\n"
                    f"사용자 질의 원문:\n{query}\n\n"
                    "단일 도면 블록만 작성하고, 총 개수 라인은 절대 출력하지 마세요."
                )
                response = self.client.chat.completions.create(
                    model=self.llm_model_name,
                    messages=[
                        {"role": "system", "content": chunk_prompt},
                        {"role": "user", "content": chunk_user_content},
                    ],
                    temperature=0.2,
                )
                raw_chunk = response.choices[0].message.content or ""
                raw_chunk = re.sub(r"<think>[\s\S]*?</think>\s*", "", raw_chunk)
                raw_chunk = re.sub(r"</?think>\s*", "", raw_chunk).strip()
                return self._normalize_single_general_block(
                    raw_chunk,
                    rank=candidate_rank,
                    document_id=candidate_document_id,
                )

            ordered_futures: list[tuple[int, Any]] = []
            with ThreadPoolExecutor(max_workers=worker_count) as chunk_executor:
                for candidate in candidates:
                    rank = int(candidate.get("rank") or 1)
                    future = chunk_executor.submit(_generate_single_chunk, candidate)
                    ordered_futures.append((rank, future))

                ordered_blocks = [future.result() for _, future in ordered_futures]

            answer_text = self._compose_general_answer_text(
                total_match_count=total_match_count,
                blocks=ordered_blocks,
            )
            self._log_event(
                event="generate_chunk_parallel_done",
                level=logging.INFO,
                candidate_count=len(candidates),
                latency_ms=int((time.perf_counter() - chunk_start) * 1000),
            )
            return answer_text

        answer: str
        if chunk_mode_enabled:
            try:
                chunk_answer = _call_llm_chunked()
                if self.answer_validation_enabled:
                    chunk_validation_start = time.perf_counter()
                    chunk_validation_result = self._validate_answer_format(
                        answer=chunk_answer,
                        mode="general",
                    )
                    chunk_validation_ms = int(
                        (time.perf_counter() - chunk_validation_start) * 1000
                    )
                    if chunk_validation_result.ok:
                        self._log_event(
                            event="generate_chunk_parallel_validation_pass",
                            level=logging.INFO,
                            latency_ms=chunk_validation_ms,
                        )
                        answer = chunk_answer
                    else:
                        self._log_event(
                            event="generate_chunk_parallel_validation_fail",
                            level=logging.WARNING,
                            latency_ms=chunk_validation_ms,
                            missing_fields=",".join(chunk_validation_result.missing_fields)
                            or "none",
                        )
                        answer = self._run_validated_generation(
                            mode="general",
                            generate_fn=_call_llm,
                        )
                else:
                    answer = chunk_answer
            except Exception as exc:
                self._log_event(
                    event="generate_chunk_parallel_fallback",
                    level=logging.WARNING,
                    reason="chunk_generation_error",
                    error=str(exc),
                )
                answer = self._run_validated_generation(mode="general", generate_fn=_call_llm)
        else:
            answer = self._run_validated_generation(mode="general", generate_fn=_call_llm)
        answer = self._enforce_compliance_items_for_general_answer(
            answer,
            candidates,
            query=query,
        )
        return self._prune_uncertain_signal_match_conditions(answer)

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
            count_context = self._count_matches_context(
                query_json.get("filters", {}) or {},
                query_json.get("documents", "") or "",
            )
            total_match_count = int(count_context.get("display_count", 0) or 0)
            retrieve_match_count = int(count_context.get("retrieve_count", 0) or 0)
        except Exception:
            total_match_count = total_shown
            retrieve_match_count = total_shown

        context = {
            "type": "more_context",
            "query_text": base_query,
            "query_json": query_json,
            "total_match_count": int(total_match_count),
            "current_offset": int(total_shown),
            "returned_floorplan_ids": [],
            "returned_floorplan_names": returned_doc_names,
            "updated_at": time.time(),
        }
        self._log_event(
            event="chat_history_more_context_loaded",
            chat_room_id=chat_room_id,
            base_query=base_query[:120],
            total_match_count=int(total_match_count),
            retrieve_match_count=int(retrieve_match_count),
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

            filters = query_json.get("filters", {}) or {}
            documents = query_json.get("documents", "") or ""
            count_context: dict[str, int] = {}
            prefetched_docs: Optional[list] = None
            count_latency_ms: Optional[int] = None
            retrieve_latency_ms: Optional[int] = None
            retrieve_source = "sequential"

            if self.enable_parallel and self._executor is not None:
                parallel_start = time.perf_counter()
                self._log_event(
                    event="parallel_stage_start",
                    query_id=query_id,
                    retrieve_k_hint=50,
                    filter_count=len(filters),
                    documents_len=len(str(documents or "")),
                )
                count_future = self._executor.submit(self._run_count_task, query_json)
                retrieve_future: Optional[Any] = None
                try:
                    count_context = count_future.result()
                    count_latency_ms = int((time.perf_counter() - parallel_start) * 1000)
                    self._log_event(
                        event="parallel_count_done",
                        query_id=query_id,
                        latency_ms=count_latency_ms,
                        total_match_count=int(count_context.get("display_count", 0) or 0),
                        retrieve_match_count=int(
                            count_context.get("retrieve_count", 0) or 0
                        ),
                    )
                    parallel_retrieve_match_count = int(
                        count_context.get("retrieve_count", 0) or 0
                    )
                    if parallel_retrieve_match_count > 0:
                        retrieve_future = self._executor.submit(
                            self._run_retrieve_task,
                            query_json,
                            50,
                        )
                        prefetched_docs = retrieve_future.result()
                        retrieve_latency_ms = int(
                            (time.perf_counter() - parallel_start) * 1000
                        )
                        self._log_event(
                            event="parallel_retrieve_done",
                            query_id=query_id,
                            latency_ms=retrieve_latency_ms,
                            prefetched_count=len(prefetched_docs),
                        )
                    else:
                        self._log_event(
                            event="parallel_retrieve_skipped_no_match",
                            query_id=query_id,
                            retrieve_match_count=parallel_retrieve_match_count,
                        )
                    self._log_event(
                        event="parallel_stage_done",
                        query_id=query_id,
                        latency_ms=int((time.perf_counter() - parallel_start) * 1000),
                    )
                except Exception as exc:
                    count_future.cancel()
                    if retrieve_future is not None:
                        retrieve_future.cancel()
                    prefetched_docs = None
                    retrieve_latency_ms = None
                    if not count_context:
                        count_latency_ms = None
                    self._log_event(
                        event="parallel_fallback_triggered",
                        level=logging.WARNING,
                        query_id=query_id,
                        reason="parallel_task_failure",
                        error=str(exc),
                    )

            if not count_context:
                count_start = time.perf_counter()
                count_context = self._count_matches_context(filters, documents)
                count_latency_ms = int((time.perf_counter() - count_start) * 1000)

            total_match_count = int(count_context.get("display_count", 0) or 0)
            retrieve_match_count = int(count_context.get("retrieve_count", 0) or 0)
            self._log_event(
                event="count_complete",
                query_id=query_id,
                latency_ms=int(count_latency_ms or 0),
                total_match_count=total_match_count,
                retrieve_match_count=retrieve_match_count,
            )
            if retrieve_match_count <= 0:
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
            retrieve_k = min(max(retrieve_match_count, 3), 50)

            if prefetched_docs is not None:
                docs = prefetched_docs[:retrieve_k]
                retrieve_source = "parallel_prefetch"
                if not docs and retrieve_match_count > 0:
                    self._log_event(
                        event="parallel_fallback_triggered",
                        level=logging.WARNING,
                        query_id=query_id,
                        reason="prefetch_empty_with_positive_count",
                        retrieve_match_count=retrieve_match_count,
                    )
                    retrieve_start = time.perf_counter()
                    docs = self._retrieve_hybrid(query_json, top_k=retrieve_k)
                    retrieve_latency_ms = int((time.perf_counter() - retrieve_start) * 1000)
                    retrieve_source = "sequential_after_prefetch_empty"
            else:
                retrieve_start = time.perf_counter()
                docs = self._retrieve_hybrid(query_json, top_k=retrieve_k)
                retrieve_latency_ms = int((time.perf_counter() - retrieve_start) * 1000)
                retrieve_source = "sequential"

            self._log_event(
                event="retrieve_complete",
                query_id=query_id,
                latency_ms=int(retrieve_latency_ms or 0),
                retrieve_k=retrieve_k,
                retrieved_count=len(docs),
                retrieve_source=retrieve_source,
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
