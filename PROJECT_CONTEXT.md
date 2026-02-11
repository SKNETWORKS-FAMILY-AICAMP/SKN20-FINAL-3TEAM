# ARAE 프로젝트 컨텍스트 문서

> **목적**: AI 어시스턴트가 프로젝트를 이해하고 적절한 답변을 제공하기 위한 컨텍스트 문서

---

## 📌 프로젝트 개요

### 프로젝트명
**ARAE** (건축사 보조용 시스템)

### 핵심 기능
1. **도면 자산화**: 건축 도면 이미지 → 구조화된 데이터로 변환
2. **도면 평가**: 사내 기준 기반 자동 평가
3. **유사 도면 검색**: 기존 도면과의 유사도 기반 검색
4. **법규·조례 조회**: 주소/필지 기반 관련 법규 데이터 조회

### 개발 기간 & 팀
- **기간**: 2025.01.13 ~ 2025.02.04
- **팀**: WE (김지은, 나호성, 이승규, 정래원, 홍혜원)

---

## 🏗️ 시스템 아키텍처

### 전체 구조
```
Frontend (React + TypeScript)
    ↓
Backend (Spring Boot 8080)
    ↓
Python Server (FastAPI 8000) ← CV 모델 + LLM
    ↓
Database (PostgreSQL + pgvector)
```

### 주요 컴포넌트

#### 1. Frontend
- **프레임워크**: React 19.2 + TypeScript
- **빌드 도구**: Vite 7.2
- **라우팅**: React Router DOM 7.12
- **HTTP 클라이언트**: Axios 1.13
- **스타일링**: CSS Modules
- **주요 페이지**:
  - 도면 업로드 페이지 (`FileUploadPage`)
  - 채팅 페이지 (`ChatPage`)
  - 관리자 페이지 (Admin Dashboard)
  - 인증 페이지 (로그인/회원가입)

#### 2. Backend (Spring Boot)
- **버전**: Spring Boot 3.2.1
- **언어**: Java 21
- **ORM**: Spring Data JPA
- **포트**: 8080
- **주요 Controller**:
  - `FloorPlanController`: 도면 분석 및 저장
  - `ChatbotController`: 챗봇 기능
  - `AdminController`: 관리자 기능
  - `AuthController`: 인증/인가

**FloorPlanController 주요 엔드포인트**:
- `POST /api/floorplan/analyze`: 도면 분석 (DB 저장 X, 프리뷰만)
- `POST /api/floorplan/save`: 도면 최종 저장 (DB에 저장)

#### 3. Python Server (FastAPI)
- **포트**: 8000
- **주요 파일**: `python/main.py`
- **주요 엔드포인트**:
  - `POST /analyze`: 도면 이미지 분석
  - `POST /save`: 도면 저장 및 평가
  - `POST /chat`: 챗봇 대화
  - `GET /health`: 헬스 체크

**서비스 구조** (`python/services/`):
- `cv_service.py`: CV 모델 파이프라인 실행
- `rag_service.py`: RAG 기반 도면 평가
- `embedding_service.py`: 벡터 임베딩 생성
- `chatbot_service.py`: 챗봇 대화 처리
  - 질문 분류 Agent (Top Agent)
  - 도면 찾기 로직
  - 법/조례 조회 로직
  - 답변 생성 Agent (LLM → sLLM 전환 예정)
  - 답변 검증 Agent (Verification Agent)
- `pgvector_service.py`: pgvector 벡터 검색

#### 4. Database
- **RDBMS**: PostgreSQL
- **Vector 검색**: pgvector (PostgreSQL Extension)
- **주요 테이블**: 8개 (User, FloorPlan, FloorplanAnalysis, InternalEval, LandChar, Law, ChatRoom, ChatHistory)
- **데이터 파일** (`Backend/target/classes/data/`):
  - `법규조례_전처리완료.csv`: Law 테이블 초기 데이터 (913,591건, 7개 컬럼)
    * 컬럼: region_code, region_name, zone_district_name, law_name, land_use_activity, permission_category, condition_exception
  - `토지특성정보_전처리완료.csv`: LandChar 테이블 초기 데이터 (5,841,461건, 14개 컬럼)
    * 컬럼: legal_dong_code, legal_dong_name, ledger_type, lot_number, land_category, land_area, zone1, zone2, land_use, terrain_height, terrain_shape, road_access, address_text, region_code
  - `evaluation_docs_export.json`: InternalEval 테이블 초기 데이터 (벡터 포함)
  - `건축물용도_정의.csv`: 건축물 용도 참조 데이터

