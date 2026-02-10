import json
import logging
import re
from pathlib import Path
from typing import Any, Optional
import psycopg2
from openai import OpenAI


class ArchitecturalHybridRAG:
    ALLOWED_FILTER_COLUMNS = [
        "windowless_ratio",
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

    INT_FILTERS = {"bay_count", "room_count", "bathroom_count"}
    FLOAT_FILTERS = {
        "windowless_ratio",
        "balcony_ratio",
        "living_room_ratio",
        "bathroom_ratio",
        "kitchen_ratio",
    }
    BOOL_FILTERS = {"has_special_space", "has_etc_space"}
    VALID_RATIO_OPERATORS = {"이상", "이하", "초과", "미만", "동일"}

    def __init__(
        self,
        db_config,
        openai_api_key,
        embedding_model: str = "text-embedding-3-small",
        embedding_dimensions: int = 1024,
        vector_weight: float = 0.8,
        text_weight: float = 0.2,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
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
        self.word_dict: dict[str, Any] = {}
        word_path = Path(__file__).resolve().parent / "data" / "word.json"
        try:
            with word_path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.word_dict = loaded if isinstance(loaded, dict) else {}
        except Exception as exc:  # noqa: BLE001
            self.word_dict = {}
            self.logger.warning("Failed to load word dictionary (%s): %s", word_path, exc)

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
            '    "windowless_ratio": {"op": "이상|이하|초과|미만|동일", "val": "number"} (optional),\n'
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
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                temperature=0.0,
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

        # Also support split pair keys like kitchen_ratio_op + kitchen_ratio_val.
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

        # Backward compatibility: numeric-only input means exact match.
        if isinstance(value, (int, float)):
            return {"op": "동일", "val": float(value)}

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            # Accept forms like "이상 20", "20 이하", or plain number.
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
            # If op is present but invalid, keep it as None so SQL treats it as no filter.
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
                # group index differs by regex branch, so choose first numeric group.
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
        # Ratio filters should be applied only when the user explicitly gives numeric intent.
        if re.search(r"(%|퍼센트|비율|ratio|이상|이하|초과|미만|동일)", query, flags=re.IGNORECASE):
            return filters

        sanitized = dict(filters)
        for key in self.FLOAT_FILTERS:
            sanitized.pop(key, None)
        return sanitized

    def _retrieve_hybrid(self, query_json: dict, top_k: int = 50) -> list:
        """
        Generate embedding -> build query -> execute DB query -> return results
        """
        filters = query_json.get("filters", {}) or {}
        documents = query_json.get("documents", "") or ""
        raw_query = query_json.get("raw_query", "") or ""
        semantic_query = f"{documents} {raw_query}".strip() or raw_query or documents

        embedding_resp = self.client.embeddings.create(
            model=self.embedding_model,
            input=semantic_query,
            dimensions=self.embedding_dimensions,
        )
        embedding = embedding_resp.data[0].embedding
        embedding_vector = "[" + ",".join(map(str, embedding)) + "]"

        where_clauses = []
        params: list[Any] = [embedding_vector, semantic_query]

        for column in self.ALLOWED_FILTER_COLUMNS:
            value = filters.get(column)
            if value is None:
                continue
            if column in self.FLOAT_FILTERS:
                op = value.get("op") if isinstance(value, dict) else None
                val = value.get("val") if isinstance(value, dict) else None
                where_clauses.append(f"ratio_cmp({column}::double precision, %s, %s)")
                params.extend([op, val])
            else:
                where_clauses.append(f"{column} = %s")
                params.append(value)

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        params.append(self.vector_weight)
        params.append(self.text_weight)
        params.append(top_k)

        sql = f"""
            WITH scored AS (
                SELECT document_id, document, windowless_ratio, balcony_ratio, living_room_ratio, bathroom_ratio, kitchen_ratio,
                structure_type, bay_count, room_count, bathroom_count,
                compliance_grade, ventilation_grade, has_special_space, has_etc_space,
                (1 - (embedding <=> %s::vector)) AS vector_similarity,
                ts_rank_cd(
                    to_tsvector('simple', COALESCE(document, '')),
                    websearch_to_tsquery('simple', %s)
                ) AS text_score
                FROM FP_Analysis
                WHERE {where_sql}
            )
            SELECT document_id, document, windowless_ratio, balcony_ratio, living_room_ratio, bathroom_ratio, kitchen_ratio,
            structure_type, bay_count, room_count, bathroom_count,
            compliance_grade, ventilation_grade, has_special_space, has_etc_space,
            (%s * vector_similarity + %s * text_score) AS similarity
            FROM scored
            ORDER BY similarity DESC
            LIMIT %s
        """

        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def _count_matches(self, filters: dict[str, Any]) -> int:
        where_clauses = []
        params: list[Any] = []

        for column in self.ALLOWED_FILTER_COLUMNS:
            value = filters.get(column)
            if value is None:
                continue
            if column in self.FLOAT_FILTERS:
                op = value.get("op") if isinstance(value, dict) else None
                val = value.get("val") if isinstance(value, dict) else None
                where_clauses.append(f"ratio_cmp({column}::double precision, %s, %s)")
                params.extend([op, val])
            else:
                where_clauses.append(f"{column} = %s")
                params.append(value)

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        sql = f"SELECT COUNT(*) FROM FP_Analysis WHERE {where_sql}"
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return int(cur.fetchone()[0])

    def _generate_answer(
        self, query: str, query_json: dict, docs: list, total_match_count: int
    ) -> str:
        """
        Format retrieved docs as documents and send to the LLM to generate the answer
        """
        if not docs:
            return "Try searching again."

        filters_json = json.dumps(query_json.get("filters", {}), ensure_ascii=False, indent=2)
        (
            document_id,
            document,
            windowless_ratio,
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
            _similarity,
        ) = docs[0]
        retrieved_ids = [row[0] for row in docs]
        id_list_text = ", ".join(retrieved_ids)

        metadata = {
            "room_count": room_count,
            "bathroom_count": bathroom_count,
            "bay_count": bay_count,
            "living_room_ratio": living_room_ratio,
            "kitchen_ratio": kitchen_ratio,
            "bathroom_ratio": bathroom_ratio,
            "balcony_ratio": balcony_ratio,
            "windowless_ratio": windowless_ratio,
            "structure_type": structure_type,
            "ventilation_quality": ventilation_grade,
            "has_special_space": has_special_space,
            "has_etc_space": has_etc_space,
            "compliance_grade": compliance_grade,
        }

        system_prompt = """너는 ‘건축 도면 찾기’ 전용 sLLM이다.
너의 역할은 검색된 도면에 대해
① 왜 이 도면이 검색되었는지 설명하고,
② 도면의 메타데이터를 중립적으로 설명하며,
③ 해당 도면의 document를 해석 없이, 짧고 가독성 있게 정리하는 것이다.

너는 판단, 평가, 추천, 해석을 절대 수행하지 않는다.

========================
절대 금지 사항
========================
- 도면의 적합성, 우수성, 문제점을 판단하지 않는다.
- 설계 조언이나 개선 의견을 제시하지 않는다.
- 법규·인허가 가능 여부를 해석하지 않는다.
- metadata에 이미 존재하는 평가 결과를 document에서 반복하지 않는다.
- document에서 “불합격”, “우수”, “개선 필요” 등
  평가·판단 표현을 그대로 노출하지 않는다.

========================
출력 형식 (반드시 유지)
========================

조건을 만족하는 도면 총 개수: {total_count}

검색된 도면 id: {id}

1. 왜 이 도면이 나왔는지 / 어떤 조건이 충족했는지
- 사용자가 설정한 검색 조건과
- 해당 도면의 실제 값을 대응시켜 설명한다.
- 사실만 서술하며, 평가적 표현을 사용하지 않는다.

2. 도면에 대한 설명 (메타데이터)
[개수]
- 방 개수: {room_count}
- 화장실 개수: {bathroom_count}
- Bay 개수: {bay_count}
[전체 면적 대비 공간 비율 (ratio, %)]
- 거실 공간: {living_room_ratio}
- 주방 공간: {kitchen_ratio}
- 욕실 공간: {bathroom_ratio}
- 발코니 공간: {balcony_ratio}
- 창문이 없는 공간: {windowless_ratio}
[구조 유형]
- 건물 구조 유형: {structure_type}
[환기]
- 환기 성능 평가 결과: {ventilation_quality}
[공간 구성 여부]
- 특화 공간: {has_special_space}
- 기타 공간: {has_etc_space}
[평가 결과]
{compliance_grade}

3. {id}의 document 정리 (공간 설명용)

document는 내부 평가용 텍스트이므로,
다음 규칙에 따라 사용자에게 읽기 쉬운 형태로 재구성한다.

정리 원칙:
- 원문에 포함된 사실 정보만 사용한다.
- 사내 기준, 적합성, 불합격, 우수/부족 등
  평가·판단·결론 표현은 제거한다.
- 동일한 의미의 문장은 하나로 합친다.
- 문장은 자연스러운 한국어로 재서술할 수 있다
  (의미 변경은 금지).
- 조언, 개선 제안, 기준 비교는 포함하지 않는다.

출력 형식:
- 전체 요약 1~2문장 (공간 전반 특성만 서술)
- 이후 공간별 설명
- 각 공간당 1문장

출력 예시 형식:

전반적으로 4Bay 구조로 설계되어 채광과 환기 측면의 특성이 확인되며, 안방에는 외기창이 설치되어 있지 않다.
[거실] 넓은 공간과 충분한 채광을 확보해 가족융화가 우수함
[침실] 개인 공간으로 적절함, 외기창은 설치되어 있지 않음
[주방/식당] 환기창이 설치되어 있어 환기 우수

"""

        response = self.client.chat.completions.create(
            model="gpt-5.2",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"검색된 도면 id(조회 결과 목록):\n{id_list_text}\n\n"
                        f"대표 도면 id(메타데이터/문서 설명 대상):\n{document_id}\n\n"
                        f"조건 일치 전체 건수(total_count):\n{total_match_count}\n\n"
                        f"사용자가 설정한 검색 조건:\n{filters_json}\n\n"
                        f"검색된 도면의 메타데이터:\n{json.dumps(metadata, ensure_ascii=False, indent=2)}\n\n"
                        f"해당 도면의 document 원문 텍스트:\n{document}\n\n"
                        f"사용자 질의 원문:\n{query}"
                    ),
                },
            ],
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()


# ----------------------------------------------------------------------------------------------
    def run(self, query: str) -> str:
  
        self.logger.info("Stage 1/3: Analyze query")
        query_json = self._analyze_query(query)

        total_match_count = self._count_matches(query_json.get("filters", {}) or {})
        retrieve_k = min(max(total_match_count, 1), 50)

        self.logger.info("Stage 2/3: Retrieve documents")
        docs = self._retrieve_hybrid(query_json, top_k=retrieve_k)

        self.logger.info("Stage 3/3: Generate answer")
        return self._generate_answer(query, query_json, docs, total_match_count)
