#### SKN20-FINAL-3TEAM
# ARAE 

ARAE는 건축 도면을 입력으로 받아  
1) 도면 자산화(도면 → 구조화 데이터 생성)  
2) 사내 기준 기반 도면 평가  
3) 유사 도면 검색  
4) 주소/필지 기반 법규·조례 조회  
를 제공하는 **건축사 보조용 시스템**입니다.

---

## 팀명 : WE
- **팀원 소개**: 김지은, 나호성, 이승규, 정래원, 홍혜원
- **개발 기간**: 2025.01.13 ~ 2025.03.11

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

### AI / Analysis
- **Vision AI** (RunPod Serverless)
  - 건축 도면 이미지 분석
  - 공간 구성, 면적 비율, Bay 수 등 도면의 정량·구조 정보 추출
  - OBJ: YOLOv5 기반 객체 검출 (위생설비, 주방기기)
  - OCR: YOLOv5 + CRNN 기반 텍스트 검출 및 인식
  - STR/SPA: DeepLabV3+ 기반 구조 및 공간 분석

- **sLLM** (RunPod Pod, vLLM 서빙)
  - Qwen3-8B 파인튜닝 모델 2개
  - 도면 요약 텍스트 생성 / 사내 기준 기반 도면 평가 텍스트 생성
  - 판단 주체가 아닌, **결과 정리 및 설명 용도**로 사용

- **임베딩 / 리랭킹** (RunPod Serverless)
  - Qwen3-Embedding-0.6B (1024차원 벡터 생성)
  - Cross-encoder 리랭커 (검색 결과 재정렬)

### Frontend
| 분야 | 기술 스택 |
|------|----------|
| **Framework** | React 19.2.0 + TypeScript 5.9.3 |
| **Build Tool** | Vite 7.2.4 |
| **Routing** | React Router DOM 7.12.0 |
| **HTTP Client** | Axios 1.13.2 |
| **UI** | React Icons 5.5.0, React Hot Toast 2.6.0, React Markdown 10.1.0 |
| **Styling** | CSS Modules |


### Backend
| 분야 | 기술 스택 |
|------|----------|
| **Framework** | Spring Boot 3.4.3 |
| **Language** | Java 21 |
| **ORM** | Spring Data JPA + Hibernate |
| **Security** | Spring Security + JWT (JJWT 0.12.3) |
| **API Server** | FastAPI (Python) |
| **Cloud** | AWS S3 (도면 이미지 저장), AWS RDS (PostgreSQL) |

### Database
| 분야 | 기술 스택 |
|------|----------|
| **RDBMS** | PostgreSQL (AWS RDS) |
| **Vector DB** | pgvector (PostgreSQL Extension) |
| **저장 데이터** | 도면 메타데이터, 토지 특성 정보, 법규·조례 원문 데이터 |
| **벡터 데이터** | 도면 요약 및 특성 벡터, 유사 도면 검색용 임베딩 |

### Infra / DevOps
| 분야 | 기술 스택 |
|------|----------|
| **Server** | AWS EC2 (Spring Boot + FastAPI + Nginx) |
| **Database** | AWS RDS (PostgreSQL + pgvector) |
| **Storage** | AWS S3 (도면 이미지 저장) |
| **CI/CD** | GitHub Actions (자동 배포) |
| **GPU - Pod** | RunPod Pod + vLLM (sLLM 모델 2개 서빙) |
| **GPU - Serverless** | RunPod Serverless (CV 4모델, 임베딩, 리랭커) |


---

## 4. Architecture

### System Architecture

<img width="900" height="700" alt="ARAE System Architecture" src="https://github.com/user-attachments/assets/9e7c3249-6be6-48bb-bd0a-965208c439f7" />

### Workflow