**테이블 상세 구조**:

**1. Law (법규/조례)**
```java
@Entity
@Table(name = "law")
public class Law {
    private Long id;
    private String regionCode;         // 지역 코드 (시군구 코드)
    private String regionName;         // 지역명 (예: 서울특별시, 경기도)
    private String zoneDistrictName;   // 용도지역/지구명 (예: 제1종일반주거지역)
    private String lawName;            // 관련 법률명
    private String landUseActivity;    // 토지 이용 행위 (건축, 개발 등)
    private String permissionCategory; // 가능여부_정규화 (허용, 불허, 조건부허용)
    private String conditionException; // 조건 및 예외사항
}
```
- **용도**: 법/조례 조회 챗봇의 핵심 데이터
- **연결**: `regionCode`와 `zoneDistrictName`으로 LandChar와 연결
- **검색**: 지역 + 용도지역 조합으로 관련 법규 조회
- **전처리 데이터**: `법규조례_전처리완료.csv` (913,591건, 7개 컬럼)

**2. LandChar (토지 특성)**
```java
@Entity
@Table(name = "land_char")
public class LandChar {
    private Long id;
    private String legalDongCode;      // 법정동 코드
    private String legalDongName;      // 법정동 이름 (예: 서울특별시 강남구 역삼동)
    private String ledgerType;         // 대장 구분 (토지/임야)
    private String lotNumber;          // 지번 (예: 123-45)
    private String landCategory;       // 지목 (대, 전, 답, 임야 등)
    private Float landArea;            // 토지 면적 (㎡)
    private String zone1;              // 용도지역1 (주거지역, 상업지역 등)
    private String zone2;              // 용도지역2 (세부 용도지역)
    private String landUse;            // 토지 이용 현황
    private String terrainHeight;      // 지형 높이
    private String terrainShape;       // 지형 형상
    private String roadAccess;         // 도로 접면
    private String addressText;        // 주소_텍스트 (전처리 완료)
    private String regionCode;         // 지역 코드 (시군구 코드)
}
```
- **용도**: 주소/필지로 토지 정보 조회
- **연결**: `regionCode`와 `zone1/zone2`로 Law 테이블과 연결
- **검색**: `legalDongName` + `lotNumber`로 특정 필지 조회
- **전처리 데이터**: `토지특성정보_전처리완료.csv` (5,841,461건, 14개 컬럼)

**3. FloorPlan (도면)**
```java
@Entity
@Table(name = "floorplan")
public class FloorPlan {
    private Long id;
    @ManyToOne private User user;
    private LocalDate createdAt;
    private String name;
    private String imageUrl;
    private String assessmentJson;     // 요약 및 평가 JSON
    @OneToOne private FloorplanAnalysis analysis;
}
```
- **용도**: 도면 메타데이터 저장
- **연결**: FloorplanAnalysis와 1:1 관계

**4. InternalEval (사내 평가 기준)**
```java
@Entity
@Table(name = "InternalEval")
public class InternalEval {
    private Long id;
    private String keywords;           // 키워드
    private String document;           // 문서 내용
    @Column(columnDefinition = "vector(512)")
    private float[] embedding;         // 벡터 임베딩 (512차원)
}
```
- **용도**: RAG 기반 도면 평가 시 사내 기준 문서 검색
- **검색**: pgvector의 코사인 유사도 검색

**5. ChatRoom, ChatHistory**
- 챗봇 대화 세션 및 히스토리 관리

---

## 🤖 AI/ML 컴포넌트

### CV 파이프라인 (`python/CV/cv_inference/`)

**실행 순서**:
1. **OBJ Model** (YOLOv5): 객체 검출 (변기, 세면대, 싱크대, 욕조, 가스레인지)
2. **OCR Model** (YOLOv5 + CRNN): 텍스트 영역 검출 및 인식
3. **STR Model** (DeepLabV3+): 구조 요소 검출 (출입문, 창호, 벽체)
4. **SPA Model** (DeepLabV3+): 공간 분석 (13개 공간 타입 분류)
5. **Aggregator**: 결과 통합 및 후처리
6. **sLLM** (GPT-4o-mini): 도면 요약 및 평가 텍스트 생성

