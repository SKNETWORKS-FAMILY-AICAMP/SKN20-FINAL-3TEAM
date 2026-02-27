"""
RunPod Serverless API 클라이언트
CV 추론, 임베딩, 리랭킹을 RunPod GPU에서 실행
"""

import os
import time
import logging
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("RunPodClient")

RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY", "")
RUNPOD_ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID", "")
RUNPOD_BASE_URL = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}"

# 타임아웃 설정
CV_TIMEOUT = 300      # CV 추론: 최대 5분 (콜드스타트 포함)
EMBED_TIMEOUT = 120   # 임베딩: 최대 2분
RERANK_TIMEOUT = 120  # 리랭킹: 최대 2분


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }


async def call_runpod_async(action: str, payload: dict, timeout: int = 120) -> dict:
    """
    RunPod Serverless 비동기 호출 (runsync)

    Args:
        action: 핸들러 액션 (cv_inference, embed, embed_batch, rerank)
        payload: 액션별 입력 데이터
        timeout: 타임아웃 (초)

    Returns:
        RunPod 핸들러 반환값
    """
    url = f"{RUNPOD_BASE_URL}/runsync"
    body = {"input": {"action": action, **payload}}

    start = time.time()
    logger.info(f"[RunPod] 요청: action={action}, timeout={timeout}s")

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=_headers(), json=body)
        resp.raise_for_status()
        result = resp.json()

    elapsed = time.time() - start
    status = result.get("status", "UNKNOWN")
    logger.info(f"[RunPod] 응답: status={status}, {elapsed:.2f}s")

    if status == "COMPLETED":
        return result.get("output", {})
    elif status == "FAILED":
        error = result.get("error", "Unknown error")
        raise RuntimeError(f"RunPod 작업 실패: {error}")
    else:
        raise RuntimeError(f"RunPod 예상치 못한 상태: {status}, result={result}")


def call_runpod_sync(action: str, payload: dict, timeout: int = 120) -> dict:
    """
    RunPod Serverless 동기 호출 (runsync)
    비동기 환경이 아닌 곳에서 사용
    """
    url = f"{RUNPOD_BASE_URL}/runsync"
    body = {"input": {"action": action, **payload}}

    start = time.time()
    logger.info(f"[RunPod] 동기 요청: action={action}, timeout={timeout}s")

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=_headers(), json=body)
        resp.raise_for_status()
        result = resp.json()

    elapsed = time.time() - start
    status = result.get("status", "UNKNOWN")
    logger.info(f"[RunPod] 동기 응답: status={status}, {elapsed:.2f}s")

    if status == "COMPLETED":
        return result.get("output", {})
    elif status == "FAILED":
        error = result.get("error", "Unknown error")
        raise RuntimeError(f"RunPod 작업 실패: {error}")
    else:
        raise RuntimeError(f"RunPod 예상치 못한 상태: {status}, result={result}")


# ── 편의 함수 ──

async def cv_inference_async(image_base64: str, filename: str = "input.png") -> dict:
    """CV 추론 (비동기)"""
    return await call_runpod_async(
        "cv_inference",
        {"image": image_base64, "filename": filename},
        timeout=CV_TIMEOUT,
    )


async def embed_text_async(text: str) -> list[float]:
    """단일 텍스트 임베딩 (비동기)"""
    result = await call_runpod_async(
        "embed",
        {"text": text},
        timeout=EMBED_TIMEOUT,
    )
    return result.get("embedding", [])


async def embed_batch_async(texts: list[str]) -> list[list[float]]:
    """배치 텍스트 임베딩 (비동기)"""
    result = await call_runpod_async(
        "embed_batch",
        {"texts": texts},
        timeout=EMBED_TIMEOUT,
    )
    return result.get("embeddings", [])


async def rerank_async(query: str, documents: list[str]) -> list[float]:
    """Cross-encoder 리랭킹 (비동기)"""
    result = await call_runpod_async(
        "rerank",
        {"query": query, "documents": documents},
        timeout=RERANK_TIMEOUT,
    )
    return result.get("scores", [])


def embed_text_sync(text: str) -> list[float]:
    """단일 텍스트 임베딩 (동기)"""
    result = call_runpod_sync(
        "embed",
        {"text": text},
        timeout=EMBED_TIMEOUT,
    )
    return result.get("embedding", [])


def rerank_sync(query: str, documents: list[str]) -> list[float]:
    """Cross-encoder 리랭킹 (동기)"""
    result = call_runpod_sync(
        "rerank",
        {"query": query, "documents": documents},
        timeout=RERANK_TIMEOUT,
    )
    return result.get("scores", [])
