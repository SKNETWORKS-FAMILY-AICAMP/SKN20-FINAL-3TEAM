"""
RunPod Serverless Handler
- CV 추론 (YOLOv5 + DeepLabV3+)
- Qwen3-Embedding-0.6B 임베딩
- CrossEncoder 리랭킹
"""

import runpod
import base64
import json
import logging
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format='[%(asctime)s][%(levelname)s] %(message)s')
logger = logging.getLogger("RunPodHandler")

# ================================================================
# 글로벌 모델 (콜드 스타트 시 1회 로딩)
# ================================================================

cv_pipeline = None
embed_model = None
reranker_model = None


def load_cv_pipeline():
    """CV 파이프라인 로드"""
    global cv_pipeline
    if cv_pipeline is not None and cv_pipeline._models_loaded:
        return cv_pipeline

    from CV.cv_inference.pipeline import InferencePipeline
    from CV.cv_inference.config import InferenceConfig

    logger.info("CV 파이프라인 로딩 시작...")
    config = InferenceConfig()
    config.OUTPUT_PATH = Path("/tmp/cv_output")
    config.OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    pipeline = InferencePipeline(config)
    pipeline.load_models()
    cv_pipeline = pipeline
    logger.info("CV 파이프라인 로딩 완료!")
    return cv_pipeline


def load_embed_model():
    """Qwen3-Embedding-0.6B 로드"""
    global embed_model
    if embed_model is not None:
        return embed_model

    from sentence_transformers import SentenceTransformer

    logger.info("Qwen3 임베딩 모델 로딩 시작...")
    embed_model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")
    logger.info("Qwen3 임베딩 모델 로딩 완료!")
    return embed_model


def load_reranker():
    """CrossEncoder 리랭커 로드"""
    global reranker_model
    if reranker_model is not None:
        return reranker_model

    from sentence_transformers import CrossEncoder

    logger.info("CrossEncoder 리랭커 로딩 시작...")
    reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    logger.info("CrossEncoder 리랭커 로딩 완료!")
    return reranker_model


# ================================================================
# 액션 핸들러
# ================================================================

def handle_cv_inference(input_data: dict) -> dict:
    """
    도면 이미지 CV 추론

    input: {"image": "<base64 encoded image>", "filename": "test.png"}
    output: {"topology_json": {...}, "topology_image": "<base64>"}
    """
    pipeline = load_cv_pipeline()

    image_b64 = input_data["image"]
    filename = input_data.get("filename", "input.png")

    # base64 -> numpy array
    image_bytes = base64.b64decode(image_b64)
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        return {"error": "이미지 디코딩 실패"}

    # 임시 파일로 저장 (pipeline.run이 파일 경로를 요구)
    temp_dir = Path("/tmp/cv_input")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / filename
    cv2.imwrite(str(temp_path), image)

    try:
        # CV 파이프라인 실행
        start = time.time()
        results = pipeline.run(temp_path, save_json=True, save_visualization=True)
        elapsed = time.time() - start
        logger.info(f"CV 추론 완료: {elapsed:.2f}s")

        # topology 이미지 base64 인코딩
        topo_image_path = pipeline.config.OUTPUT_PATH / Path(filename).stem / "topology_result.png"
        topo_b64 = None
        if topo_image_path.exists():
            with open(topo_image_path, "rb") as f:
                topo_b64 = base64.b64encode(f.read()).decode("utf-8")

        return {
            "topology_json": results.get("topology_graph", {}),
            "low_result": results.get("low_result", {}),
            "source_result": results.get("source_result", {}),
            "topology_image_base64": topo_b64,
            "inference_time_sec": round(elapsed, 2),
        }
    finally:
        # 임시 파일 정리
        temp_path.unlink(missing_ok=True)
        # 출력 디렉토리 정리
        output_dir = pipeline.config.OUTPUT_PATH / Path(filename).stem
        if output_dir.exists():
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)


def handle_embed(input_data: dict) -> dict:
    """
    텍스트 임베딩 생성

    input: {"text": "건축 도면 분석"}
    output: {"embedding": [0.1, 0.2, ...]}
    """
    model = load_embed_model()
    text = input_data["text"]

    # 텍스트 길이 제한 (Qwen3 max_seq_length 고려)
    truncated = text[:8000]
    embedding = model.encode(truncated, normalize_embeddings=True)
    return {"embedding": embedding.tolist()}


def handle_embed_batch(input_data: dict) -> dict:
    """
    배치 임베딩 생성

    input: {"texts": ["텍스트1", "텍스트2", ...]}
    output: {"embeddings": [[0.1, ...], [0.2, ...], ...]}
    """
    model = load_embed_model()
    texts = input_data["texts"]

    truncated = [t[:8000] for t in texts]
    embeddings = model.encode(truncated, normalize_embeddings=True)
    return {"embeddings": embeddings.tolist()}


def handle_rerank(input_data: dict) -> dict:
    """
    Cross-encoder 리랭킹

    input: {"query": "방 3개 아파트", "documents": ["문서1", "문서2", ...]}
    output: {"scores": [0.95, 0.82, ...]}
    """
    model = load_reranker()
    query = input_data["query"]
    documents = input_data["documents"]

    pairs = [(query, doc) for doc in documents]
    scores = model.predict(pairs)
    return {"scores": scores.tolist()}


# ================================================================
# RunPod 메인 핸들러
# ================================================================

def handler(event):
    """
    통합 핸들러 - action 파라미터로 분기

    지원 action:
    - cv_inference: 도면 CV 추론
    - embed: 단일 텍스트 임베딩
    - embed_batch: 배치 텍스트 임베딩
    - rerank: Cross-encoder 리랭킹
    """
    try:
        input_data = event["input"]
        action = input_data.get("action", "")

        logger.info(f"요청 수신: action={action}")

        if action == "cv_inference":
            return handle_cv_inference(input_data)
        elif action == "embed":
            return handle_embed(input_data)
        elif action == "embed_batch":
            return handle_embed_batch(input_data)
        elif action == "rerank":
            return handle_rerank(input_data)
        else:
            return {"error": f"알 수 없는 action: {action}"}

    except Exception as e:
        logger.error(f"핸들러 에러: {e}", exc_info=True)
        return {"error": str(e)}


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
