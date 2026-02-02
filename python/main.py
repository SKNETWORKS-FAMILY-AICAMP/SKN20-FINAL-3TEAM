"""
건축 평면도 분석 FastAPI 서버
Spring Boot와 연동하여 도면 이미지를 분석하고 결과를 반환
"""

import io
import os
import base64
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from openai import OpenAI
from pgvector.psycopg2 import register_vector

# CV 추론 파이프라인 import
from CV.cv_inference.pipeline import InferencePipeline
from CV.cv_inference.config import InferenceConfig

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

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY"))

# CV 파이프라인 전역 변수
cv_pipeline: Optional[InferencePipeline] = None


# ===== 응답 모델 정의 =====
class AnalysisResponse(BaseModel):
    """도면 분석 응답 모델"""
    # Topology 데이터
    topology_json: str  # topology_graph.json 전체를 문자열로
    topology_image_url: str  # Base64 인코딩된 토폴로지 이미지
    
    # 분석 지표 (13가지)
    windowless_ratio: float  # 무창실 비율
    has_special_space: bool  # 특수 공간 존재 여부
    bay_count: int  # 베이 개수
    balcony_ratio: float  # 발코니 비율
    living_room_ratio: float  # 거실 비율
    bathroom_ratio: float  # 욕실 비율
    kitchen_ratio: float  # 주방 비율
    room_count: int  # 방 개수
    compliance_grade: str  # 법적 준수 등급
    ventilation_quality: str  # 환기 품질
    has_etc_space: bool  # 기타 공간 존재 여부
    structure_type: str  # 구조 타입
    bathroom_count: int  # 욕실 개수
    
    # 분석 설명
    analysis_description: str  # 상세 분석 설명 텍스트
    
    # 임베딩 벡터
    embedding: list[float]  # 1536차원 벡터


class ChatRequest(BaseModel):
    """RAG 챗봇 요청 모델"""
    email: str
    question: str


# ===== 유틸리티 함수 =====
def image_to_base64(image: np.ndarray) -> str:
    """OpenCV 이미지를 Base64 문자열로 변환"""
    _, buffer = cv2.imencode('.png', image)
    return base64.b64encode(buffer).decode('utf-8')


def generate_analysis_description(topology_data: Dict[str, Any], metrics: Dict[str, Any]) -> str:
    """
    topology 데이터와 지표를 기반으로 분석 설명 텍스트 생성
    """
    # metadata에서 document가 있으면 사용, 없으면 생성
    metadata = topology_data.get("metadata", {})
    if "document" in metadata:
        return metadata["document"]
    
    # document가 없으면 지표 기반으로 간단한 설명 생성
    description_parts = []
    
    # 구조 타입과 베이 정보
    description_parts.append(
        f"이 평면도는 {metrics['bay_count']}베이 {metrics['structure_type']} 구조입니다."
    )
    
    # 채광 및 환기
    if metrics['windowless_ratio'] < 0.2:
        description_parts.append("채광과 환기가 우수합니다.")
    elif metrics['windowless_ratio'] < 0.4:
        description_parts.append("채광과 환기가 보통 수준입니다.")
    else:
        description_parts.append("무창실 비율이 높아 채광과 환기 개선이 필요합니다.")
    
    # 법적 준수
    description_parts.append(f"법적 준수 등급: {metrics['compliance_grade']}")
    description_parts.append(f"환기 품질: {metrics['ventilation_quality']}")
    
    # 공간 구성
    space_info = f"방 {metrics['room_count']}개, 욕실 {metrics['bathroom_count']}개로 구성되어 있습니다."
    description_parts.append(space_info)
    
    # 특수 공간
    if metrics['has_special_space']:
        description_parts.append("특화공간이 포함되어 있습니다.")
    if metrics['has_etc_space']:
        description_parts.append("기타 활용 공간이 있습니다.")
    
    return " ".join(description_parts)