**출력 파일**:
- `topology_graph.json`: 공간 구조 그래프 데이터
- `analysis_result.json`: 상세 분석 결과
- `evaluation_result.json`: 평가 결과 (RAG 기반)
- `topology_image.png`: 시각화된 토폴로지 이미지

### RAG 시스템 (`python/CV/rag_system/`)
- **목적**: 사내 기준 문서 기반 도면 평가
- **구성**:
  - `config.py`: RAG 설정
  - `embeddings.py`: 임베딩 생성
  - `llm_client.py`: OpenAI API 클라이언트
  - `prompts.py`: 프롬프트 템플릿
  - `schemas.py`: 데이터 스키마

---

## 📂 프로젝트 구조

```
SKN20-FINAL-3TEAM/
├── README.md                    # 프로젝트 설명
├── PROJECT_CONTEXT.md           # 이 문서 (AI 어시스턴트용)
├── SETUP_GUIDE.md              # 설치 가이드
├── 산출물/                      # 주차별 산출물
│   ├── 1주차/
│   ├── 2주차/
│   └── 3주차/
│       └── finetunned_models/  # 파인튜닝 모델
├── Backend/                     # Spring Boot 서버
│   ├── pom.xml                 # Maven 설정
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/com/example/skn20/
│   │   │   │   ├── controller/  # REST API 컨트롤러
│   │   │   │   ├── service/     # 비즈니스 로직
│   │   │   │   ├── entity/      # JPA 엔티티
│   │   │   │   ├── dto/         # 데이터 전송 객체
│   │   │   │   └── repository/  # JPA 레포지토리
│   │   │   └── resources/
│   │   │       ├── application.properties  # Spring 설정
│   │   │       └── data/        # CSV 데이터 파일
│   │   └── test/                # 테스트 코드
│   └── target/                  # 빌드 출력 (생성됨)
├── final-frontend-ts/           # React + TypeScript 프론트엔드
│   ├── package.json            # npm 설정
│   ├── vite.config.ts          # Vite 설정
│   ├── tsconfig.json           # TypeScript 설정
│   └── src/
│       ├── App.tsx             # 메인 앱 컴포넌트
│       ├── main.tsx            # 엔트리 포인트
│       ├── features/           # 기능별 모듈
│       │   ├── admin/          # 관리자 기능
│       │   ├── auth/           # 인증 기능
│       │   ├── chat/           # 채팅 기능
│       │   ├── floor-plan/     # 도면 업로드/분석
│       │   └── profile/        # 프로필
│       └── shared/             # 공통 모듈
│           ├── api/            # API 클라이언트
│           ├── components/     # 공통 컴포넌트
│           ├── contexts/       # React Context
│           ├── hooks/          # 커스텀 훅
│           └── utils/          # 유틸리티 함수
└── python/                      # FastAPI 서버
    ├── main.py                 # FastAPI 앱 (엔트리 포인트)
    ├── requirements.txt        # Python 의존성
    ├── README_API.md           # API 실행 가이드
    ├── api_models/             # API 스키마
    │   └── schemas.py          # Request/Response 모델
    ├── api_utils/              # API 유틸리티
    │   └── image_utils.py      # 이미지 처리 유틸
    ├── services/               # 비즈니스 로직
    │   ├── cv_service.py       # CV 파이프라인 서비스
    │   ├── rag_service.py      # RAG 평가 서비스
    │   ├── embedding_service.py    # 임베딩 서비스
    │   ├── chatbot_service.py      # 챗봇 서비스
    │   └── pgvector_service.py     # Vector DB 서비스
    └── CV/                     # Computer Vision 모듈
        ├── requirements.txt    # CV 전용 의존성
        ├── cv_inference/       # CV 추론 파이프라인
        │   ├── pipeline.py     # 메인 파이프라인
        │   ├── aggregator.py   # 결과 통합
        │   ├── config.py       # CV 설정
        │   ├── visualizer.py   # 시각화
        │   ├── models/         # 모델 가중치 (.pt 파일)
        │   └── yolov5/         # YOLOv5 구현
        └── rag_system/         # RAG 평가 시스템
            ├── config.py       # RAG 설정
            ├── embeddings.py   # 임베딩 생성
            ├── llm_client.py   # LLM 클라이언트
            ├── prompts.py      # 프롬프트 템플릿
            └── schemas.py      # RAG 스키마
```

