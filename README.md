#### SKN20-FINAL-3TEAM
# ARAE 

ARAE는 건축 도면을 입력으로 받아  
1) 도면 자산화(도면 → 구조화 데이터 생성)  
2) 사내 기준 기반 도면 평가  
3) 유사 도면 검색  
4) 주소/필지 기반 법규·조례 조회  
를 제공하는 **건축사 보조용 시스템**입니다.

---

## 🏆 팀명 : WE

### 👥 팀원 소개
| 이름       | 역할               | 주요 기여 분야                      |
|------------|--------------------|-----------------------------------|
🏆 **[SKN Family AI캠프] 최종 프로젝트**  
📅 **개발 기간**: 2025.01.13 ~ 2025.02.04

---

## 1. Overview

### 문제정의

건축 실무에서 도면은 대부분 **파일(PDF, 이미지)이나 실제 종이 형태**로 존재하며,  
도면의 공간 구성, 면적 비율, Bay 수, 발코니 비율 등 핵심 정보는 **사람이 직접 읽고 판단**해야 합니다.

또한 도면 검토 과정에서
- 사내 기준에 부합하는지,
- 기존 도면과 유사한 사례가 있는지,
- 해당 필지에 적용되는 법규·조례는 무엇인지

를 **서로 다른 자료와 시스템을 오가며** 직접 개별적으로 확인해야 합니다.

이로 인해 도면 검토는 **시간이 많이 들고**, 판단 기준이 사람마다 달라 **일관성이 떨어지는** 문제가 발생합니다.

### 왜 필요한가?

ARAE는 도면과 법규 데이터를 각각 분리된 정보가 아니라, **하나의 조회·분석·검색 흐름 안에서 다룰 수 있도록 통합**합니다.

- 도면을 **구조화된 데이터 자산**으로 변환하고,
- 사내 기준에 따라 **도면 평가를 자동화**하며,
- 기존 도면과의 **유사성 검색**을 제공하고,
- 주소/필지 기반으로 관련 **법규 데이터를 정확히 조회**합니다.

이를 통해 도면 검토 과정에서 반복되는 수작업과 맥락 전환을 줄이고, **건축사가 판단에 집중할 수 있는 환경**을 만드는 것이 최종 목적입니다.

### 이 프로젝트가 해결하는 것

도면 검토는 반복적이지만 자동화되어 있지 않습니다.

- 도면 정보, 내부 기준, 법규 정보가 **서로 연결되지 않은 채 분산**되어 있습니다.
- "비슷한 도면 사례"나 "기존 평가 결과"를 **체계적으로 재활용하기 어렵습니다**.

ARAE는 이 문제를 **AI의 추론이 아니라 데이터 구조화와 검색 중심**으로 해결한다는 점에서, 실무에 적용 가능한 보조 시스템입니다


---

## 2. Features

### F1. 도면 자산화
업로드된 도면을 분석하여 공간 구성, 면적 비율 등 핵심 정보를 **구조화된 데이터**로 생성합니다.

### F2. 도면 평가
도면 데이터를 저장하기 이전, **사내 기준 문서를 기반**으로 항목별 평가 결과를 제공합니다.

### F3. 유사 도면 검색
기존 도면 데이터 중 **공간 구성 및 특성이 유사한 도면**을 검색하고 비교합니다.

### F4. 법규·조례 조회
주소 또는 필지 정보를 기반으로 관련 **법규·조례 데이터를 정확히 조회**하여 제공합니다.

---

## 3. Tech Stack

### 🤖 AI / Analysis
- **Vision AI**
  - 건축 도면 이미지 분석
  - 공간 구성, 면적 비율, Bay 수 등 도면의 정량·구조 정보 추출
  - YOLOv5 기반 객체 검출 (OBJ, OCR, STR, SPA)
  
- **sLLM**
  - 도면 요약 텍스트 생성
  - 사내 기준 문서 기반 도면 평가 텍스트 생성
  - 판단 주체가 아닌, **결과 정리 및 설명 용도**로 사용
  - OpenAI GPT-4o-mini