```
┌──────────────────────────────────────────────────────────┐
│                  사용자 (건축사/검토자)                     │
└──────────┬───────────────────────────────┬───────────────┘
           │                               │
           ▼                               ▼
┌─────────────────────┐       ┌─────────────────────┐
│  Frontend (React)   │       │  Admin Dashboard    │
│  - TypeScript       │       │  - 도면/사용자 관리   │
│  - Vite             │       │  - 로그 조회         │
└──────────┬──────────┘       └──────────┬──────────┘
           │                             │
           ▼                             ▼
┌──────────────────────────────────────────────────────┐
│       Backend (Spring Boot 3.4.3, Java 21)           │
│       - REST API (Auth, FloorPlan, Admin, Chatbot)   │
│       - JWT 인증/인가, S3 이미지 저장                  │
└──────────────────────┬───────────────────────────────┘
                       │ REST API
                       ▼
┌──────────────────────────────────────────────────────┐
│          Python API Server (FastAPI)                 │
│  ┌────────────────────────────────────────────────┐  │
│  │  Orchestrator Agent (의도 분류 & 라우팅)         │  │
│  │  ├─ FloorplanSearchAgent (도면 검색/평가)       │  │
│  │  ├─ RegulationSearchAgent (법규·조례 조회)      │  │
│  │  └─ CVAnalysisAgent (도면 분석)                 │  │
│  └────────────────────────────────────────────────┘  │
└───────┬──────────────┬──────────────┬───────────────┘
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌───────────────┐ ┌───────────────┐
│  PostgreSQL  │ │ RunPod Pod    │ │RunPod         │
│  + pgvector  │ │ vLLM 서빙     │ │Serverless     │
│  (AWS RDS)   │ │ sLLM x2      │ │CV·임베딩·리랭커│
└──────────────┘ └───────────────┘ └───────────────┘
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
│  │     └─→ 객체 검출 (변기, 세면대,   │  │
│  │         싱크대, 욕조, 가스레인지)   │  │
│  │                                   │  │
│  │  2️⃣ OCR Model (YOLOv5 + CRNN)    │  │
│  │     └─→ 텍스트 영역 검출 및 인식   │  │
│  │                                   │  │
│  │  3️⃣ STR Model (DeepLabV3+)       │  │
│  │     └─→ 출입문, 창호, 벽체 검출    │  │
│  │                                   │  │
│  │  4️⃣ SPA Model (DeepLabV3+)       │  │
│  │     └─→ 13개 공간 타입 분석        │  │
│  │                                   │  │
│  │  5️⃣ Aggregator                    │  │
│  │     └─→ 결과 통합 및 후처리         │  │
│  │                                   │  │
│  │  6️⃣ sLLM (Qwen3-8B Fine-tuned)   │  │
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

### Spring Boot API (포트 8080)

#### 인증 (`/api/auth`)
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/auth/signup` | 회원가입 |
| POST | `/api/auth/login` | 로그인 (JWT 발급) |
| POST | `/api/auth/refresh` | 토큰 갱신 |
| GET | `/api/auth/me` | 내 정보 조회 |
| POST | `/api/auth/change-password` | 비밀번호 변경 |
| POST | `/api/auth/mailSend` | 인증 메일 발송 |

#### 도면 (`/api/floorplan`)
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/floorplan/analyze` | 도면 이미지 분석 (CV 파이프라인) |
| POST | `/api/floorplan/save` | 분석 결과 저장 |
| GET | `/api/floorplan/my` | 내 도면 목록 조회 |
| GET | `/api/floorplan/{id}/detail` | 도면 상세 조회 |
| GET | `/api/floorplan/{id}/image` | 도면 이미지 조회 (S3) |

#### 챗봇 (`/api/chatbot`)
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/chatbot/chat` | 대화 요청 (Orchestrator → Agent 라우팅) |
| POST | `/api/chatbot/sessionuser` | 세션 사용자 설정 |
| POST | `/api/chatbot/roomhistory` | 채팅방 히스토리 조회 |
| POST | `/api/chatbot/editroomname` | 채팅방 이름 변경 |
| POST | `/api/chatbot/deleteroom` | 채팅방 삭제 |

#### 관리자 (`/api/admin`)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/admin/stats` | 대시보드 통계 |
| GET | `/api/admin/logs` | 활동 로그 조회 |
| GET | `/api/admin/floorplans` | 전체 도면 관리 |

### FastAPI (Python, 포트 8000)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/analyze` | CV 파이프라인 실행 (OBJ→OCR→STR→SPA→Aggregator→sLLM) |
| POST | `/generate-metadata` | 도면 메타데이터 생성 (임베딩 포함) |
| POST | `/orchestrate` | 챗봇 질의 처리 (의도 분류 → 에이전트 라우팅) |
| GET | `/health` | 서버 상태 확인 |

---


## 7. 주요 성과 및 특징

### 차별화 포인트
- **도면을 데이터 자산화**: 이미지 → 구조화 데이터 변환
- **실무 중심 설계**: AI 추론이 아닌 검색·분석 중심 접근
- **통합 워크플로우**: 도면 분석 → 평가 → 저장 / 유사 도면 검색 / 법규 조회

---


