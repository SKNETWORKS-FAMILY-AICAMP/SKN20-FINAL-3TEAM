# 🏢 AI 기반 아파트 도면 분석 시스템 (AI-Powered Floor Plan Analysis System)

Computer Vision과 RAG 기술을 활용한 아파트 도면 자동 분석 및 상담 시스템

**빠르고 정확한 도면 분석**으로 부동산 상담의 새로운 패러다임을 제시합니다.

---

## 🏆 팀명 : 청바지 (청춘은 바로 지금)

### 👥 팀원 소개
| 이름       | 역할               | 주요 기여 분야                      |
|------------|--------------------|-----------------------------------|
🏆 **[SKN Family AI캠프] 최종 프로젝트**  
📅 **개발 기간**: 2025.01.13 ~ 2025.02.04

---

## 🎯 프로젝트 개요

본 프로젝트는 아파트 도면 이미지를 AI로 자동 분석하여 **방 구조, 면적, 공간 관계**를 파악하고, 이를 기반으로 **AI 챗봇이 실시간 부동산 상담**을 제공하는 통합 시스템입니다.

### 💡 핵심 가치
- **자동화된 도면 분석**: YOLOv5 기반 객체 인식으로 도면 요소 자동 검출
- **정확한 공간 인식**: OCR, 구조 분석, 공간 분석을 통합한 멀티모달 파이프라인
- **지능형 상담**: RAG(Retrieval-Augmented Generation) 기술로 도면 기반 맞춤 상담 제공
- **실시간 처리**: FastAPI + Spring Boot + React로 빠른 응답 속도 구현

### 🔑 해결하는 문제
- 📄 **도면 분석의 비효율성**: 수동 도면 검토에 소요되는 시간 단축
- 🏠 **부동산 정보 비대칭**: AI 상담으로 전문 지식 없이도 도면 이해 가능
- 💬 **실시간 상담 부재**: 24/7 AI 챗봇으로 언제든 도면 관련 질문 답변

---

## ✨ 주요 기능

### 1. 🖼️ **AI 기반 도면 분석**
- **객체 인식 (OBJ)**: 방, 문, 창문, 벽 등 도면 요소 자동 검출
- **문자 인식 (OCR)**: 도면 내 텍스트 영역 검출
- **구조 인식 (STR)**: 공간 구조 및 레이아웃 분석
- **공간 분석 (SPA)**: 방 간 연결 관계 및 위상 구조(Topology) 생성
- **시각화**: 분석 결과를 직관적인 이미지로 변환

### 2. 💬 **RAG 기반 AI 챗봇**
- 도면 분석 결과를 기반으로 한 맞춤형 상담
- 벡터 DB(PGVector)를 활용한 유사 도면 검색
- GPT-4o-mini 기반 자연어 대화
- 실시간 질의응답 및 컨텍스트 유지

### 3. 📊 **도면 관리 시스템**
- 업로드된 도면 이력 관리
- 분석 결과 저장 및 조회
- 사용자별 도면 데이터 관리
- 관리자 대시보드

---

## 🛠️ 기술 스택

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
| **Database** | H2 (Dev), MySQL (Prod) |
| **API** | RESTful API |

### 🤖 AI/ML Server (Python)
| 분야 | 기술 스택 |
|------|----------|
| **Framework** | FastAPI |
| **CV Library** | OpenCV, PyTorch, YOLOv5 |
| **OCR** | PaddleOCR / EasyOCR |
| **LLM** | OpenAI GPT-4o-mini |
| **Embedding** | OpenAI text-embedding-3-small |
| **Vector DB** | PGVector (PostgreSQL) |
| **Server** | Uvicorn |

### 🧠 AI Models
| 모델 | 용도 | 특징 |
|------|------|------|
| **YOLOv5** | 객체 검출 (OBJ) | 빠른 실시간 검출 성능 |
| **OCR Model** | 텍스트 영역 검출 | 한글/영문 도면 텍스트 인식 |
| **STR Model** | 구조 인식 | 도면 레이아웃 분석 |
| **SPA Model** | 공간 분석 | 방 간 연결 관계 파악 |
| **GPT-4o-mini** | 대화형 AI | 저비용 고성능 언어 모델 |
| **text-embedding-3-small** | 임베딩 | 벡터 검색 최적화 |

---

## 📊 시스템 아키텍처