---

## 🔄 주요 워크플로우

### 1. 도면 분석 워크플로우

```
[사용자] 이미지 업로드
    ↓
[Frontend] FormData로 파일 전송
    ↓
[Spring Boot] POST /api/floorplan/analyze
    ↓ (파일 전달)
[Python FastAPI] POST /analyze
    ↓
[CV Pipeline] 
    - OBJ 검출
    - OCR 인식
    - STR 구조 분석
    - SPA 공간 분석
    - Aggregator 통합
    - LLM 요약 생성
    ↓
[Python] 분석 결과 반환
    - topology_graph
    - topology_image (Base64)
    - analysis_result (LLM 요약 포함)
    ↓
[Spring Boot] 결과 전달
    ↓
[Frontend] 프리뷰 화면 표시
```

### 2. 도면 저장 워크플로우

```
[사용자] "저장" 버튼 클릭
    ↓
[Frontend] POST /api/floorplan/save
    - file (이미지)
    - name (도면명)
    - assessmentJson (사내 기준 평가 JSON)
    ↓
[Spring Boot] Python 서버로 전달
    ↓
[Python FastAPI] POST /save
    ↓
[RAG Service] 사내 기준 문서 기반 평가
    ↓
[Embedding Service] 벡터 임베딩 생성
    ↓
[pgvector] 벡터 저장
    ↓
[PostgreSQL] 도면 메타데이터 저장
    ↓
[Python] 저장 결과 반환
    ↓
[Spring Boot] DB에 최종 저장
    ↓
[Frontend] 완료 메시지 표시
```

### 3. 챗봇 워크플로우

```
[사용자] 질문 입력
    ↓
[Frontend] POST /api/chatbot/chat
    ↓
[Spring Boot] Python 서버로 전달
    ↓
[Python FastAPI] POST /chat
    ↓
[질문 분류 Agent (LLM)]
    - 질문 유형 분류: "도면 찾기" or "법/조례 조회"
    ↓
    ├─→ [도면 찾기 로직]
    │       - 사용자 질문 임베딩
    │       - pgvector에서 유사 도면 검색
    │       - 검색된 도면 데이터 수집
    │       ↓
    │   [답변 생성 (LLM)]
    │       - 검색 결과 기반 답변 생성
    │       - (향후: sLLM으로 전환 예정)
    │       ↓
    │   [답변 검증 Agent]
    │       - 생성된 답변의 정확성 검증
    │       - 검색 결과와 답변 일치성 확인
    │       - 환각(Hallucination) 방지
    │       - 필요시 답변 수정 또는 재생성 요청
    │
    └─→ [법/조례 조회 로직]
            - 주소/필지 정보 추출
            - 관련 법규 데이터 검색
            - 토지 특성 정보 조회
            ↓
        [답변 생성 (LLM)]
            - 법규 조회 결과 기반 답변 생성
            - (향후: sLLM으로 전환 예정)
            ↓
        [답변 검증 Agent]
            - 생성된 답변의 정확성 검증
            - 법규 데이터와 답변 일치성 확인
            - 환각(Hallucination) 방지
            - 필요시 답변 수정 또는 재생성 요청
    ↓
[Python] 답변 반환
    ↓
[Spring Boot] 답변 전달
    ↓
[Frontend] 채팅 화면에 표시
```

#### 챗봇 아키텍처 상세

**🔍 1단계: 질문 분류 (Top Agent)**
- **역할**: 사용자 질문을 2가지 유형으로 분류
  - **도면 찾기**: 유사 도면 검색, 도면 비교, 공간 구성 질문 등
  - **법/조례 조회**: 주소 기반 법규 조회, 건축 규정 질문 등
- **모델**: LLM (GPT-4o-mini)
- **입력**: 사용자 질문 텍스트
- **출력**: 질문 유형 분류 결과 (`floor_plan` or `regulation`)

**🏗️ 2단계: 질문 유형별 처리**