def calculate_metrics(topology_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    topology_graph.json 데이터로부터 13가지 분석 지표 계산
    실제 CV 파이프라인 출력 형식에 맞춰 처리
    """
    # metadata에서 직접 값을 추출 (CV 파이프라인이 이미 계산한 값)
    metadata = topology_data.get("metadata", {})
    
    # metadata에 이미 값이 있으면 그대로 사용, 없으면 기본값 또는 계산
    return {
        "windowless_ratio": round(metadata.get("windowless_ratio", 0.0) / 100.0, 4),  # 퍼센트를 0-1 범위로 변환
        "has_special_space": metadata.get("has_special_space", False),
        "bay_count": metadata.get("bay_count", 1),
        "balcony_ratio": round(metadata.get("balcony_ratio", 0.0) / 100.0 if metadata.get("balcony_ratio", 0.0) > 1 else metadata.get("balcony_ratio", 0.0), 4),
        "living_room_ratio": round(metadata.get("living_room_ratio", 0.0), 4),
        "bathroom_ratio": round(metadata.get("bathroom_ratio", 0.0), 4),
        "kitchen_ratio": round(metadata.get("kitchen_ratio", 0.0), 4),
        "room_count": metadata.get("room_count", 0),
        "compliance_grade": metadata.get("compliance_grade", "미분류"),
        "ventilation_quality": metadata.get("ventilation_quality", "미분류"),
        "has_etc_space": metadata.get("has_etc_space", False),
        "structure_type": metadata.get("structure_type", "일반형"),
        "bathroom_count": metadata.get("bathroom_count", 0)
    }


def generate_embedding(topology_json_str: str) -> list[float]:
    """
    topology.json 데이터로부터 임베딩 벡터 생성
    OpenAI embedding-3-small 모델 사용 (1536차원)
    """
    try:
        response = client.embeddings.create(
            input=topology_json_str[:8000],  # 토큰 제한 고려
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"임베딩 생성 실패: {e}")
        # 실패 시 0 벡터 반환
        return [0.0] * 1536


# ===== DB 연결 함수 =====
def get_db_conn():
    """PostgreSQL 연결 및 pgvector 등록"""
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        database="arae",
        user="postgres",
        password="1234"
    )
    register_vector(conn)  # 이거 안 하면 벡터 검색 시 에러 날 수 있음
    return conn


# ===== API 엔드포인트 =====

# 서버 시작 시 모델을 로드하지 않음 - 첫 요청 시 lazy loading
# @app.on_event("startup")
# async def startup_event():
#     """서버 시작 시 CV 모델 로드"""
#     global cv_pipeline
#     
#     logger.info("=" * 60)
#     logger.info("FastAPI 서버 시작 - CV 모델 로딩 중...")
#     logger.info("=" * 60)
#     
#     try:
#         config = InferenceConfig()
#         config.OUTPUT_PATH = Path("./temp_output")
#         config.OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
#         
#         cv_pipeline = InferencePipeline(config)
#         cv_pipeline.load_models()
#         
#         logger.info("CV 모델 로딩 완료!")
#     except Exception as e:
#         logger.error(f"CV 모델 로딩 실패: {e}")
#         raise


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
        # 현재 디렉토리 기준으로 경로 설정
        config.OUTPUT_PATH = Path("./temp_output")
        config.OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
        
        cv_pipeline = InferencePipeline(config)
        cv_pipeline.load_models()
        
        logger.info("CV 모델 로딩 완료!")
        return cv_pipeline
    except Exception as e:
        logger.error(f"CV 모델 로딩 실패: {e}")
        raise HTTPException(status_code=500, detail=f"CV 모델 로딩 실패: {str(e)}")


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_floorplan(file: UploadFile = File(...)):
    """
    도면 이미지 분석 엔드포인트
    
    Args:
        file: 업로드된 도면 이미지 파일
        
    Returns:
        AnalysisResponse: 분석 결과 (topology, 지표, 임베딩)
    """
    # lazy loading: 첫 요청 시에만 모델 로드
    pipeline = load_cv_pipeline()
    
    try:
        # 1. 이미지 파일 읽기
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다.")
        
        logger.info(f"이미지 수신: {file.filename}, 크기: {image.shape}")
        
        # 2. 임시 파일로 저장 (파이프라인이 Path를 요구하므로)
        temp_dir = Path("./temp_input")
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / file.filename
        cv2.imwrite(str(temp_path), image)
        
        # 3. CV 파이프라인 실행
        logger.info("CV 추론 시작...")
        results = pipeline.run(
            temp_path,
            save_json=True,
            save_visualization=True
        )
        
        # 4. topology_graph.json 추출
        topology_data = results.get("topology_graph", {})
        topology_json_str = json.dumps(topology_data, ensure_ascii=False)
        
        # 5. topology 이미지 Base64 인코딩
        topology_image_path = pipeline.config.OUTPUT_PATH / f"{temp_path.stem}_topology.png"
        if topology_image_path.exists():
            topology_image = cv2.imread(str(topology_image_path))
            topology_image_base64 = image_to_base64(topology_image)
        else:
            # 토폴로지 이미지가 없으면 빈 이미지 생성
            topology_image_base64 = ""
        
        # 6. 분석 지표 계산
        metrics = calculate_metrics(topology_data)
        
        # 7. 분석 설명 텍스트 생성
        analysis_description = generate_analysis_description(topology_data, metrics)
        
        # 8. 임베딩 생성
        embedding = generate_embedding(topology_json_str)
        
        # 9. 응답 생성
        response = AnalysisResponse(
            topology_json=topology_json_str,
            topology_image_url=f"data:image/png;base64,{topology_image_base64}",
            analysis_description=analysis_description,
            embedding=embedding,
            **metrics
        )
        
        # 9. 임시 파일 정리
        temp_path.unlink(missing_ok=True)
        
        logger.info("분석 완료!")
        return response
        
    except Exception as e:
        logger.error(f"분석 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"분석 실패: {str(e)}")


@app.post("/chatllm")  # 자바 서비스의 URL과 맞춤
def ask_rag(request: ChatRequest):
    """
    RAG 기반 챗봇 엔드포인트 (기존 코드 유지)
    """
    try:
        # 1. 질문 임베딩
        emb_res = client.embeddings.create(
            input=request.question,
            model="text-embedding-3-small"
        )
        q_embedding = emb_res.data[0].embedding

        # 2. 벡터 유사도 검색 (Legal + Internal 합쳐서 검색 예시)
        conn = get_db_conn()
        with conn.cursor() as cur:
            search_query = """
                SELECT content, region FROM legal_documents 
                ORDER BY embedding <=> %s::vector LIMIT 3
            """
            cur.execute(search_query, (q_embedding,))
            results = cur.fetchall()

        # 3. 컨텍스트 구성
        context = "\n".join([f"[{r[1]}] {r[0]}" for r in results])

        # 4. LLM 답변 및 요약 제목 생성
        llm_res = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"당신은 법률 전문가입니다. 다음 내용을 참고해서 답변하세요: {context}"},
                {"role": "user", "content": f"질문: {request.question}\n\n답변은 친절하게 해주고, 답변의 내용을 한 줄로 요약한 'summaryTitle'도 함께 만들어줘."}
            ]
        )
        
        full_text = llm_res.choices[0].message.content
        # 임시로 제목과 본문 분리 (실제로는 LLM에게 JSON 포맷으로 달라고 하면 더 정확함)
        return {
            "summaryTitle": request.question[:15] + "...",  # 임시 요약
            "answer": full_text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "cv_pipeline_loaded": cv_pipeline is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)