# 🏗️ 건축 평면도 분석 시스템 - 통합 가이드

## 📋 시스템 아키텍처

```
[프론트엔드 (React)] 
    ↓ (이미지 업로드)
[Spring Boot (8080)]
    ↓ (이미지 전달)
[Python FastAPI (8000)]
    ↓ (CV 분석)
[분석 결과 반환]
    ↓
[Spring Boot → 프론트]
    ↓ (사용자 확인)
[프론트 → Spring Boot]
    ↓ (저장 요청)
[PostgreSQL DB 저장]
```

---

## 🚀 1단계: Python FastAPI 서버 설정

### 1.1 의존성 설치

```bash
cd python
pip install -r requirements.txt
```

### 1.2 환경 변수 설정

`.env` 파일 생성:
```env
OPENAI_API_KEY=your_openai_api_key_here
```

### 1.3 서버 실행

**Windows:**
```bash
start_server.bat
```

**Linux/Mac:**
```bash
chmod +x start_server.sh
./start_server.sh
```

**직접 실행:**
```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

### 1.4 서버 확인

- **헬스 체크**: http://localhost:8000/health
- **API 문서**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🔧 2단계: Spring Boot 서버 설정

### 2.1 application.properties 확인

`Backend/src/main/resources/application.properties`:
```properties
# Python CV Server
python.server.url=http://localhost:8000
```

### 2.2 PostgreSQL 설정 확인

```properties
spring.datasource.url=jdbc:postgresql://localhost:5432/arae
spring.datasource.username=postgres
spring.datasource.password=1234
```

### 2.3 Spring Boot 실행

```bash
cd Backend
mvn spring-boot:run
```

또는 IDE에서 `Skn20Application` 실행

---

## 📡 3단계: API 플로우

### 3.1 분석 단계 (DB 저장 없음)

**프론트엔드 → Spring Boot**
```javascript
POST http://localhost:8080/api/floorplan/analyze
Content-Type: multipart/form-data

file: [이미지 파일]
```

**Spring Boot → Python**
```javascript
POST http://localhost:8000/analyze
Content-Type: multipart/form-data

file: [이미지 파일]
```

**Python 응답**
```json
{
  "topology_json": "{...}",
  "topology_image_url": "data:image/png;base64,...",
  "windowless_ratio": 0.15,
  "has_special_space": true,
  "bay_count": 2,
  "balcony_ratio": 0.08,
  "living_room_ratio": 0.25,
  "bathroom_ratio": 0.12,
  "kitchen_ratio": 0.10,
  "room_count": 3,
  "compliance_grade": "우수",
  "ventilation_quality": "양호",
  "has_etc_space": false,
  "structure_type": "일반형",
  "bathroom_count": 2,
  "embedding": [0.123, 0.456, ...]
}
```

### 3.2 저장 단계 (DB 저장)

사용자가 분석 결과 확인 후 "저장" 버튼 클릭:

**프론트엔드 → Spring Boot**
```javascript
POST http://localhost:8080/api/floorplan/save
Content-Type: application/json
Authorization: Bearer [JWT 토큰]

{
  "name": "우리집 평면도",
  "imageUrl": "https://...",
  "topologyJson": "{...}",
  "topologyImageUrl": "data:image/png;base64,...",
  "windowlessRatio": 0.15,
  "hasSpecialSpace": true,
  "bayCount": 2,
  "balconyRatio": 0.08,
  "livingRoomRatio": 0.25,
  "bathroomRatio": 0.12,
  "kitchenRatio": 0.10,
  "roomCount": 3,
  "complianceGrade": "우수",
  "ventilationQuality": "양호",
  "hasEtcSpace": false,
  "structureType": "일반형",
  "bathroomCount": 2,
  "embedding": [0.123, 0.456, ...]
}
```

**Spring Boot 응답**
```json
{
  "floorplanId": 123,
  "analysisId": 456,
  "name": "우리집 평면도",
  "createdAt": "2026-02-02",
  "message": "도면 분석 결과가 성공적으로 저장되었습니다."
}
```

---

## 🗄️ 4단계: 데이터베이스 구조

### Floorplan 테이블
```sql
CREATE TABLE floorplan (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    created_at DATE NOT NULL,
    name VARCHAR(255),
    image_url VARCHAR(500),
    topology_json TEXT,
    topology_image_url VARCHAR(500)
);
```

### Floorplan_Analysis 테이블
```sql
CREATE TABLE floorplan_analysis (
    id BIGSERIAL PRIMARY KEY,
    floorplan_id BIGINT NOT NULL UNIQUE REFERENCES floorplan(id),
    windowless_ratio DOUBLE PRECISION,
    has_special_space BOOLEAN,
    bay_count INTEGER,
    balcony_ratio DOUBLE PRECISION,
    living_room_ratio DOUBLE PRECISION,
    bathroom_ratio DOUBLE PRECISION,
    kitchen_ratio DOUBLE PRECISION,
    room_count INTEGER,
    compliance_grade VARCHAR(50),
    ventilation_quality VARCHAR(50),
    has_etc_space BOOLEAN,
    structure_type VARCHAR(50),
    bathroom_count INTEGER,
    embedding vector(1536)  -- pgvector 확장 필요
);
```

---

## 🧪 테스트 방법

### 1. Python 서버 단독 테스트

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@test_image.png"
```

### 2. Spring Boot 연동 테스트

**Postman 또는 curl:**
```bash
# 분석
curl -X POST http://localhost:8080/api/floorplan/analyze \
  -F "file=@test_image.png"

# 저장 (JWT 토큰 필요)
curl -X POST http://localhost:8080/api/floorplan/save \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "테스트 평면도",
    "imageUrl": "https://...",
    ...
  }'
```

---

## 🔍 트러블슈팅

### Python 서버가 시작되지 않는 경우

1. **CV 모델 파일 확인**
   ```bash
   ls CV/cv_inference/
   ```

2. **의존성 재설치**
   ```bash
   pip install -r requirements.txt --force-reinstall
   ```

3. **포트 충돌 확인**
   ```bash
   # Windows
   netstat -ano | findstr :8000
   
   # Linux/Mac
   lsof -i :8000
   ```

### Spring Boot 연결 실패

1. **Python 서버 상태 확인**
   ```bash
   curl http://localhost:8000/health
   ```

2. **application.properties 확인**
   ```properties
   python.server.url=http://localhost:8000
   ```

3. **방화벽/네트워크 확인**

### DB 저장 실패

1. **PostgreSQL 실행 확인**
   ```bash
   psql -U postgres -d arae
   ```

2. **pgvector 확장 설치**
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

---

## 📚 추가 리소스

- FastAPI 공식 문서: https://fastapi.tiangolo.com/
- Spring Boot 문서: https://spring.io/projects/spring-boot
- pgvector 문서: https://github.com/pgvector/pgvector

---

## ✅ 체크리스트

- [ ] Python 의존성 설치 완료
- [ ] OpenAI API 키 설정 완료
- [ ] Python 서버 실행 확인 (http://localhost:8000/health)
- [ ] Spring Boot 서버 실행 확인
- [ ] PostgreSQL 실행 및 pgvector 확장 설치 확인
- [ ] 테스트 이미지로 분석 API 테스트 완료
- [ ] 저장 API 테스트 완료