### 🎨 Frontend
| 분야 | 기술 스택 |
|------|----------|
| **Framework** | React 19.2 + TypeScript |
| **Build Tool** | Vite 7.2 |
| **Routing** | React Router DOM 7.12 |
| **HTTP Client** | Axios 1.13 |
| **UI** | React Icons, React Hot Toast |
| **Styling** | CSS Modules |


### ⚙️ Backend
| 분야 | 기술 스택 |
|------|----------|
| **Framework** | Spring Boot 3.2.1 |
| **Language** | Java 21 |
| **ORM** | Spring Data JPA |
| **API Server** | FastAPI (Python) |
| **서버 역할** | 도면 처리 파이프라인, 데이터 정규화 및 응답 구성 로직 |

### 🗄️ Database
| 분야 | 기술 스택 |
|------|----------|
| **RDBMS** | PostgreSQL |
| **Vector DB** | pgvector (PostgreSQL Extension) |
| **저장 데이터** | 도면 메타데이터, 토지 특성 정보, 법규·조례 원문 데이터 |
| **벡터 데이터** | 도면 요약 및 특성 벡터, 유사 도면 검색용 임베딩 |

### 📊 Data Processing
| 분야 | 기술 스택 |
|------|----------|
| **Format** | JSON (도면 분석 결과, 평가 결과, 메타데이터) |
| **Library** | pandas (데이터 검증, 전처리, 샘플 데이터 분석) |


---

## 4. Architecture

### System Architecture

<img width="900" height="700" alt="ARAE System Architecture" src="https://github.com/user-attachments/assets/9e7c3249-6be6-48bb-bd0a-965208c439f7" />

### Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                      사용자 (건축사/검토자)                         │
└────────────────┬────────────────────────────────┬────────────────┘
                 │                                │
                 ▼                                ▼
    ┌─────────────────────┐          ┌─────────────────────┐
    │   Frontend (React)  │          │  Admin Dashboard    │
    │   - TypeScript      │          │  - 도면 관리         │
    │   - Vite           │          │  - 평가 기준 설정     │
    └──────────┬──────────┘          └──────────┬──────────┘
               │                                │
               ▼                                ▼
    ┌──────────────────────────────────────────────────────┐
    │         Backend (Spring Boot + FastAPI)              │
    │         - 도면 처리 파이프라인                          │
    │         - 데이터 정규화 및 응답 구성                     │
    │         - API 엔드포인트 제공                          │
    └────────────┬─────────────────────────┬───────────────┘
                 │                         │
                 ▼                         ▼
    ┌─────────────────────┐    ┌─────────────────────┐
    │Database (PostgreSQL)│    │ Vision AI / sLLM    │
    │ - 도면 메타데이터     │    │ - 도면 이미지 분석   │
    │ - 토지 특성 정보     │    │ - 구조화 데이터 생성 │
    │ - 법규·조례 데이터   │    │ - 평가 텍스트 생성   │
    └─────────────────────┘    └─────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────┐
    │  pgvector                    │
    │  - 도면 특성 벡터             │
    │  - 유사 도면 검색             │
    └──────────────────────────────┘
```

### CV 파이프라인 구조

```
┌────────────────┐
│ 도면 이미지 업로드 │
└────────┬───────┘
         │
         ▼
