"""
건축 평면도 분석 FastAPI 서버
Spring Boot와 연동하여 도면 이미지를 분석하고 결과를 반환
"""

import json
import logging
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# 로컬 모듈 import
from api_models.schemas import AnalyzeResponse, SaveRequest, SaveResponse
from services.cv_service import cv_service
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


# ===== API 엔드포인트 =====

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_floorplan(file: UploadFile = File(...)):
    """
    도면 이미지 분석 엔드포인트

    Input: PNG 파일
    Output: topology_graph, topology_image, analysis_result (with LLM document)
    """
    logger.info("=" * 80)
    logger.info("=== /analyze 엔드포인트 호출됨 ===")
    logger.info(f"파일명: {file.filename}")
    logger.info(f"Content-Type: {file.content_type}")
    logger.info("=" * 80)
    
    try:
        # 1. 이미지 파일 읽기
        logger.info("Step 1: 이미지 파일 읽기 시작...")
        contents = await file.read()
        logger.info(f"파일 크기: {len(contents)} bytes")
        
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            logger.error("이미지 디코딩 실패!")
            raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다.")

        logger.info(f"이미지 수신 완료: {file.filename}, 크기: {image.shape}")

        # 2. CV 파이프라인 실행
        logger.info("Step 2: CV 추론 시작...")
        results = cv_service.analyze_image(
            image=image,
            filename=file.filename,
            save_json=True,
            save_visualization=True
        )
        logger.info("CV 추론 완료!")

        # 3. topology_graph.json 추출
        logger.info("Step 3: topology_graph 추출...")
        topology_data = results.get("topology_graph", {})
        logger.info(f"Topology 데이터 크기: {len(str(topology_data))} chars")

        # 4. topology 이미지 Base64 인코딩
        logger.info("Step 4: topology 이미지 인코딩...")
        topology_image_path = cv_service.get_topology_image_path(file.filename)
        logger.info(f"Topology 이미지 경로: {topology_image_path}")
        
        if topology_image_path.exists():
            topology_image = cv2.imread(str(topology_image_path))
            topology_image_base64 = f"data:image/png;base64,{image_to_base64(topology_image)}"
            logger.info(f"Topology 이미지 인코딩 성공! (크기: {len(topology_image_base64)} chars)")
        else:
            logger.warning(f"Topology 이미지 파일을 찾을 수 없습니다: {topology_image_path}")
            topology_image_base64 = ""

        # 5. RAG LLM 분석 실행
        logger.info("Step 5: RAG LLM 분석 시작...")
        llm_analysis = rag_service.analyze_topology(topology_data)
        logger.info("RAG LLM 분석 완료!")

        # 6. 13개 지표 추출
        logger.info("Step 6: 메트릭 추출...")
        metrics = rag_service.extract_metrics(llm_analysis)

        # 7. to_natural_language()로 document 생성
        logger.info("Step 7: Document 생성...")
        document = llm_analysis.to_natural_language()

        # 8. 임베딩 생성
        logger.info("Step 8: 임베딩 생성...")
        embedding = embedding_service.generate_embedding(document)

        # 9. 응답 생성 (Spring Boot 형식에 맞춤)
        logger.info("Step 9: 응답 생성...")
        response = AnalyzeResponse(
            topology_json=json.dumps(topology_data, ensure_ascii=False),  # 1번
            topology_image_url=topology_image_base64,  # 2번
            assessment_json=json.dumps(topology_data, ensure_ascii=False),  # 3번
            **metrics,  # 13개 지표
            analysis_description=document,
            embedding=embedding
        )

        # 10. analysis_result.json 저장
        logger.info("Step 10: analysis_result.json 저장 시작...")
        try:
            output_dir = cv_service.pipeline.config.OUTPUT_PATH / Path(file.filename).stem
            output_dir.mkdir(parents=True, exist_ok=True)
            analysis_result_path = output_dir / "analysis_result.json"
            logger.info(f"저장 경로: {analysis_result_path}")
            
            # Pydantic v1/v2 호환성 처리
            response_dict = response.model_dump() if hasattr(response, 'model_dump') else response.dict()
            
            with open(analysis_result_path, "w", encoding="utf-8") as f:
                json.dump(response_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✓ analysis_result.json 저장 완료! ({analysis_result_path.stat().st_size} bytes)")
        except Exception as save_error:
            logger.error(f"✗ analysis_result.json 저장 실패: {save_error}")
            logger.error(f"에러 타입: {type(save_error).__name__}")
            import traceback
            traceback.print_exc()

        logger.info("=" * 80)
        logger.info("=== 분석 완료! 응답 반환 ===")
        logger.info("=" * 80)
        return response

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"!!! 분석 중 오류 발생 !!!")
        logger.error(f"에러 타입: {type(e).__name__}")
        logger.error(f"에러 메시지: {str(e)}")
        logger.error("=" * 80)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"분석 실패: {str(e)}")


@app.post("/generate-metadata", response_model=SaveResponse)
async def generate_metadata(request: SaveRequest):
    """
    메타데이터 생성 엔드포인트 (4번 생성)
    
    Input: assessment_json (3번 - topology_graph.json 문자열)
    Output: metadata + document + embedding (4번)
    """
    logger.info("=" * 80)
    logger.info("=== /generate-metadata 엔드포인트 호출됨 ===")
    logger.info("=" * 80)
    
    try:
        # 1. assessmentJson 파싱
        logger.info("Step 1: assessment_json 파싱...")
        topology_data = json.loads(request.assessment_json)
        
        # 2. RAG LLM 분석 실행
        logger.info("Step 2: RAG LLM 분석 시작...")
        llm_analysis = rag_service.analyze_topology(topology_data)
        logger.info("RAG LLM 분석 완료!")
        
        # 3. 13개 지표 추출
        logger.info("Step 3: 메트릭 추출...")
        metrics = rag_service.extract_metrics(llm_analysis)
        
        # 4. document 생성
        logger.info("Step 4: Document 생성...")
        document = llm_analysis.to_natural_language()
        
        # 5. 임베딩 생성
        logger.info("Step 5: 임베딩 생성 중...")
        embedding_vector = embedding_service.generate_embedding(document)
        
        # 6. 응답 생성 (Spring Boot 형식)
        logger.info("Step 6: 메타데이터 생성 완료!")
        
        response = SaveResponse(
            document_id=f"floorplan_{hash(document) % 1000000}",
            metadata=metrics,
            document=document,
            embedding=embedding_vector  # 전체 벡터 전송
        )
        
        logger.info("=" * 80)
        logger.info("=== 메타데이터 생성 완료! ===")
        logger.info("=" * 80)
        
        return response

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"!!! 메타데이터 생성 중 오류 !!!")
        logger.error(f"에러 타입: {type(e).__name__}")
        logger.error(f"에러 메시지: {str(e)}")
        logger.error("=" * 80)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"메타데이터 생성 실패: {str(e)}")


@app.get("/health")
def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "cv_pipeline_loaded": cv_service.is_loaded(),
        "rag_loaded": rag_service.is_loaded(),
        "embedding_loaded": embedding_service.is_loaded()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)