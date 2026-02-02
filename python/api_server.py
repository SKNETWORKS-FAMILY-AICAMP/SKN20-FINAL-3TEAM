"""
건축 평면도 분석 FastAPI 서버
Spring Boot와 연동하여 도면 이미지를 분석하고 결과를 반환
"""

import os
import json
import base64
import logging
from pathlib import Path
from typing import Optional, Dict, Any

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

# CV 추론 파이프라인 import
from CV.cv_inference.pipeline import InferencePipeline
from CV.cv_inference.config import InferenceConfig

# RAG 시스템 import
from CV.rag_system.config import RAGConfig
from CV.rag_system.embeddings import EmbeddingManager
from CV.rag_system.vector_store import VectorStore
from CV.rag_system.llm_client import OpenAIClient
from CV.rag_system.schemas import FloorPlanAnalysis
from CV.rag_system.prompts import SYSTEM_PROMPT, build_analysis_prompt

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

# 전역 변수
cv_pipeline: Optional[InferencePipeline] = None
rag_config: Optional[RAGConfig] = None
embedding_manager: Optional[EmbeddingManager] = None
vector_store: Optional[VectorStore] = None
llm_client: Optional[OpenAIClient] = None


# ===== 요청/응답 모델 정의 =====

class AnalysisResult(BaseModel):
    """분석 결과 (13개 지표 + LLM 분석 document)"""
    # 13개 지표
    windowless_ratio: float
    has_special_space: bool
    bay_count: int
    balcony_ratio: float
    living_room_ratio: float
    bathroom_ratio: float
    kitchen_ratio: float
    room_count: int
    compliance_grade: str
    ventilation_quality: str
    has_etc_space: bool
    structure_type: str
    bathroom_count: int
    # LLM 분석 결과 (to_natural_language() 출력)
    document: str


class AnalyzeResponse(BaseModel):
    """도면 분석 응답 모델 - Spring Boot와 매핑"""
    topology_json: str  # 1번: topology json string
    topology_image_url: str  # 2번: base64 이미지
    assessment_json: str  # 3번: topology_graph.json 전체
    
    # 13개 분석 지표 (flat 구조)
    windowless_ratio: float
    has_special_space: bool
    bay_count: int
    balcony_ratio: float
    living_room_ratio: float
    bathroom_ratio: float
    kitchen_ratio: float
    room_count: int
    compliance_grade: str
    ventilation_quality: str
    has_etc_space: bool
    structure_type: str
    bathroom_count: int
    analysis_description: str  # LLM 분석 결과 문서
    embedding: list[float]  # 임베딩 벡터 (1536차원)


class SaveRequest(BaseModel):
    """저장 요청 모델 - Spring Boot에서 assessmentJson (3번) 전송"""
    assessment_json: str  # topology_graph.json 문자열


class SaveResponse(BaseModel):
    """저장 응답 모델 - Spring Boot로 4번 데이터 전송"""
    document_id: str
    metadata: Dict[str, Any]  # 13개 지표
    document: str  # 분석 설명
    embedding: list[float]  # 전체 임베딩 벡터 (1536차원)


# ===== 유틸리티 함수 =====

def image_to_base64(image: np.ndarray) -> str:
    """OpenCV 이미지를 Base64 문자열로 변환"""
    _, buffer = cv2.imencode('.png', image)
    return base64.b64encode(buffer).decode('utf-8')


def load_cv_pipeline():
    """CV 파이프라인을 lazy loading 방식으로 로드"""
    global cv_pipeline

    if cv_pipeline is not None:
        return cv_pipeline

    logger.info("=" * 60)
    logger.info("첫 요청 감지 - CV 모델 로딩 중...")
    logger.info("=" * 60)

    try:
        config = InferenceConfig()
        config.OUTPUT_PATH = Path("./temp_output")
        config.OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

        cv_pipeline = InferencePipeline(config)
        cv_pipeline.load_models()

        logger.info("CV 모델 로딩 완료!")
        return cv_pipeline
    except Exception as e:
        logger.error(f"CV 모델 로딩 실패: {e}")
        raise HTTPException(status_code=500, detail=f"CV 모델 로딩 실패: {str(e)}")