**A. 도면 찾기 로직**
1. 사용자 질문을 벡터로 임베딩
2. pgvector에서 코사인 유사도 기반 검색
3. 검색된 도면의 메타데이터 및 분석 결과 수집
4. 도면 간 비교 데이터 생성 (필요 시)

**B. 법/조례 조회 로직**

**처리 흐름**:
```
사용자 질문: "서울시 강남구 역삼동 123-45번지에 건축할 때 적용되는 법규가 뭐야?"
    ↓
1. 주소/필지 정보 추출 (LLM 또는 정규식)
   - 주소: "서울특별시 강남구 역삼동"
   - 지번: "123-45"
    ↓
2. LandChar 테이블 조회 (Spring Boot Repository)
   - legalDongName LIKE '%강남구 역삼동%'
   - lotNumber = '123-45'
   → 토지 특성 정보 획득:
     * zone1: "주거지역"
     * zone2: "제1종일반주거지역"
     * regionCode: "11680"
     * landArea: 250.5
     * landCategory: "대"
     * terrainHeight, terrainShape, roadAccess 등
    ↓
3. Law 테이블 조회 (Spring Boot Repository)
   - regionCode = "11680"
   - zoneDistrictName LIKE '%제1종일반주거지역%'
   → 관련 법규 목록 획득:
     * regionName: "서울특별시"
     * lawName: "국토의 계획 및 이용에 관한 법률"
     * landUseActivity: "단독주택 건축"
     * permissionCategory: "허용"
     * conditionException: "건폐율 60% 이하, 용적률 200% 이하"
    ↓
4. 컨텍스트 구성
   {
     "토지정보": {
       "주소": "서울특별시 강남구 역삼동",
       "지번": "123-45",
       "용도지역": "제1종일반주거지역",
       "면적": 250.5,
       "지목": "대"
     "관련법규": [
       {
         "지역명": "서울특별시",
         "법률명": "국토의 계획 및 이용에 관한 법률",
         "행위": "단독주택 건축",
         "허가상태": "허용",
         "조건": "건폐율 60% 이하, 용적률 200% 이하"
       }
     ]
   }
```

**검색 전략**:
- **1순위**: `regionCode` + `zoneDistrictName` 정확 매칭
- **2순위**: `regionName` + `zoneDistrictName` 부분 문자열 매칭
- **3순위**: `zoneDistrictName`만 부분 문자열 매칭
- **4순위**: `regionCode`만 매칭

**필요한 인덱스**:
```sql
-- LandChar 테이블
CREATE INDEX idx_land_legal_dong_name ON land_char(legal_dong_name);
CREATE INDEX idx_land_region_code ON land_char(region_code);
CREATE INDEX idx_land_zone1 ON land_char(zone1);
CREATE INDEX idx_land_address_text ON land_char(address_text);

-- Law 테이블
CREATE INDEX idx_law_region_code ON law(region_code);
CREATE INDEX idx_law_region_name ON law(region_name);
CREATE INDEX idx_law_zone_district ON law(zone_district_name);
CREATE INDEX idx_law_permission ON law(permission_category);
```
4. 용도지역, 건폐율, 용적률 등 정보 수집
4. 용도지역, 건폐율, 용적률 등 정보 수집

**📝 3단계: 답변 생성**
- **현재**: LLM (GPT-4o-mini) 사용
  - 검색 결과를 컨텍스트로 제공
  - 자연어 답변 생성
- **향후 계획**: sLLM으로 전환
  - LLM 사용 중 대화 로그 및 답변 품질 수집
  - 학습 데이터셋 구축
  - sLLM 파인튜닝 및 성능 비교
  - 성능 검증 후 sLLM 배포

**✅ 4단계: 답변 검증 (Verification Agent)**
- **역할**: 생성된 답변의 신뢰성 검증
- **검증 항목**:
  1. **사실 일치성**: 검색된 데이터와 답변 내용 일치 여부
  2. **환각 방지**: 존재하지 않는 정보를 답변에 포함했는지 확인
  3. **완성도**: 사용자 질문에 충분히 답변했는지 확인
  4. **일관성**: 답변 내 논리적 모순 여부 확인
- **처리 방식**:
  - 검증 통과 시: 답변 그대로 반환
  - 검증 실패 시: 답변 수정 또는 재생성 요청
  - 심각한 오류 시: 사용자에게 경고 메시지 포함
