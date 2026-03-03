"""
도면 검색 에이전트
text_search 모드: ArchitecturalHybridRAG.run() 래핑
image 모드: CV 분석 결과 → 섹션 2,3 답변 생성
"""

import json
import logging
import re
from typing import Optional

from agents.base import BaseAgent
from api_models.schemas import CVAnalysisResult

logger = logging.getLogger("FloorplanSearchAgent")


class FloorplanSearchAgent(BaseAgent):
    """도면 검색 에이전트 — text_search / image 두 가지 모드"""

    @property
    def name(self) -> str:
        return "floorplan_search"

    def __init__(self):
        self._rag = None
        self._config = None
        self._db_conn = None

    def _load_components(self):
        if self._rag is not None:
            return

        from CV.rag_system.config import RAGConfig
        self._config = RAGConfig()

        db_config = {
            "host": self._config.POSTGRES_HOST,
            "port": self._config.POSTGRES_PORT,
            "database": self._config.POSTGRES_DB,
            "user": self._config.POSTGRES_USER,
            "password": self._config.POSTGRES_PASSWORD,
        }

        import psycopg2
        self._db_conn = psycopg2.connect(**db_config)

        from services.floorplan_text_search_service import ArchitecturalHybridRAG
        self._rag = ArchitecturalHybridRAG(
            db_config=db_config,
            openai_api_key=self._config.OPENAI_API_KEY,
            llm_backend=self._config.LLM_BACKEND,
            vllm_base_url=self._config.VLLM_BASE_URL,
            vllm_search_model_name=self._config.VLLM_SEARCH_MODEL_NAME,
        )
        logger.info("FloorplanSearchAgent 컴포넌트 로드 완료")

    def execute(self, mode: str, **kwargs) -> dict:
        """
        Args:
            mode: "text_search" | "image" | "image_search"
            kwargs:
                text_search  → query: str, email: str
                image        → cv_result: CVAnalysisResult
                image_search → cv_result: CVAnalysisResult
        """
        self._load_components()

        if mode == "text_search":
            return self._execute_text_search(
                query=kwargs["query"],
                email=kwargs["email"],
                chat_room_id=kwargs.get("chat_room_id"),
            )
        elif mode == "image":
            return self._execute_image_analysis(
                cv_result=kwargs["cv_result"],
            )
        elif mode == "image_search":
            return self._execute_image_search(
                cv_result=kwargs["cv_result"],
            )
        else:
            raise ValueError(f"지원하지 않는 모드: {mode}")

    # ===== text_search 모드 =====

    def _execute_text_search(self, query: str, email: str, chat_room_id: int = None) -> dict:
        """기존 ArchitecturalHybridRAG.run() 호출"""
        logger.info(f"[text_search] 질의: {query}")
        result = self._rag.run(query, email=email, chat_room_id=chat_room_id)
        return {
            "summaryTitle": query[:30] + "..." if len(query) > 30 else query,
            "answer": result.get("answer", "답변을 생성하지 못했습니다."),
            "floorplan_ids": result.get("floorplan_ids", []),
        }

    # ===== image 모드 =====

    def _execute_image_analysis(self, cv_result: CVAnalysisResult) -> dict:
        """CV 분석 결과 → 섹션 2,3 답변 생성"""
        logger.info("[image] 이미지 분석 결과로 답변 생성 시작")
        answer = self._generate_answer_sections_2_3(cv_result)
        return {
            "summaryTitle": "도면 이미지 분석 결과",
            "answer": answer,
            "floorplan_ids": None,
        }

    # ===== image_search 모드 =====

    def _execute_image_search(self, cv_result: CVAnalysisResult) -> dict:
        """CV 분석 결과 → 분석 텍스트 + 유사 도면 검색 (image_search 모듈 사용)"""
        from services.floorplan_image_search_service import search_similar

        logger.info("=" * 50)
        logger.info("[image_search] 이미지 분석 + 유사 도면 검색 시작")
        logger.info("=" * 50)

        # 1. 분석 텍스트 생성 (도면 기본 정보 + 공간 구성 설명)
        logger.info("[1/3] 도면 분석 텍스트 생성 중...")
        analysis_text = self._generate_answer_sections_2_3(cv_result)
        logger.info("[1/3] 분석 텍스트 생성 완료")

        # 2. 검색 쿼리 + 필터 구성
        metrics = cv_result.metrics or {}
        metric_parts = []
        if metrics.get("structure_type"):
            metric_parts.append(f"{metrics['structure_type']} 구조")
        if metrics.get("bay_count"):
            metric_parts.append(f"{metrics['bay_count']}베이")
        if metrics.get("room_count"):
            metric_parts.append(f"방 {metrics['room_count']}개")
        if metrics.get("bathroom_count"):
            metric_parts.append(f"화장실 {metrics['bathroom_count']}개")
        if metrics.get("windowless_count") is not None:
            metric_parts.append(f"무창 공간 {metrics['windowless_count']}개")
        if metrics.get("living_room_ratio") is not None:
            metric_parts.append(f"거실 비율 {metrics['living_room_ratio']}%")

        summary_match = re.search(r'Overall summary:\s*(.+?)(?:\n|$)', analysis_text)
        overall_summary = summary_match.group(1).strip() if summary_match else ""

        metrics_prefix = ", ".join(metric_parts) + ". " if metric_parts else ""
        search_query = metrics_prefix + overall_summary
        if not search_query.strip():
            search_query = (cv_result.document or "")[:200]

        filters = {}
        for key in ("structure_type", "room_count", "bay_count", "bathroom_count", "windowless_count"):
            if metrics.get(key) is not None:
                filters[key] = metrics[key]
        if metrics.get("living_room_ratio") is not None:
            filters["living_room_ratio"] = {"op": "동일", "val": metrics["living_room_ratio"]}

        # 3. 유사 도면 검색 (image_search 모듈 — 임베딩 유사도 + 필터 완화)
        logger.info("[2/3] 유사 도면 검색 시작...")
        search_result = search_similar(
            conn=self._db_conn,
            description=search_query,
            filters=filters,
            top_k=3,
        )
        docs = search_result["docs"]
        total_count = search_result["total_count"]
        floorplan_ids = [row[0] for row in docs] if docs else []

        logger.info(
            "[2/3] 유사 도면 %d개 반환 (총 %d개 중): %s",
            len(floorplan_ids), total_count, floorplan_ids,
        )

        # 4. 유사 도면 구조화된 설명 생성 (LLM)
        answer = analysis_text
        if docs:
            logger.info("[3/3] 유사 도면 구조화된 설명 생성 중 (LLM)...")
            similar_answer = self._rag.generate_similar_answer(
                analysis_metrics=metrics,
                docs=docs,
                total_count=total_count,
            )
            if similar_answer:
                answer += "\n\n" + similar_answer
            logger.info("[3/3] 유사 도면 설명 생성 완료")
        else:
            logger.info("[3/3] 유사 도면 없음 — 설명 생성 건너뜀")

        logger.info("=" * 50)
        logger.info("[image_search] 완료 (도면 %d개)", len(floorplan_ids))
        logger.info("=" * 50)

        return {
            "summaryTitle": "도면 이미지 분석 결과",
            "answer": answer,
            "floorplan_ids": floorplan_ids if floorplan_ids else None,
        }

    def _generate_answer_sections_2_3(self, cv_result: CVAnalysisResult) -> str:
        """섹션 2(기본 정보) + 섹션 3(공간 구성 설명) 전용 LLM 호출"""
        metrics = cv_result.metrics
        document = cv_result.document

        system_prompt = self._build_image_mode_system_prompt()
        user_content = self._build_image_mode_user_content(metrics, document)

        logger.info(
            "[Step1-도면분석] 프롬프트 준비 — system=%d chars, user=%d chars, model=%s",
            len(system_prompt), len(user_content), self._rag.llm_model_name,
        )

        response = self._rag.client.chat.completions.create(
            model=self._rag.llm_model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            max_tokens=1500,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

        usage = response.usage
        finish = response.choices[0].finish_reason
        if usage:
            logger.info(
                "[Step1-도면분석] 토큰 사용량 — prompt=%d, completion=%d, total=%d, finish=%s",
                usage.prompt_tokens, usage.completion_tokens, usage.total_tokens, finish,
            )
        if finish == "length":
            logger.warning("[Step1-도면분석] ⚠️ max_tokens에서 잘림! 출력이 불완전할 수 있음")

        raw = response.choices[0].message.content or ""
        raw = re.sub(r"<think>[\s\S]*?</think>\s*", "", raw)
        raw = re.sub(r"</?think>\s*", "", raw)
        logger.info("[Step1-도면분석] 응답 길이 — %d chars", len(raw.strip()))
        return raw.strip()

    def _build_image_mode_system_prompt(self) -> str:
        """CV 분석 결과를 정해진 포맷으로 출력하는 sLLM 전용 프롬프트"""
        return """주어진 메타데이터와 document를 아래 고정 형식에 맞춰 한국어로 출력하라.
값을 그대로 사용하고, 판단·평가·추천은 절대 하지 마라.

### 1. 도면 기본 정보 📊
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

### 2. 도면 공간 구성 설명 🧩
■ 종합 등급: {compliance_grade}
• 적합 항목: {compliance_fit_items를 그대로 사용, 없으면 없음}
• 부적합 항목: {compliance_unfit_items를 그대로 사용, 없으면 없음}
■ 핵심 설계 평가
[평가 항목명] ...
■ 주요 공간별 상세 분석
[공간명] ...

## FEW-SHOT EXAMPLES

### 핵심 설계 평가 문장 스타일
Source: "거실 채광 우수. 주방 환기 미흡. 드레스룸 연결 구조."

Correct:
[채광] 거실의 채광 환경이 우수합니다.
[환기] 주방의 환기 성능이 미흡합니다.
[안방] 드레스룸이 연결된 구조입니다.

Wrong:
[평가 항목명] ...

## 중단 규칙
동일 공간이 여러 개면 하나로 합쳐라. 절대 반복하지 마라. 위 항목을 모두 작성하면 즉시 종료하라.
"""

    def _build_image_mode_user_content(self, metrics: dict, document: str) -> str:
        # boolean → 한글 변환 (sLLM이 true/false를 그대로 출력하는 문제 방지)
        display = {**metrics}
        for key in ("has_special_space", "has_etc_space"):
            if key in display:
                display[key] = "존재" if display[key] else "없음"
        return (
            f"도면 메타데이터:\n{json.dumps(display, ensure_ascii=False, indent=2)}\n\n"
            f"도면 분석 document:\n{document}\n\n"
            "위 데이터를 기반으로 '1. 도면 기본 정보'와 '2. 도면 공간 구성 설명'을 작성하세요."
        )

    def is_loaded(self) -> bool:
        return self._rag is not None
