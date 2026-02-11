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
from api_models.schemas import AnalyzeResponse, SaveRequest, SaveResponse, ChatRequest, ChatResponse
from services.cv_service import cv_service
from services.rag_service import rag_service
from services.embedding_service import embedding_service
from services.chatbot_service_v2 import chatbot_service
from services.law_verification import ArchitectureLawValidator, QuestionContext, VerificationStatus
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

        # 6. 응답 생성 (Spring Boot 형식에 맞춤)
        logger.info("Step 6: 응답 생성...")
        llm_analysis_dict = llm_analysis.model_dump() if hasattr(llm_analysis, 'model_dump') else llm_analysis.dict()
        response = AnalyzeResponse(
            topology_json=json.dumps(topology_data, ensure_ascii=False),  # 1번: topology_graph.json
            topology_image_url=topology_image_base64,  # 2번: topology 시각화 이미지
            llm_analysis_json=json.dumps(llm_analysis_dict, ensure_ascii=False)  # 3번: llm_analysis.json
        )

        # 7. llm_analysis.json 저장
        logger.info("Step 7: llm_analysis.json 저장...")
        try:
            output_dir = cv_service.pipeline.config.OUTPUT_PATH / Path(file.filename).stem
            output_dir.mkdir(parents=True, exist_ok=True)

            llm_analysis_path = output_dir / "llm_analysis.json"
            with open(llm_analysis_path, "w", encoding="utf-8") as f:
                json.dump(llm_analysis_dict, f, ensure_ascii=False, indent=2)

            logger.info(f"✓ llm_analysis.json 저장 완료! ({llm_analysis_path.stat().st_size} bytes)")

        except Exception as save_error:
            logger.error(f"✗ llm_analysis.json 저장 실패: {save_error}")
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
    메타데이터 생성 엔드포인트

    Input: llm_analysis_json (FloorPlanAnalysis JSON 문자열)
    Output: metadata + document + embedding
    """
    logger.info("=" * 80)
    logger.info("=== /generate-metadata 엔드포인트 호출됨 ===")
    logger.info("=" * 80)

    try:
        # 1. llm_analysis_json 파싱 → FloorPlanAnalysis 객체로 변환
        logger.info("Step 1: llm_analysis_json 파싱...")
        from CV.rag_system.schemas import FloorPlanAnalysis
        llm_analysis_dict = json.loads(request.llm_analysis_json)
        llm_analysis = FloorPlanAnalysis(**llm_analysis_dict)
        logger.info("FloorPlanAnalysis 파싱 완료!")

        # 2. 13개 지표 추출
        logger.info("Step 2: 메트릭 추출...")
        metrics = rag_service.extract_metrics(llm_analysis)

        # 3. document 생성 (to_natural_language)
        logger.info("Step 3: Document 생성...")
        document = llm_analysis.to_natural_language()

        # 4. 임베딩 생성
        logger.info("Step 4: 임베딩 생성 중...")
        embedding_vector = embedding_service.generate_embedding(document)

        # 5. 응답 생성 (Spring Boot로 반환)
        logger.info("Step 5: 응답 생성...")
        response = SaveResponse(
            document_id=f"floorplan_{hash(document) % 1000000}",
            metadata=metrics,
            document=document,
            embedding=embedding_vector
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


@app.post("/ask", response_model=ChatResponse)
async def ask_chatbot(request: ChatRequest):
    """
    챗봇 질의응답 엔드포인트 (검증 에이전트 통합)
    
    Input: email, question
    Output: summaryTitle, answer (검증 완료된 답변)
    
    Flow:
    1. 챗봇이 답변 생성
    2. 법/조례 검증 에이전트로 검증
    3. PASS: 그대로 반환
    4. RETRY/FAIL: 피드백과 함께 재생성 (최대 3회)
    """
    logger.info("=" * 80)
    logger.info("=== /ask 엔드포인트 호출됨 ===")
    logger.info(f"Email: {request.email}")
    logger.info(f"Question: {request.question}")
    logger.info("=" * 80)
    
    try:
        # 검증 에이전트 초기화
        validator = ArchitectureLawValidator()
        
        max_attempts = 3
        final_result = None
        
        for attempt in range(1, max_attempts + 1):
            logger.info(f"\n[Attempt {attempt}/{max_attempts}] 답변 생성 중...")
            
            # 챗봇 서비스로 질문 처리
            if attempt == 1:
                # 첫 시도: 원래 질문으로 답변 생성
                result = chatbot_service.ask(
                    email=request.email,
                    question=request.question
                )
            else:
                # 재시도: 검증 피드백을 포함한 질문 생성
                feedback_question = (
                    f"{request.question}\n\n"
                    f"[이전 답변 검증 결과]\n"
                    f"- 상태: {final_result.status}\n"
                    f"- 점수: {final_result.score}/100\n"
                    f"- 문제점: {', '.join(final_result.issues)}\n"
                    f"- 권장사항: {final_result.recommendation}\n\n"
                    f"위 검증 결과를 반영하여 정확한 답변을 생성해주세요."
                )
                logger.info(f"[Retry] 피드백 포함 질문:\n{feedback_question[:200]}...")
                
                result = chatbot_service.ask(
                    email=request.email,
                    question=feedback_question
                )
            
            answer = result["answer"]
            summary_title = result["summaryTitle"]
            
            logger.info(f"[Attempt {attempt}] 답변 생성 완료 (길이: {len(answer)}자)")
            
            # 법/조례 검증 실행
            logger.info(f"[Attempt {attempt}] 검증 시작...")
            
            # QuestionContext는 주소, 용도지역 등의 세부 정보를 담는 용도
            # 현재는 검증에 필요한 정보가 답변에서 추출되므로 빈 컨텍스트 전달
            question_context = QuestionContext()
            
            verification_result = validator.verify(
                llm_answer=answer,
                question=request.question,
                question_context=question_context
            )
            
            final_result = verification_result
            
            logger.info(f"[Attempt {attempt}] 검증 완료:")
            logger.info(f"  - 상태: {verification_result.status}")
            logger.info(f"  - 점수: {verification_result.score}/100")
            
            # details에서 세부 점수 추출 (있는 경우)
            if 'hard_rule' in verification_result.details:
                logger.info(f"  - Hard Rule: {verification_result.details.get('hard_rule', {}).get('passed', 'N/A')}")
            if 'semantic_consistency' in verification_result.details:
                semantic_score = verification_result.details['semantic_consistency'].get('score', 'N/A')
                logger.info(f"  - Semantic: {semantic_score}/100" if isinstance(semantic_score, (int, float)) else f"  - Semantic: {semantic_score}")
            
            if verification_result.issues:
                logger.warning(f"  - 문제점: {', '.join(verification_result.issues)}")
            
            if verification_result.warnings:
                logger.info(f"  - 경고: {', '.join(verification_result.warnings)}")
            
            # 검증 결과에 따른 처리
            if verification_result.status == VerificationStatus.PASS:
                logger.info(f"✅ [Attempt {attempt}] 검증 통과! 답변 반환")
                response = ChatResponse(
                    summaryTitle=summary_title,
                    answer=answer
                )
                
                logger.info("=" * 80)
                logger.info("=== 챗봇 응답 완료 (검증 통과) ===")
                logger.info("=" * 80)
                
                return response
            
            elif verification_result.status == VerificationStatus.RETRY:
                logger.warning(f"⚠️ [Attempt {attempt}] 재시도 필요 (점수: {verification_result.score})")
                if attempt == max_attempts:
                    logger.warning(f"⚠️ 최대 재시도 횟수 도달. 마지막 답변 반환")
                else:
                    logger.info(f"   → 피드백 반영하여 재생성 시도...")
                    continue
            
            else:  # FAIL
                logger.error(f"❌ [Attempt {attempt}] 검증 실패 (점수: {verification_result.score})")
                if attempt == max_attempts:
                    logger.error(f"❌ 최대 재시도 횟수 도달. 마지막 답변 반환")
                else:
                    logger.info(f"   → 피드백 반영하여 재생성 시도...")
                    continue
        
        # 최대 재시도 후에도 PASS 못한 경우: 마지막 답변 반환 (경고 포함)
        logger.warning(f"⚠️ {max_attempts}회 시도 후에도 검증 통과 실패. 마지막 답변 반환 (상태: {final_result.status})")
        
        # 경고 메시지를 답변에 추가
        warning_message = (
            "\n\n⚠️ **검증 안내**\n"
            f"이 답변은 자동 검증에서 완전히 통과하지 못했습니다 (점수: {final_result.score}/100).\n"
            "실제 적용 전에 관할 구청 건축과에 확인하시기 바랍니다."
        )
        
        final_answer = answer + warning_message
        
        response = ChatResponse(
            summaryTitle=summary_title,
            answer=final_answer
        )
        
        logger.info("=" * 80)
        logger.info("=== 챗봇 응답 완료 (검증 미통과, 경고 포함) ===")
        logger.info("=" * 80)
        
        return response
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"!!! 챗봇 응답 생성 중 오류 !!!")
        logger.error(f"에러 타입: {type(e).__name__}")
        logger.error(f"에러 메시지: {str(e)}")
        logger.error("=" * 80)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"챗봇 오류: {str(e)}")


@app.get("/health")
def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "cv_pipeline_loaded": cv_service.is_loaded(),
        "rag_loaded": rag_service.is_loaded(),
        "embedding_loaded": embedding_service.is_loaded(),
        "chatbot_loaded": chatbot_service.is_loaded()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)