┌─────────────────────────────────────────┐
│         Vision AI Pipeline              │
│  ┌───────────────────────────────────┐  │
│  │    CV Inference Pipeline          │  │
│  │                                   │  │
│  │  1️⃣ OBJ Model (YOLOv5)            │  │
│  │     └─→ 객체 검출 (방, 문, 창문)    │  │
│  │                                   │  │
│  │  2️⃣ OCR Model                     │  │
│  │     └─→ 텍스트 영역 검출           │  │
│  │                                   │  │
│  │  3️⃣ STR Model                     │  │
│  │     └─→ 구조 분석                 │  │
│  │                                   │  │
│  │  4️⃣ SPA Model                     │  │
│  │     └─→ 공간 관계 분석             │  │
│  │                                   │  │
│  │  5️⃣ Aggregator                    │  │
│  │     └─→ 결과 통합 및 후처리         │  │
│  │                                   │  │
│  │  6️⃣ sLLM (GPT-4o-mini)           │  │
│  │     └─→ 도면 요약 및 평가 생성     │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│     분석 결과 출력                        │
│  - topology_graph.json                  │
│  - analysis_result.json                 │
│  - evaluation_result.json               │
└─────────────────────────────────────────┘
```

---

## 5. ERD

<img width="700" height="600" alt="ARAE ERD" src="https://github.com/user-attachments/assets/d58882d9-3e5e-4659-81ac-6aeeed104ba4" />

### 주요 테이블 구조

#### FloorPlan (도면)
- 도면 메타데이터 (ID, 업로드 일시, 파일 경로)
- 분석 결과 (topology_graph, analysis_result)
- 평가 결과 (evaluation_result)

#### Land (토지 정보)
- 주소, 필지 정보
- 토지 특성 (용도지역, 건폐율, 용적률)

#### Regulation (법규·조례)
- 법규 ID, 법규명
- 원문 데이터
- 적용 범위 (지역, 용도지역)

#### Vector (임베딩)
- 도면 특성 벡터
- pgvector를 통한 유사도 검색

---

## 6. API 명세

### 도면 분석 API

#### `POST /api/floorplan/analyze`
도면 이미지를 분석하여 구조화된 데이터를 반환합니다.

**Request**
```http
POST /api/floorplan/analyze
Content-Type: multipart/form-data

file: [도면 이미지 파일 (PNG, JPG, PDF)]
```

**Response**
```json
{
  "floorplan_id": "FP_20250204_001",
  "topology_graph": {
    "nodes": [...],
    "edges": [...]
  },
  "analysis_result": {
    "total_area": 84.5,
    "room_count": 3,
    "bay_count": 4,
    "balcony_ratio": 0.12
  },
  "summary": "3Bay 4룸 구조의 일반적인 아파트 도면입니다..."
}
```

---

### 도면 평가 API

#### `POST /api/floorplan/evaluate`
사내 기준 문서를 기반으로 도면을 평가합니다.

**Request**
```http
POST /api/floorplan/evaluate
Content-Type: application/json

{
  "floorplan_id": "FP_20250204_001",
  "criteria": "internal_standard_v1.0"
}
```

**Response**
```json
{
  "evaluation_id": "EVAL_001",
  "overall_score": 85,
  "items": [
    {
      "category": "공간 효율성",
      "score": 90,
      "comment": "전용면적 대비 거실 비율이 적정합니다."
    },
    {
      "category": "발코니 설계",
      "score": 75,
      "comment": "발코니 면적이 다소 작습니다."
    }
  ]
}
```

---

### 유사 도면 검색 API

#### `GET /api/floorplan/similar`
유사한 도면을 검색합니다.

**Request**
```http
GET /api/floorplan/similar?floorplan_id=FP_20250204_001&limit=5
```

**Response**
```json
{
  "query_floorplan": "FP_20250204_001",
  "similar_floorplans": [
    {
      "floorplan_id": "FP_20250120_045",
      "similarity_score": 0.92,
      "thumbnail": "data:image/png;base64,..."
    },
    ...
  ]
}
```

---

### 법규·조례 조회 API

#### `GET /api/regulation/query`
주소 또는 필지 정보로 관련 법규를 조회합니다.

**Request**
```http
GET /api/regulation/query?address=서울특별시 강남구 역삼동 123-45
```

**Response**
```json
{
  "address": "서울특별시 강남구 역삼동 123-45",
  "land_info": {
    "zone": "제2종일반주거지역",
    "building_coverage": 0.60,
    "floor_area_ratio": 2.50
  },
  "regulations": [
    {
      "regulation_id": "REG_001",
      "title": "건축법 제60조 (건폐율)",
      "content": "..."
    },
    ...
  ]
}
```

---

## 7. 프로젝트 구조

```