- **모델**: LLM (GPT-4o-mini)
- **목적**: 답변 품질 향상 및 신뢰성 확보

---

## 🔑 주요 기술적 특징

### 1. 멀티 모델 앙상블
- 4개의 딥러닝 모델을 순차적으로 실행하여 도면 분석
- 각 모델의 출력을 Aggregator가 통합하여 최종 결과 생성

### 2. RAG 기반 평가
- 사내 기준 문서를 벡터화하여 저장
- 도면 특성과 유사한 기준 문서를 검색
- LLM이 검색된 문서를 참조하여 평가 텍스트 생성

### 3. pgvector를 통한 유사 도면 검색
- 도면의 공간 구성, 면적 비율 등을 벡터로 임베딩
- 코사인 유사도 기반 검색으로 유사 도면 추천

### 4. Spring Boot와 FastAPI 연동
- Spring Boot: 프론트엔드 요청 처리, DB 관리
- FastAPI: AI/ML 추론, 벡터 검색
- RestTemplate을 통한 HTTP 통신

### 5. 2단계 저장 프로세스
- **Step 1 (analyze)**: DB 저장 없이 프리뷰만 제공
- **Step 2 (save)**: 사용자 확인 후 최종 저장
### 6. 멀티 에이전트 챗봇 구조
- **Top Agent**: 질문 유형 분류 (도면 찾기 vs 법/조례 조회)
- **Sub Agents**: 각 유형별 전문 처리 로직
- **Answer Generator**: LLM 기반 답변 생성 (향후 sLLM 전환)
- **Verification Agent**: 답변 검증 및 품질 보증
- **학습 데이터 수집**: LLM 사용 중 대화 로그 수집 → sLLM 학습 데이터 구축
- **학습 데이터 수집**: LLM 사용 중 대화 로그 수집 → sLLM 학습 데이터 구축

---

## 🛠️ 개발 환경

### Backend (Spring Boot)
- **JDK**: Java 21
- **빌드 도구**: Maven
- **실행 포트**: 8080
- **실행 방법**:
  ```bash
  cd Backend
  mvn spring-boot:run
  ```

### Python Server (FastAPI)
- **Python**: 3.8+
- **실행 포트**: 8000
- **실행 방법**:
  ```bash
  cd python
  pip install -r requirements.txt
  python main.py
  # 또는
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
  ```

### Frontend (React)
- **Node.js**: 16+
- **패키지 매니저**: npm
- **실행 포트**: 3000 (개발), 5173 (Vite 기본)
- **실행 방법**:
  ```bash
  cd final-frontend-ts
  npm install
  npm run dev
  ```

### Database
- **PostgreSQL**: 13+
- **Extensions**: pgvector

---

## 📝 중요 데이터 형식

### topology_graph.json
```json
{
  "nodes": [
    {
      "id": "room_1",
      "type": "거실",
      "area": 25.5,
      "bbox": [x1, y1, x2, y2]
    }
  ],
  "edges": [
    {
      "from": "room_1",
      "to": "room_2",
      "connection_type": "door"
    }
  ]
}
```

### analysis_result.json
```json
{
  "summary": "LLM 생성 도면 요약 텍스트",
  "total_area": 85.2,
  "room_count": 3,
  "bay_count": 2,
  "balcony_ratio": 0.12,
  "room_details": [...]
}
```

### evaluation_result.json
```json
{
  "overall_score": 85,
  "criteria": [
    {
      "name": "채광 및 환기",
      "score": 90,
      "feedback": "LLM 생성 피드백"
    }
  ]
}
```

---

## 🚨 주의사항 및 알려진 이슈

### 1. 포트 충돌
- Spring Boot (8080)와 Python (8000) 포트가 동시에 사용 중이어야 함
- 포트 충돌 시 서비스가 정상 작동하지 않음

### 2. CV 모델 파일
- `python/CV/cv_inference/models/` 경로에 `.pt` 모델 파일이 있어야 함
- 모델 파일이 없으면 추론 실패

### 3. OpenAI API Key
- `.env` 파일에 `OPENAI_API_KEY` 설정 필요
- API Key가 없으면 LLM 기반 요약/평가 기능 동작 안 함

### 4. 이미지 용량
- 대용량 이미지 업로드 시 분석 시간이 오래 걸릴 수 있음
- 권장 크기: 2000x2000 픽셀 이하