### 전체 시스템 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                        사용자 (브라우저)                           │
└────────────────┬────────────────────────────────┬────────────────┘
                 │                                │
                 ▼                                ▼
    ┌─────────────────────┐          ┌─────────────────────┐
    │   Frontend (React)  │          │  Admin Dashboard    │
    │   - TypeScript      │          │  - 도면 관리         │
    │   - Vite           │          │  - 사용자 관리        │
    └──────────┬──────────┘          └──────────┬──────────┘
               │                                │
               ▼                                ▼
    ┌──────────────────────────────────────────────────────┐
    │         Backend (Spring Boot)                        │
    │         - RESTful API                                │
    │         - 사용자 인증/인가                             │
    │         - 도면 데이터 관리                             │
    └────────────┬─────────────────────────┬───────────────┘
                 │                         │
                 ▼                         ▼
    ┌─────────────────────┐    ┌─────────────────────┐
    │   Database (MySQL)  │    │ AI Server (FastAPI) │
    │   - 사용자 정보       │    │ - CV 파이프라인      │
    │   - 도면 메타데이터    │    │ - RAG 시스템         │
    │   - 분석 결과        │    └──────────┬──────────┘
    └─────────────────────┘               │
                                          ▼
                           ┌──────────────────────────────┐
                           │  Vector DB (PGVector)        │
                           │  - 도면 임베딩                │
                           │  - 유사도 검색                │
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
│         FastAPI Server                  │
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
│  │  6️⃣ Visualizer                    │  │
│  │     └─→ 결과 시각화                │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│     분석 결과 출력                        │
│  - topology_graph.json                  │
│  - topology_image.png                   │
│  - analysis_result.json                 │
│  - llm_analysis.json                    │
└─────────────────────────────────────────┘
```

### RAG 시스템 구조

```
┌─────────────────┐
│  사용자 질문      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│      RAG Service                    │
│  ┌───────────────────────────────┐  │
│  │  1️⃣ Embedding Service          │  │
│  │     └─→ 질문 벡터화             │  │
│  └───────────────────────────────┘  │
│              │                      │
│              ▼                      │
│  ┌───────────────────────────────┐  │
│  │  2️⃣ PGVector Service           │  │
│  │     └─→ 유사 도면 검색          │  │
│  └───────────────────────────────┘  │
│              │                      │
│              ▼                      │
│  ┌───────────────────────────────┐  │
│  │  3️⃣ Context Builder            │  │
│  │     └─→ 컨텍스트 구성           │  │
│  └───────────────────────────────┘  │
│              │                      │
│              ▼                      │
│  ┌───────────────────────────────┐  │
│  │  4️⃣ LLM Client (GPT-4o-mini)   │  │
│  │     └─→ 답변 생성               │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│   AI 답변 반환   │
└─────────────────┘
```

---

## 📁 프로젝트 구조

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

---

## 📡 API 명세

### 1. 도면 분석 API

#### `POST /analyze`
아파트 도면 이미지를 분석하여 객체, 구조, 공간 정보를 반환합니다.

**Request**
```http
POST /analyze
Content-Type: multipart/form-data

file: [이미지 파일 (PNG, JPG)]
```

**Response**
```json
{
  "topology_graph": {
    "nodes": [
      {
        "id": "room_001",
        "type": "거실",
        "area": 25.5,
        "position": {"x": 100, "y": 150}
      }
    ],
    "edges": [
      {
        "source": "room_001",
        "target": "room_002",
        "type": "문"
      }
    ]
  },
  "topology_image": "data:image/png;base64,iVBORw0KGgo...",
  "analysis_result": {
    "total_rooms": 3,
    "total_area": 84.5,
    "room_types": ["거실", "안방", "침실"]
  }
}
```

**상태 코드**
- `200 OK`: 분석 성공
- `400 Bad Request`: 잘못된 이미지 파일
- `500 Internal Server Error`: 서버 오류

---

### 2. 챗봇 API

#### `POST /chat`
도면 분석 결과 기반 AI 챗봇 대화

**Request**
```http
POST /chat
Content-Type: application/json

{
  "message": "이 아파트 거실 크기가 어떻게 되나요?",
  "floor_plan_id": "APT_FP_OBJ_001046197"
}
```

**Response**
```json
{
  "response": "분석 결과, 거실 면적은 약 25.5㎡입니다. 일반적인 84㎡ 아파트의 평균 거실 크기와 비슷합니다.",
  "confidence": 0.92,
  "related_info": {
    "room_type": "거실",
    "area": 25.5,
    "context": "topology_graph"
  }
}
```

---

### 3. 도면 저장 API

#### `POST /save`
분석된 도면 결과를 데이터베이스에 저장

**Request**
```http
POST /save
Content-Type: application/json

