# =============================================
# RunPod CV Worker - Dockerfile
# =============================================
FROM pytorch/pytorch:2.4.1-cuda12.4-cudnn9-runtime

WORKDIR /app

# 시스템 패키지 (OpenCV 의존성)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Qwen3-Embedding + CrossEncoder 사전 다운로드 (빌드 시 포함 -> 콜드스타트 단축)
RUN python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
print('Downloading Qwen3-Embedding-0.6B...'); \
SentenceTransformer('Qwen/Qwen3-Embedding-0.6B'); \
print('Downloading CrossEncoder...'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2'); \
print('Done!')"

# CV 코드 복사 (추론에 필요한 것만)
COPY CV/ ./CV/

# 핸들러 복사
COPY handler.py .

# 실행
CMD ["python", "handler.py"]
