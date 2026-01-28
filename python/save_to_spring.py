import requests
import json
from pydantic import BaseModel
from typing import List

class DrawingAnalysisResult(BaseModel):
    projectName: str
    rawJson: dict           # CV가 뽑은 도면 데이터
    summaryText: str        # sLLM 1이 요약한 내용
    summaryEmbedding: List[float]  # 벡터 값 (1536차원 등)

def send_to_spring_boot(analysis_data: DrawingAnalysisResult):
    SPRING_BOOT_URL = "http://localhost:8080/api/drawings"
    
    # Pydantic 모델을 JSON으로 변환
    payload = analysis_data.model_dump()
    
    try:
        response = requests.post(
            SPRING_BOOT_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            print("데이터 전송 성공!")
        else:
            print(f"전송 실패: {response.status_code}")
    except Exception as e:
        print(f"에러 발생: {e}")





# --- 파이썬 팀원의 작업 영역 ---

# 1. CV 모델이 도면에서 뽑아낸 실제 데이터 (예시)
real_cv_data = {
    "dimensions": {"width": 1200, "height": 800},
    "rooms": [
        {"type": "living_room", "area": 25.5},
        {"type": "bedroom", "area": 12.0}
    ],
    "elements": ["wall", "door", "window"]
}

# 2. sLLM 1이 생성한 실제 요약 텍스트
real_summary = "이 도면은 거실 1개와 침실 1개로 구성된 25.5평형 주거 공간입니다."

# 3. 임베딩 모델이 생성한 1536차원 숫자 리스트
real_vector = [0.0123, -0.0456, 0.7890, ...] 

# ★ 여기서 넣는 겁니다! ★
send_to_spring_boot(
    projectName="한남동_A단지_301호", # 프로젝트 이름
    rawJson=real_cv_data,           # 분석한 JSON 데이터
    summaryText=real_summary,            # 요약 텍스트
    summaryEmbedding=real_vector            # 벡터 데이터
)