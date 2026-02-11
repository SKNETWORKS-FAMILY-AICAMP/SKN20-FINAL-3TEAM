import logging
import unittest
from types import SimpleNamespace

from pipeline import ArchitecturalHybridRAG


def _make_rag_for_validation(
    *,
    enabled: bool = True,
    retry_max: int = 1,
    safe_fallback: bool = True,
    logger_name: str = "pipeline.validation.tests",
):
    rag = ArchitecturalHybridRAG.__new__(ArchitecturalHybridRAG)
    rag.logger = logging.getLogger(logger_name)
    rag.answer_validation_enabled = enabled
    rag.answer_validation_retry_max = retry_max
    rag.answer_validation_safe_fallback = safe_fallback
    return rag


class _FallbackCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.conn.sql_history.append((sql, params))
        if self.conn.fail_on_websearch and "websearch_to_tsquery" in sql:
            raise RuntimeError("invalid tsquery")

    def fetchall(self):
        return list(self.conn.fetchall_rows)

    def fetchone(self):
        return self.conn.fetchone_row


class _FallbackConnection:
    def __init__(
        self,
        *,
        fetchall_rows=None,
        fetchone_row=(0,),
        fail_on_websearch=True,
    ):
        self.fetchall_rows = fetchall_rows or []
        self.fetchone_row = fetchone_row
        self.fail_on_websearch = fail_on_websearch
        self.sql_history: list[tuple[str, object]] = []

    def cursor(self):
        return _FallbackCursor(self)


class _FakeEmbeddingsClient:
    def __init__(self, embedding):
        self.embedding = embedding

    def create(self, **kwargs):
        _ = kwargs
        return SimpleNamespace(data=[SimpleNamespace(embedding=self.embedding)])


class _FakeOpenAIClient:
    def __init__(self, embedding):
        self.embeddings = _FakeEmbeddingsClient(embedding)


