# FastAPI 서버 실행 가이드

## 1. 의존성 설치

```bash
pip install -r requirements.txt
```

## 2. 환경 변수 설정

`.env` 파일을 생성하거나 환경 변수로 설정:

```
OPENAI_API_KEY=your_openai_api_key_here
```

## 3. 서버 실행

### 방법 1: Python으로 직접 실행
```bash
python api_server.py
```

### 방법 2: Uvicorn으로 실행 (권장)
```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

- `--reload`: 코드 변경 시 자동 재시작 (개발 환경용)
- `--host 0.0.0.0`: 모든 네트워크 인터페이스에서 접근 가능
- `--port 8000`: 포트 번호 (Spring Boot는 8080 사용)

## 4. API 테스트

### 헬스 체크
```bash
curl http://localhost:8000/health
```

### 도면 분석
```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@test_image.png"
```

## 5. API 문서 확인

서버 실행 후 브라우저에서:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 6. Spring Boot 연동 확인

Spring Boot 서버(8080 포트)를 실행한 후:
1. 프론트엔드에서 이미지 업로드
2. Spring Boot가 Python 서버(8000 포트)로 요청 전달
3. Python에서 분석 후 결과 반환
4. Spring Boot가 프론트로 결과 전달

## 7. 주의사항

- CV 모델 파일들이 올바른 경로에 있어야 함 (`CV/cv_inference/` 폴더)
- GPU 사용을 위해 PyTorch CUDA 버전 필요 (선택사항)
- 첫 실행 시 모델 로딩에 시간이 걸릴 수 있음
