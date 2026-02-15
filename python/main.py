"""
건축 평면도 분석 FastAPI 서버
Spring Boot와 연동하여 도면 이미지를 분석하고 결과를 반환
"""

import json
import logging
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# 스키마
from api_models.schemas import (
    AnalyzeResponse, SaveRequest, SaveResponse,
    OrchestrateResponse,
)

# 에이전트
from agents.orchestrator import OrchestratorAgent
from agents.cv_analysis_agent import CVAnalysisAgent

# /generate-metadata 에서만 직접 사용
from services.rag_service import rag_service
from services.embedding_service import embedding_service

from api_utils.image_utils import image_to_base64

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger("FastAPI")

# FastAPI 앱 초기화
app = FastAPI(title="건축 평면도 분석 API")

# CORS 설정 (Spring Boot와 통신을 위해)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 싱글톤 에이전트 인스턴스
orchestrator = OrchestratorAgent()
cv_analysis_agent = CVAnalysisAgent()


# ===== API 엔드포인트 =====

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_floorplan(file: UploadFile = File(...)):
    """
    도면 이미지 분석 엔드포인트

    Input: PNG 파일
    Output: topology_graph, topology_image, analysis_result (with LLM document)
    """
    logger.info("=== /analyze 엔드포인트 호출됨 ===")
    logger.info(f"파일명: {file.filename}")

    try:
        # 이미지 파일 읽기
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다.")

        logger.info(f"이미지 수신 완료: {file.filename}, 크기: {image.shape}")

        # CV 에이전트 실행 (preview 모드: CV 추론 + LLM 분석까지만)
        cv_result = cv_analysis_agent.execute(
            image=image, filename=file.filename, mode="preview",
        )

        response = AnalyzeResponse(
            topology_json=json.dumps(cv_result.topology_data, ensure_ascii=False),
            topology_image_url=cv_result.topology_image_base64,
            llm_analysis_json=json.dumps(cv_result.llm_analysis, ensure_ascii=False),
        )

        logger.info("=== /analyze 완료 ===")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"분석 중 오류: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"분석 실패: {str(e)}")


@app.post("/generate-metadata", response_model=SaveResponse)
async def generate_metadata(request: SaveRequest):
    """
    메타데이터 생성 엔드포인트

    Input: llm_analysis_json (FloorPlanAnalysis JSON 문자열)
    Output: metadata + document + embedding
    """
    logger.info("=== /generate-metadata 엔드포인트 호출됨 ===")

    try:
        # 1. llm_analysis_json 파싱 → FloorPlanAnalysis 객체로 변환
        from CV.rag_system.schemas import FloorPlanAnalysis
        llm_analysis_dict = json.loads(request.llm_analysis_json)
        llm_analysis = FloorPlanAnalysis(**llm_analysis_dict)

        # 2. 13개 지표 추출
        metrics = rag_service.extract_metrics(llm_analysis)

        # 3. document 생성 (to_natural_language)
        document = llm_analysis.to_natural_language()

        # 4. 임베딩 생성
        embedding_vector = embedding_service.generate_embedding(document)

        # 5. 응답 생성 (Spring Boot로 반환)
        response = SaveResponse(
            document_id=f"floorplan_{hash(document) % 1000000}",
            metadata=metrics,
            document=document,
            embedding=embedding_vector,
        )

        logger.info("=== /generate-metadata 완료 ===")
        return response

    except Exception as e:
        logger.error(f"메타데이터 생성 중 오류: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"메타데이터 생성 실패: {str(e)}")


@app.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate_query(
    email: str = Form(...),
    question: str = Form(""),
    file: Optional[UploadFile] = File(None),
):
    """
    의도 분류 오케스트레이터 엔드포인트

    텍스트 질문 → 의도 분류 → 도면 검색 / 법규 검색 에이전트 라우팅
    이미지 업로드 → CV 분석 → 도면 검색 에이전트 (image 모드)
    """
    logger.info("=== /orchestrate 엔드포인트 호출됨 ===")
    logger.info(f"Email: {email}, Question: {question}, File: {file is not None}")

    try:
        image = None
        filename = ""

        if file is not None:
            contents = await file.read()
            nparr = np.frombuffer(contents, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            filename = file.filename or ""
            if image is None:
                raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다.")

        result = orchestrator.route(
            email=email,
            question=question,
            image=image,
            filename=filename,
        )

        logger.info(
            f"오케스트레이션 완료: intent={result['intent_type']}, "
            f"agent={result['agent_used']}"
        )

        return OrchestrateResponse(**result)

    except ValueError as ve:
        logger.warning(f"[Orchestrator] 입력 검증 실패: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[Orchestrator] 오류 발생: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail="오케스트레이션 처리 중 내부 오류가 발생했습니다.",
        )


@app.get("/health")
def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "orchestrator_loaded": orchestrator.is_loaded(),
        "cv_agent_loaded": cv_analysis_agent.is_loaded(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