class PipelineAnswerValidationTests(unittest.TestCase):
    def test_validate_document_id_success(self):
        rag = _make_rag_for_validation()
        answer = (
            "1. 검색된 도면 id: APT_FP_001.PNG\n\n"
            "2. 도면 기본 정보 요약 📊\n"
            "- 방 개수: 3\n\n"
            "3. 도면 공간 구성 설명 🧩\n"
            "- 거실 중심 배치"
        )
        result = rag._validate_answer_format(
            answer=answer,
            mode="document_id",
            expected_document_id="APT_FP_001.PNG",
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.missing_fields, [])

    def test_validate_document_id_mismatch_fails(self):
        rag = _make_rag_for_validation()
        answer = (
            "1. 검색된 도면 id: APT_FP_999.PNG\n\n"
            "2. 도면 기본 정보 요약 📊\n"
            "- 방 개수: 3\n\n"
            "3. 도면 공간 구성 설명 🧩\n"
            "- 거실 중심 배치"
        )
        result = rag._validate_answer_format(
            answer=answer,
            mode="document_id",
            expected_document_id="APT_FP_001.PNG",
        )
        self.assertFalse(result.ok)
        self.assertIn("document_id_token", result.missing_fields)

    def test_validate_general_success(self):
        rag = _make_rag_for_validation()
        answer = (
            "검색된 도면 id: APT_FP_001.PNG, APT_FP_002.PNG\n\n"
            "2. 도면 기본 정보 요약 📊\n"
            "- 방 개수: 3\n\n"
            "3. 도면 공간 구성 설명 🧩\n"
            "- 거실 중심 배치"
        )
        result = rag._validate_answer_format(answer=answer, mode="general")
        self.assertTrue(result.ok)

    def test_validate_missing_layout_section_fails(self):
        rag = _make_rag_for_validation()
        answer = (
            "검색된 도면 id: APT_FP_001.PNG\n\n"
            "2. 도면 기본 정보 요약 📊\n"
            "- 방 개수: 3\n"
        )
        result = rag._validate_answer_format(answer=answer, mode="general")
        self.assertFalse(result.ok)
        self.assertIn("layout_summary", result.missing_fields)

    def test_validate_no_match_success(self):
        rag = _make_rag_for_validation()
        answer = rag._generate_no_match_answer(total_match_count=0)
        result = rag._validate_answer_format(answer=answer, mode="no_match")
        self.assertTrue(result.ok)
        self.assertEqual(result.missing_fields, [])

    def test_run_validated_generation_retry_success(self):
        rag = _make_rag_for_validation(retry_max=1, safe_fallback=True)
        bad = "형식 오류 응답"
        good = (
            "검색된 도면 id: APT_FP_001.PNG\n\n"
            "2. 도면 기본 정보 요약 📊\n"
            "- 방 개수: 3\n\n"
            "3. 도면 공간 구성 설명 🧩\n"
            "- 거실 중심 배치"
        )
        calls = {"n": 0}
        responses = [bad, good]

        def generate():
            idx = calls["n"]
            calls["n"] += 1
            return responses[idx]

        output = rag._run_validated_generation(mode="general", generate_fn=generate)
        self.assertEqual(output, good)
        self.assertEqual(calls["n"], 2)

    def test_run_validated_generation_returns_fallback_after_retry_fail(self):
        rag = _make_rag_for_validation(retry_max=1, safe_fallback=True)
        calls = {"n": 0}

        def generate():
            calls["n"] += 1
            return "형식 오류 응답"

        output = rag._run_validated_generation(mode="general", generate_fn=generate)
        self.assertIn("2. 도면 기본 정보 요약", output)
        self.assertIn("3. 도면 공간 구성 설명", output)
        self.assertIn("검색된 도면 id", output)
        self.assertEqual(calls["n"], 2)

    def test_run_validated_generation_disabled_skips_validation(self):
        rag = _make_rag_for_validation(enabled=False, retry_max=3, safe_fallback=True)
        calls = {"n": 0}
        raw = "형식 오류 응답"

        def generate():
            calls["n"] += 1
            return raw

        output = rag._run_validated_generation(mode="general", generate_fn=generate)
        self.assertEqual(output, raw)
        self.assertEqual(calls["n"], 1)

    def test_run_validated_generation_logs_failures(self):
        logger_name = "pipeline.validation.tests.logging"
        rag = _make_rag_for_validation(
            retry_max=0, safe_fallback=True, logger_name=logger_name
        )

        with self.assertLogs(logger_name, level="WARNING") as logs:
            rag._run_validated_generation(
                mode="general",
                generate_fn=lambda: "형식 오류 응답",
            )

        joined = "\n".join(logs.output)
        self.assertIn("answer_validation_fail", joined)
        self.assertIn("answer_validation_fallback", joined)

    def test_run_validated_generation_generation_error_returns_fallback(self):
        rag = _make_rag_for_validation(retry_max=1, safe_fallback=True)

        def generate():
            raise RuntimeError("llm timeout")

        output = rag._run_validated_generation(mode="general", generate_fn=generate)
        self.assertIn("검색된 도면 id", output)
        self.assertIn("2. 도면 기본 정보 요약", output)

    def test_generate_validated_no_match_fallback_when_template_is_broken(self):
        rag = _make_rag_for_validation(retry_max=1, safe_fallback=True)
        rag._generate_no_match_answer = lambda total_match_count=0: "broken"

        output = rag._generate_validated_no_match_answer(total_match_count=0)
        self.assertIn("조건을 만족하는 도면 총 개수: 0", output)
        self.assertIn("검색된 도면 id: 없음", output)

    def test_retrieve_hybrid_falls_back_when_text_query_is_invalid(self):
        rag = _make_rag_for_validation()
        rag.embedding_model = "text-embedding-3-small"
        rag.embedding_dimensions = 2
        rag.vector_weight = 0.8
        rag.text_weight = 0.2
        rag.client = _FakeOpenAIClient([0.1, 0.2])
        rag.conn = _FallbackConnection(
            fetchall_rows=[("APT_FP_001.PNG",)],
            fail_on_websearch=True,
        )

        docs = rag._retrieve_hybrid(
            {"filters": {}, "documents": "오앙", "raw_query": "오앙"},
            top_k=3,
        )

        self.assertEqual(docs, [("APT_FP_001.PNG",)])
        self.assertEqual(len(rag.conn.sql_history), 2)
        first_sql = rag.conn.sql_history[0][0]
        second_sql = rag.conn.sql_history[1][0]
        self.assertIn("websearch_to_tsquery", first_sql)
        self.assertNotIn("websearch_to_tsquery", second_sql)

    def test_count_matches_falls_back_when_text_query_is_invalid(self):
        rag = _make_rag_for_validation()
        rag.conn = _FallbackConnection(
            fetchone_row=(7,),
            fail_on_websearch=True,
        )

        count = rag._count_matches(filters={}, documents="오앙")

        self.assertEqual(count, 7)
        self.assertEqual(len(rag.conn.sql_history), 2)
        first_sql = rag.conn.sql_history[0][0]
        second_sql = rag.conn.sql_history[1][0]
        self.assertIn("websearch_to_tsquery", first_sql)
        self.assertNotIn("websearch_to_tsquery", second_sql)


if __name__ == "__main__":
    unittest.main()