### 5. CORS 설정
- 프론트엔드와 백엔드 간 CORS 설정 확인 필요
- `FloorPlanController`에 `@CrossOrigin(origins = "http://localhost:3000")` 설정됨

---

## 💡 AI 어시스턴트를 위한 가이드

### 질문 유형별 대응

#### 1. "이 프로젝트는 무엇을 하는 건가요?"
→ "도면 자산화 시스템", "건축사 보조 시스템", "4가지 핵심 기능" 설명

#### 2. "어떤 기술 스택을 사용하나요?"
→ React + Spring Boot + FastAPI + PostgreSQL + pgvector + CV 모델 + LLM 설명

#### 3. "백엔드 구조가 어떻게 되나요?"
→ Spring Boot (8080) ↔ FastAPI (8000) 연동 구조 설명

#### 4. "도면 분석은 어떻게 동작하나요?"
→ CV 파이프라인 5단계 (OBJ → OCR → STR → SPA → Aggregator → LLM) 설명

#### 5. "Frontend 구조가 어떻게 되나요?"
→ `features/` 기반 모듈 구조, `floor-plan/`, `chat/`, `auth/` 등 설명

#### 6. "Python 서버는 무슨 역할을 하나요?"
→ AI/ML 추론 전담, FastAPI 기반, CV 파이프라인 + RAG 평가 설명

#### 7. "데이터베이스 구조는 어떻게 되나요?"
→ FloorPlan, Land, Regulation, Vector 테이블 설명

#### 10. "새로운 기능을 추가하고 싶습니다"
#### 11. "챗봇 구조가 어떻게 되나요?"
→ 멀티 에이전트 구조 설명:
  - **Top Agent**: 질문 분류 (LLM)
  - **도면 찾기**: pgvector 유사도 검색
  - **법/조례 조회**: 주소 기반 법규 검색
  - **답변 생성**: LLM (향후 sLLM 전환)
  - **답변 검증**: Verification Agent로 답변 품질 보증
  - **법/조례 조회**: 주소 기반 법규 검색
  - **답변 생성**: LLM (향후 sLLM 전환)

#### 12. "sLLM은 언제 적용하나요?"
→ 단계별 계획:
  1. **현재**: LLM 사용하여 챗봇 운영
  2. **데이터 수집**: 대화 로그 및 답변 품질 평가
  3. **학습 데이터 구축**: 수집된 데이터로 파인튜닝 데이터셋 생성
  4. **sLLM 학습**: 파인튜닝 수행
  5. **성능 검증**: LLM vs sLLM 성능 비교
  6. **배포**: 검증 완료 후 sLLM으로 전환

#### 9. "에러가 발생했습니다"
→ 로그 확인, 포트 충돌, 모델 파일 존재 여부, API Key 설정 등 체크

#### 10. "새로운 기능을 추가하고 싶습니다"
→ Frontend, Backend, Python 중 어느 레이어에 추가할지 먼저 판단

### 주요 파일 경로 참조

**컨트롤러**:
- `Backend/src/main/java/com/example/skn20/controller/FloorPlanController.java`
- `Backend/src/main/java/com/example/skn20/controller/ChatbotController.java`

**Python 서버**:
- `python/main.py` (FastAPI 앱)
- `python/services/cv_service.py` (CV 파이프라인)
- `python/services/rag_service.py` (RAG 평가)

**Frontend**:
- `final-frontend-ts/src/features/floor-plan/FileUploadPage.tsx` (도면 업로드)
- `final-frontend-ts/src/features/chat/ChatPage.tsx` (채팅)

**CV 파이프라인**:
- `python/CV/cv_inference/pipeline.py` (메인 파이프라인)
- `python/CV/cv_inference/aggregator.py` (결과 통합)

---

## 📚 추가 참고 문서

- `README.md`: 프로젝트 전체 설명
- `SETUP_GUIDE.md`: 설치 및 실행 가이드
- `python/README_API.md`: FastAPI 서버 실행 가이드
- `산출물/`: 주차별 작업 산출물

---

**이 문서는 AI 어시스턴트가 프로젝트를 이해하고 적절한 답변을 제공하기 위해 작성되었습니다.**
**프로젝트 구조나 주요 기능이 변경되면 이 문서도 함께 업데이트해주세요.**