def load_rag_components():
    """RAG 컴포넌트를 lazy loading 방식으로 로드"""
    global rag_config, embedding_manager, vector_store, llm_client

    if llm_client is not None:
        return

    logger.info("RAG 컴포넌트 로딩 중...")

    try:
        rag_config = RAGConfig()
        embedding_manager = EmbeddingManager(
            api_key=rag_config.OPENAI_API_KEY,
            model="text-embedding-3-small"
        )
        vector_store = VectorStore(db_path="CV/rag_data")
        llm_client = OpenAIClient(
            api_key=rag_config.OPENAI_API_KEY,
            model=rag_config.OPENAI_MODEL,
            temperature=rag_config.OPENAI_TEMPERATURE
        )
        logger.info("RAG 컴포넌트 로딩 완료!")
    except Exception as e:
        logger.error(f"RAG 컴포넌트 로딩 실패: {e}")
        raise HTTPException(status_code=500, detail=f"RAG 컴포넌트 로딩 실패: {str(e)}")


def run_rag_analysis(topology_data: Dict[str, Any]) -> FloorPlanAnalysis:
    """topology 데이터로 RAG LLM 분석 실행"""
    load_rag_components()

    # 쿼리 생성 및 임베딩
    stats = topology_data.get('statistics', {})
    query_text = f"{stats.get('structure_type', '혼합형')} 건축물 {stats.get('bay_count', 0)}Bay 침실 {stats.get('room_count', 0)}개"
    query_embedding = embedding_manager.embed_text(query_text)

    # RAG 검색
    rag_results = vector_store.search_evaluation(
        query_embedding=query_embedding,
        k=rag_config.TOP_K
    )

    # 컨텍스트 포맷
    context_parts = [f"[참고 {i}]\n{result['document']}\n" for i, result in enumerate(rag_results, 1)]
    rag_context = "\n".join(context_parts)

    # LLM 분석 생성
    prompt = build_analysis_prompt(topology_data, rag_context)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

    analysis_result = llm_client.query(
        messages=messages,
        response_model=FloorPlanAnalysis
    )

    return analysis_result


def extract_metrics_from_analysis(analysis: FloorPlanAnalysis) -> Dict[str, Any]:
    """FloorPlanAnalysis에서 13개 지표 추출"""
    # 거실 면적 비율 계산
    living_room = next((s for s in analysis.spaces if '거실' in s.space_name), None)
    living_room_ratio = living_room.area_ratio if living_room and living_room.area_ratio else 0.0

    # 주방 면적 비율 계산
    kitchen = next((s for s in analysis.spaces if '주방' in s.space_name), None)
    kitchen_ratio = kitchen.area_ratio if kitchen and kitchen.area_ratio else 0.0

    # 화장실 면적 비율 계산
    bathrooms = [s for s in analysis.spaces if '욕실' in s.space_name or '화장실' in s.space_name]
    bathroom_ratio = sum(s.area_ratio for s in bathrooms if s.area_ratio) if bathrooms else 0.0

    # 기타공간/특화공간 유무 확인
    space_types = set([s.space_type for s in analysis.spaces])
    has_etc_space = "기타공간" in space_types
    has_special_space = "특화공간" in space_types

    # 적합성 등급
    compliance_grade = analysis.compliance.overall_grade if analysis.compliance else "미평가"

    return {
        "windowless_ratio": round(analysis.windowless_ratio / 100.0, 4) if analysis.windowless_ratio > 1 else round(analysis.windowless_ratio, 4),
        "has_special_space": has_special_space,
        "bay_count": analysis.bay_count,
        "balcony_ratio": round(analysis.balcony_ratio / 100.0, 4) if analysis.balcony_ratio > 1 else round(analysis.balcony_ratio, 4),
        "living_room_ratio": round(living_room_ratio, 4),
        "bathroom_ratio": round(bathroom_ratio, 4),
        "kitchen_ratio": round(kitchen_ratio, 4),
        "room_count": analysis.room_count,
        "compliance_grade": compliance_grade,
        "ventilation_quality": analysis.ventilation_quality,
        "has_etc_space": has_etc_space,
        "structure_type": analysis.structure_type,
        "bathroom_count": analysis.bathroom_count
    }


