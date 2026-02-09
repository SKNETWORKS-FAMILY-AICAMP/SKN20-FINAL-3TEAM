import json
import logging
import re
from pathlib import Path
from typing import Any
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
            '    "windowless_ratio": "number(optional)",\n'
            '    "balcony_ratio": "number(optional)",\n'
            '    "living_room_ratio": "number(optional)",\n'
            '    "bathroom_ratio": "number(optional)",\n'
            '    "kitchen_ratio": "number(optional)",\n'
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
            if isinstance(value, bool):
                return None
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                match = re.search(r"-?\d+(\.\d+)?", value)
                if match:
                    return float(match.group())
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
        if re.search(r"(%|퍼센트|비율|ratio)", query, flags=re.IGNORECASE):
            return filters

        sanitized = dict(filters)
        for key in self.FLOAT_FILTERS:
            sanitized.pop(key, None)
        return sanitized

    def _retrieve_hybrid(self, query_json: dict, top_k: int = 3) -> list:
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
            where_clauses.append(f"{column} = %s")
            params.append(value)

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        params.append(self.vector_weight)
        params.append(self.text_weight)
        params.append(top_k)

        sql = f"""
            WITH scored AS (
                SELECT document_id, windowless_ratio, balcony_ratio, living_room_ratio, bathroom_ratio, kitchen_ratio,
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
            SELECT document_id, windowless_ratio, balcony_ratio, living_room_ratio, bathroom_ratio, kitchen_ratio,
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

    def _generate_answer(self, query: str, docs: list) -> str:
        """
        Format retrieved docs as documents and send to the LLM to generate the answer
        """
        if not docs:
            return "Try searching again."

        documents_lines = []
        for idx, row in enumerate(docs, start=1):
            (
                document_id,
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
                similarity,
            ) = row
            documents_lines.append(
                f"[Candidate {idx}] ID: {document_id}, "
                f"Structure: {structure_type}, Bay: {bay_count}, "
                f"Rooms: {room_count}, Bathrooms: {bathroom_count}, "
                f"Compliance: {compliance_grade}, Similarity: {similarity:.4f}, "
                f"WindowlessRatio: {windowless_ratio}, BalconyRatio: {balcony_ratio}, "
                f"LivingRoomRatio: {living_room_ratio}, BathroomRatio: {bathroom_ratio}, KitchenRatio: {kitchen_ratio}, "
                f"Ventilation: {ventilation_grade}, SpecialSpace: {has_special_space}, EtcSpace: {has_etc_space}"
            )

        documents = "\n".join(documents_lines)
        system_prompt = (
            "You are an architectural drawing recommendation expert.\n"
            "Requirements:\n"
            "1) Explicitly state the document_id of the recommended drawing.\n"
            "2) Explain why it matches the user query using only provided features.\n"
            "3) Do not fabricate facts not present in the documents."
        )

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"User Query:\n{query}\n\nRetrieved Documents:\n{documents}",
                },
            ],
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()


# ----------------------------------------------------------------------------------------------
    def run(self, query: str) -> str:
  
        self.logger.info("Stage 1/3: Analyze query")
        query_json = self._analyze_query(query)

        self.logger.info("Stage 2/3: Retrieve documents")
        docs = self._retrieve_hybrid(query_json)

        self.logger.info("Stage 3/3: Generate answer")
        return self._generate_answer(query, docs)