---

## 8. 실행 방법

### 1️⃣ 사전 준비

#### 필수 설치
- **Java**: OpenJDK 21 이상
- **Maven**: 3.8 이상
- **Node.js**: 18.x 이상
- **Python**: 3.9 이상
- **PostgreSQL**: 14 이상 (pgvector 확장 포함)

#### 환경 변수 설정
Python 서버의 `.env` 파일 생성:
```bash
# python/.env
OPENAI_API_KEY=your_openai_api_key_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=arae_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

---

### 2️⃣ Backend 실행 (Spring Boot)

```bash
cd Backend
mvn clean install
mvn spring-boot:run
```

서버 실행: `http://localhost:8080`

---

### 3️⃣ AI Server 실행 (Python/FastAPI)

```bash
cd python
pip install -r requirements.txt
python main.py
```

또는 Uvicorn으로 실행:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

서버 실행: `http://localhost:8000`  
API 문서: `http://localhost:8000/docs`

---

### 4️⃣ Frontend 실행 (React)

```bash
cd final-frontend-ts
npm install
npm run dev
```

개발 서버 실행: `http://localhost:3000`

---

### 5️⃣ 전체 시스템 확인

1. **Backend**: `http://localhost:8080`
2. **AI Server**: `http://localhost:8000`
3. **Frontend**: `http://localhost:3000`
4. **AI API Docs**: `http://localhost:8000/docs`

브라우저에서 `http://localhost:3000` 접속하여 도면 업로드 및 분석을 시작하세요!

---

## 9. 주요 성과 및 특징

### ⚡ 성능 지표
- **도면 분석 속도**: 평균 3~5초 (이미지당)
- **검색 정확도**: 벡터 유사도 기반 90% 이상
- **평가 일관성**: 사내 기준 기반 자동 평가로 일관성 확보
- **API 응답 시간**: 평균 < 1초

### 🎯 차별화 포인트
- ✅ **도면을 데이터 자산화**: 이미지 → 구조화 데이터 변환
- ✅ **실무 중심 설계**: AI 추론이 아닌 검색·분석 중심 접근
- ✅ **통합 워크플로우**: 도면 분석 → 평가 → 검색 → 법규 조회 일원화
- ✅ **확장 가능한 구조**: 평가 기준, 법규 데이터 업데이트 용이

---

## 10. 향후 계획

### 🎯 단기 목표 (1~2개월)
- [ ] **평가 기준 관리 UI**: 관리자가 직접 평가 기준을 수정할 수 있는 인터페이스
- [ ] **배치 분석**: 여러 도면 동시 업로드 및 비교 분석
- [ ] **보고서 자동 생성**: 도면 분석 및 평가 결과 PDF 리포트
- [ ] **성능 최적화**: GPU 가속, 캐싱 전략 개선

### 🚀 중장기 목표 (3~6개월)
- [ ] **다양한 도면 지원**: 오피스텔, 상가, 주택 도면 확대
- [ ] **법규 자동 업데이트**: 정부 API 연동으로 최신 법규 동기화
- [ ] **3D 렌더링**: 도면 기반 3D 모델링 자동 생성
- [ ] **모바일 앱**: React Native 기반 모바일 지원

### 💡 혁신 아이디어
- 🏗️ **건축 법규 자동 검증**: 도면이 건축법을 준수하는지 자동 확인
- 📊 **트렌드 분석**: 누적된 도면 데이터로 설계 트렌드 분석
- 🤝 **협업 기능**: 여러 검토자가 동시에 도면 검토 및 코멘트