## 8. 디렉토리 구조
```
SKN20-FINAL-3TEAM/
│
├── 📄 README.md                          # 프로젝트 설명서
├── 📂 .github/workflows/                 # CI/CD (GitHub Actions 자동 배포)
│
├── 📂 Backend/                           # Spring Boot 백엔드
│   ├── pom.xml                          # Maven 의존성 관리
│   └── src/main/
│       ├── java/com/example/skn20/
│       │   ├── config/                  # Security, Web, Mail 설정
│       │   ├── controller/              # REST API 컨트롤러
│       │   │   ├── AuthController       # 인증 (로그인/회원가입)
│       │   │   ├── FloorPlanController  # 도면 분석/저장
│       │   │   ├── ChatbotController    # 챗봇
│       │   │   └── AdminController      # 관리자
│       │   ├── entity/                  # JPA 엔티티
│       │   ├── dto/                     # 요청/응답 DTO
│       │   ├── repository/              # 데이터 접근 계층
│       │   ├── service/                 # 비즈니스 로직
│       │   │   ├── FloorPlanService     # 도면 처리
│       │   │   ├── ChatbotService       # 챗봇 서비스
│       │   │   ├── S3Service            # AWS S3 이미지 저장
│       │   │   └── AdminService         # 관리자 기능
│       │   └── security/                # JWT 인증 필터
│       └── resources/                   # 설정 파일, 초기 데이터
│
├── 📂 final-frontend-ts/                 # React TypeScript 프론트엔드
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx                     # 루트 컴포넌트
│       ├── main.tsx                    # 앱 진입점
│       ├── features/                   # 기능별 모듈
│       │   ├── admin/                 # 관리자 대시보드
│       │   ├── auth/                  # 로그인/회원가입/비밀번호 재설정
│       │   ├── chat/                  # 챗봇 (도면검색 / 법규조회)
│       │   ├── floor-plan/            # 도면 업로드 & 분석 뷰어
│       │   └── profile/               # 사용자 프로필
│       └── shared/                     # 공유 모듈
│           ├── api/                   # Axios HTTP 클라이언트
│           ├── components/            # 공통 UI (Sidebar, Button 등)
│           ├── contexts/              # Auth, Theme Context
│           └── hooks/                 # Custom Hooks
│
├── 📂 python/                            # Python AI 서버 (FastAPI)
│   ├── main.py                         # FastAPI 앱 진입점
│   ├── requirements.txt                # Python 의존성
│   │
│   ├── agents/                         # Agent 오케스트레이션
│   │   ├── orchestrator.py            # 의도 분류 & 에이전트 라우팅
│   │   ├── cv_analysis_agent.py       # 도면 분석 에이전트
│   │   ├── floorplan_search_agent.py  # 도면 검색 에이전트
│   │   └── regulation_search_agent.py # 법규 조회 에이전트
│   │
│   ├── api_models/                     # API 스키마 (Pydantic)
│   ├── api_utils/                      # 이미지 처리 유틸리티
│   │
│   ├── CV/                             # Computer Vision 모듈
│   │   ├── cv_inference/              # CV 추론 파이프라인
│   │   │   ├── pipeline.py           # 메인 파이프라인
│   │   │   ├── aggregator.py         # 결과 통합 및 후처리
│   │   │   ├── visualizer.py         # 시각화
│   │   │   ├── models/               # 모델 래퍼 (OBJ, OCR, STR, SPA)
│   │   │   ├── model/                # 모델별 학습/평가 코드
│   │   │   └── yolov5/               # YOLOv5 소스 코드
│   │   ├── rag_system/                # RAG 시스템
│   │   │   ├── llm_client.py         # LLM 클라이언트
│   │   │   ├── embeddings.py         # 임베딩 생성
│   │   │   └── prompts.py            # 프롬프트 템플릿
│   │   └── rag_data/                  # RAG 참조 데이터
│   │
│   ├── services/                       # 비즈니스 로직
│   │   ├── cv_inference_service.py    # CV 파이프라인 서비스
│   │   ├── floorplan_analysis_service.py    # 도면 분석
│   │   ├── floorplan_text_search_service.py # 도면 텍스트 검색 (Hybrid RAG)
│   │   ├── floorplan_image_search_service.py # 도면 이미지 유사도 검색
│   │   ├── chatbot_law_service.py     # 법규·조례 챗봇
│   │   ├── internal_eval_service.py   # 사내 기준 평가
│   │   ├── embedding_service.py       # 임베딩 서비스
│   │   └── runpod_client.py           # RunPod Serverless 클라이언트
│   │
│   └── eval/                           # 평가 모듈
│
└── 📂 산출물/                            # 프로젝트 산출물 (주차별)