{
  "floor_plan_id": "APT_FP_OBJ_001046197",
  "user_id": "user_123",
  "analysis_data": { ... }
}
```

**Response**
```json
{
  "success": true,
  "floor_plan_id": "APT_FP_OBJ_001046197",
  "saved_at": "2025-02-04T10:30:00Z"
}
```

---

### 4. 도면 조회 API (Spring Boot)

#### `GET /api/floor-plans`
사용자의 도면 목록 조회

**Request**
```http
GET /api/floor-plans?userId=user_123
Authorization: Bearer {JWT_TOKEN}
```

**Response**
```json
{
  "floor_plans": [
    {
      "id": "APT_FP_OBJ_001046197",
      "uploadedAt": "2025-02-04T10:00:00Z",
      "status": "analyzed",
      "preview": "data:image/png;base64,..."
    }
  ],
  "total": 1
}
```

---

## 🗄️ 데이터베이스 스키마

### User (사용자)
```sql
CREATE TABLE users (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(50) UNIQUE NOT NULL,
  email VARCHAR(100) UNIQUE NOT NULL,
  password VARCHAR(255) NOT NULL,
  role ENUM('USER', 'ADMIN') DEFAULT 'USER',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### FloorPlan (도면)
```sql
CREATE TABLE floor_plans (
  id VARCHAR(100) PRIMARY KEY,
  user_id BIGINT NOT NULL,
  original_filename VARCHAR(255),
  file_path VARCHAR(500),
  status ENUM('UPLOADED', 'ANALYZING', 'COMPLETED', 'FAILED'),
  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  analyzed_at TIMESTAMP NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### AnalysisResult (분석 결과)
```sql
CREATE TABLE analysis_results (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  floor_plan_id VARCHAR(100) NOT NULL,
  topology_graph JSON,
  total_rooms INT,
  total_area DECIMAL(10, 2),
  room_details JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (floor_plan_id) REFERENCES floor_plans(id)
);
```

### ChatHistory (채팅 이력)
```sql
CREATE TABLE chat_history (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  floor_plan_id VARCHAR(100),
  message TEXT NOT NULL,
  response TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (floor_plan_id) REFERENCES floor_plans(id)
);
```

---

## 🚀 실행 방법

### 1️⃣ 사전 준비

#### 필수 설치
- **Java**: OpenJDK 21 이상
- **Maven**: 3.8 이상
- **Node.js**: 18.x 이상
- **Python**: 3.9 이상
- **PostgreSQL**: 14 이상 (PGVector 확장 포함)

#### 환경 변수 설정
Python 서버의 `.env` 파일 생성:
```bash
# python/.env
OPENAI_API_KEY=your_openai_api_key_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=floorplan_db
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

## 📊 주요 성과

### ⚡ 성능 지표
- **도면 분석 속도**: 평균 3~5초 (이미지당)
- **정확도**: 객체 검출 mAP 85% 이상
- **동시 처리**: 최대 10개 요청 병렬 처리
- **응답 시간**: API 평균 응답 시간 < 1초

### 🎯 주요 기능 달성률
- ✅ CV 파이프라인 통합 (OBJ, OCR, STR, SPA)
- ✅ RAG 기반 챗봇 시스템 구축
- ✅ 벡터 DB 기반 유사 도면 검색
- ✅ 실시간 도면 분석 및 시각화
- ✅ 사용자 인증 및 권한 관리
- ✅ 관리자 대시보드

---

## 🔮 향후 계획

### 🎯 단기 목표 (1~2개월)
- [ ] **모바일 앱 개발**: React Native로 iOS/Android 앱 출시
- [ ] **배치 분석**: 여러 도면 동시 업로드 및 비교 분석
- [ ] **3D 렌더링**: 도면 기반 3D 모델링 자동 생성
- [ ] **성능 최적화**: GPU 가속, 캐싱, CDN 적용

### 🚀 중장기 목표 (3~6개월)
- [ ] **다양한 도면 지원**: 오피스텔, 상가, 주택 도면 확대
- [ ] **실시간 협업**: 여러 사용자 동시 도면 검토 기능
- [ ] **보고서 자동 생성**: 도면 분석 결과 PDF 리포트 제작
- [ ] **API 서비스 출시**: 외부 개발자를 위한 Public API 제공
- [ ] **Fine-tuning**: 한국 아파트 도면 특화 모델 학습

### 💡 혁신 아이디어
- 🏗️ **건축 법규 검증**: 도면이 건축법을 준수하는지 자동 확인
- 💰 **가격 예측**: 도면 분석 기반 아파트 시세 예측
- 🌍 **다국어 지원**: 글로벌 시장 진출을 위한 다국어 챗봇

---