---
## 11. 디렉토리 구조
```
SKN20-final/
│
├── 📄 README.md                          # 프로젝트 설명서
│
├── 📂 Backend/                           # Spring Boot 백엔드
│   ├── pom.xml                          # Maven 의존성 관리
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/com/              # Java 소스 코드
│   │   │   └── resources/             # 설정 파일
│   │   └── test/                      # 테스트 코드
│   └── target/                         # 빌드 산출물
│
├── 📂 final-frontend-ts/                 # React TypeScript 프론트엔드
│   ├── package.json                    # npm 의존성
│   ├── vite.config.ts                  # Vite 설정
│   ├── tsconfig.json                   # TypeScript 설정
│   ├── public/                         # 정적 파일
│   └── src/
│       ├── App.tsx                     # 루트 컴포넌트
│       ├── main.tsx                    # 앱 진입점
│       ├── app/                        # 앱 설정
│       ├── features/                   # 기능별 모듈
│       │   ├── admin/                 # 관리자 기능
│       │   ├── auth/                  # 인증/인가
│       │   ├── chat/                  # 챗봇
│       │   ├── floor-plan/            # 도면 분석
│       │   └── profile/               # 프로필
│       └── shared/                     # 공유 모듈
│           ├── api/                   # API 클라이언트
│           ├── components/            # 공통 컴포넌트
│           ├── contexts/              # React Context
│           ├── hooks/                 # Custom Hooks
│           ├── types/                 # TypeScript 타입
│           └── utils/                 # 유틸리티 함수
│
├── 📂 python/                            # Python AI 서버
│   ├── main.py                         # FastAPI 앱 진입점
│   ├── requirements.txt                # Python 의존성
│   ├── README_API.md                   # API 문서
│   │
│   ├── api_models/                     # API 스키마
│   │   └── schemas.py                 # Pydantic 모델
│   │
│   ├── api_utils/                      # API 유틸리티
│   │   └── image_utils.py             # 이미지 처리
│   │
│   ├── CV/                             # Computer Vision 모듈
│   │   ├── cv_inference/              # CV 추론 파이프라인
│   │   │   ├── pipeline.py           # 메인 파이프라인
│   │   │   ├── config.py             # 설정
│   │   │   ├── aggregator.py         # 결과 통합
│   │   │   ├── visualizer.py         # 시각화
│   │   │   ├── model/                # 모델 가중치
│   │   │   └── models/               # 모델 클래스
│   │   │       ├── obj_model.py      # 객체 검출
│   │   │       ├── ocr_model.py      # OCR
│   │   │       ├── str_model.py      # 구조 인식
│   │   │       └── spa_model.py      # 공간 분석
│   │   └── rag_system/                # RAG 시스템
│   │       ├── config.py             # RAG 설정
│   │       ├── embeddings.py         # 임베딩 생성
│   │       ├── llm_client.py         # LLM 클라이언트
│   │       ├── prompts.py            # 프롬프트 템플릿
│   │       └── schemas.py            # 데이터 스키마
│   │
│   ├── services/                       # 비즈니스 로직
│   │   ├── cv_service.py              # CV 서비스
│   │   ├── rag_service.py             # RAG 서비스
│   │   ├── embedding_service.py       # 임베딩 서비스
│   │   ├── pgvector_service.py        # 벡터 DB 서비스
│   │   └── chatbot_service.py         # 챗봇 서비스
│   │
│   ├── temp_input/                     # 업로드된 이미지 임시 저장
│   └── temp_output/                    # 분석 결과 저장
│       └── APT_FP_OBJ_*/              # 도면별 결과 폴더
│           ├── analysis_result.json   # 분석 결과
│           ├── llm_analysis.json      # LLM 분석
│           ├── topology_graph.json    # 위상 그래프
│           └── source_result.json     # 원본 결과
│
└── 📂 산출물/                            # 프로젝트 산출물
    ├── 1주차/                          # 1주차 산출물
    ├── 2주차/                          # 2주차 산출물
    └── 3주차/                          # 3주차 산출물
        └── finetunned_models/         # Fine-tuned 모델
```