def generate_embedding(text: str) -> list[float]:
    """document 텍스트로부터 임베딩 벡터 생성"""
    load_rag_components()

    try:
        embedding = embedding_manager.embed_text(text[:8000])
        return embedding
    except Exception as e:
        logger.error(f"임베딩 생성 실패: {e}")
        return [0.0] * 1536


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
    
    pipeline = load_cv_pipeline()

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

        # 2. 임시 파일로 저장
        logger.info("Step 2: 임시 파일 저장...")
        temp_dir = Path("./temp_input")
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / file.filename
        cv2.imwrite(str(temp_path), image)
        logger.info(f"임시 파일 저장 완료: {temp_path}")

        # 3. CV 파이프라인 실행
        logger.info("Step 3: CV 추론 시작...")
        results = pipeline.run(
            temp_path,
            save_json=True,
            save_visualization=True
        )
        logger.info("CV 추론 완료!")

        # 4. topology_graph.json 추출
        logger.info("Step 4: topology_graph 추출...")
        topology_data = results.get("topology_graph", {})
        logger.info(f"Topology 데이터 크기: {len(str(topology_data))} chars")

        # 5. topology 이미지 Base64 인코딩
        logger.info("Step 5: topology 이미지 인코딩...")
        # visualizer가 저장하는 경로: {OUTPUT_PATH}/{file_stem}/topology_result.png
        topology_image_path = pipeline.config.OUTPUT_PATH / temp_path.stem / "topology_result.png"
        logger.info(f"Topology 이미지 경로: {topology_image_path}")
        if topology_image_path.exists():
            topology_image = cv2.imread(str(topology_image_path))
            topology_image_base64 = f"data:image/png;base64,{image_to_base64(topology_image)}"
            logger.info(f"Topology 이미지 인코딩 성공! (크기: {len(topology_image_base64)} chars)")
        else:
            logger.warning(f"Topology 이미지 파일을 찾을 수 없습니다: {topology_image_path}")
            topology_image_base64 = ""

        # 6. RAG LLM 분석 실행
        logger.info("RAG LLM 분석 시작...")
        llm_analysis = run_rag_analysis(topology_data)

        # 7. 13개 지표 추출
        metrics = extract_metrics_from_analysis(llm_analysis)

        # 8. to_natural_language()로 document 생성
        document = llm_analysis.to_natural_language()

        # 9. 임베딩 생성
        embedding = generate_embedding(document)

        # 10. 응답 생성 (Spring Boot 형식에 맞춤)
        response = AnalyzeResponse(
            topology_json=json.dumps(topology_data, ensure_ascii=False),  # 1번
            topology_image_url=topology_image_base64,  # 2번
            assessment_json=json.dumps(topology_data, ensure_ascii=False),  # 3번
            **metrics,  # 13개 지표
            analysis_description=document,
            embedding=embedding
        )

        # 11. analysis_result.json 저장
        logger.info("Step 11: analysis_result.json 저장 시작...")
        try:
            output_dir = pipeline.config.OUTPUT_PATH / temp_path.stem
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

        # 12. 임시 파일 정리
        logger.info("Step 12: 임시 파일 정리...")
        temp_path.unlink(missing_ok=True)

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
    try:
        # 1. assessmentJson 파싱
        topology_data = json.loads(request.assessment_json)
        
        # 2. RAG LLM 분석 실행
        logger.info("RAG LLM 분석 시작...")
        llm_analysis = run_rag_analysis(topology_data)
        
        # 3. 13개 지표 추출
        metrics = extract_metrics_from_analysis(llm_analysis)
        
        # 4. document 생성
        document = llm_analysis.to_natural_language()
        
        # 5. 임베딩 생성
        logger.info("임베딩 생성 중...")
        embedding_vector = generate_embedding(document)
        
        # 6. 응답 생성 (Spring Boot 형식)
        logger.info("메타데이터 생성 완료!")
        
        return SaveResponse(
            document_id=f"floorplan_{hash(document) % 1000000}",
            metadata=metrics,
            document=document,
            embedding=embedding_vector  # 전체 벡터 전송
        )

    except Exception as e:
        logger.error(f"메타데이터 생성 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"메타데이터 생성 실패: {str(e)}")


@app.get("/health")
def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "cv_pipeline_loaded": cv_pipeline is not None,
        "rag_loaded": llm_client is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
