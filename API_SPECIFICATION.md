# API 명세서

> 건축 도면 분석 및 RAG 챗봇 시스템 API 문서

---

## 목차

1. [시스템 아키텍처](#1-시스템-아키텍처)
2. [인증 API](#2-인증-api)
3. [도면 분석 API](#3-도면-분석-api)
4. [챗봇 API](#4-챗봇-api)
5. [Python AI 서버 API](#5-python-ai-서버-api)
6. [JWT 인증 흐름](#6-jwt-인증-흐름)
7. [에러 코드](#7-에러-코드)
8. [데이터 모델](#8-데이터-모델)
9. [서버 간 통신 상세](#9-서버-간-통신-상세)
10. [데이터 저장 위치](#10-데이터-저장-위치)
11. [이미지 업로드/조회 흐름](#11-이미지-업로드조회-흐름)
12. [시스템 설정값](#12-시스템-설정값)

---

## 1. 시스템 아키텍처

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Frontend      │      │    Backend      │      │  Python AI      │
│   React:3000    │─────▶│  Spring:8080    │─────▶│  FastAPI:8000   │
└─────────────────┘      └─────────────────┘      └─────────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  PostgreSQL     │
                         │     :5432       │
                         └─────────────────┘
```

### 서버 정보

| 서버 | 포트 | 기술 스택 |
|------|------|-----------|
| Frontend | 3000 / 5173 | React + TypeScript + Vite |
| Backend | 8080 | Spring Boot 3.x + JPA |
| AI Server | 8000 | FastAPI + LangChain |
| Database | 5432 | PostgreSQL + pgvector |

### Base URL

```
개발 환경: http://localhost:8080
AI 서버:   http://localhost:8000
```

---

## 2. 인증 API

### 2.1 로그인

사용자 인증 후 JWT 토큰 발급

```http
POST /api/auth/login
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| email | String | ✅ | 사용자 이메일 |
| password | String | ✅ | 비밀번호 |

**Response**

```json
{
  "token": "eyJhbGciOiJIUzI1NiJ9...",
  "type": "Bearer",
  "email": "user@example.com",
  "username": "홍길동",
  "role": "USER"
}
```

**Status Codes**

| 코드 | 설명 |
|------|------|
| 200 | 로그인 성공 |
| 401 | 이메일 또는 비밀번호 불일치 |
| 500 | 서버 오류 |

---

### 2.2 회원가입

새 사용자 등록

```http
POST /api/auth/signup
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| email | String | ✅ | 사용자 이메일 |
| pw | String | ✅ | 비밀번호 |
| name | String | ✅ | 사용자 이름 |
| phonenumber | String | ✅ | 전화번호 |

**Response**

```json
{
  "success": true,
  "message": "회원가입 성공"
}
```

**Status Codes**

| 코드 | 설명 |
|------|------|
| 200 | 회원가입 성공 |
| 400 | 이미 존재하는 이메일 |
| 500 | 서버 오류 |

---

### 2.3 이메일 중복 확인

```http
POST /api/auth/check-email
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| email | String | ✅ | 확인할 이메일 |

**Response**

```json
"사용 가능한 이메일입니다"
// 또는
"이미 사용 중인 이메일입니다"
```

---

### 2.4 현재 사용자 정보 조회

🔒 **인증 필요**

```http
GET /api/auth/me
```

**Headers**

```
Authorization: Bearer {token}
```

**Response**

```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "홍길동",
  "phonenumber": "01012345678",
  "role": "USER",
  "createAt": "2024-01-15T10:30:00",
  "updateAt": "2024-01-15T10:30:00"
}
```

---

### 2.5 프로필 수정

🔒 **인증 필요**

```http
POST /api/auth/profile
```

**Headers**

```
Authorization: Bearer {token}
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| name | String | ✅ | 새 이름 |
| phonenumber | String | ✅ | 새 전화번호 |

**Response**

```json
{
  "success": true,
  "message": "프로필 수정 성공"
}
```

---

### 2.6 비밀번호 변경

🔒 **인증 필요**

```http
POST /api/auth/change-password
```

**Headers**

```
Authorization: Bearer {token}
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| email | String | ✅ | 사용자 이메일 |
| newPassword | String | ✅ | 새 비밀번호 |

**Response**

```json
{
  "success": true,
  "message": "비밀번호 변경 성공"
}
```

---

### 2.7 인증 메일 발송

```http
POST /api/auth/mailSend
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| email | String | ✅ | 인증받을 이메일 |

**Response**

```json
{
  "success": true,
  "message": "인증 메일이 발송되었습니다"
}
```

---

### 2.8 인증번호 확인

```http
GET /api/auth/mailCheck
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| mail | String | ✅ | 이메일 |
| userNumber | String | ✅ | 입력한 인증번호 |

**Response**

```json
{
  "success": true,
  "message": "인증 성공"
}
```

---

## 3. 도면 분석 API

### 3.1 도면 분석 (프리뷰)

도면 이미지를 AI로 분석하여 결과 반환 (DB 저장 X)

```http
POST /api/floorplan/analyze
Content-Type: multipart/form-data
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| file | File | ✅ | 도면 이미지 (PNG, JPG) |

**Response**

```json
{
  "topologyJson": "{\"spaces\": [...], \"connections\": [...]}",
  "topologyImageUrl": "data:image/png;base64,iVBORw0KGgo...",
  "llmAnalysisJson": "{\"summary\": \"...\", \"compliance\": {...}}",
  "windowlessRatio": 0.15,
  "hasSpecialSpace": true,
  "bayCount": 3,
  "balconyRatio": 0.12,
  "livingRoomRatio": 0.25,
  "bathroomRatio": 0.08,
  "kitchenRatio": 0.10,
  "roomCount": 5,
  "complianceGrade": "양호",
  "ventilationQuality": "우수",
  "hasEtcSpace": false,
  "structureType": "아파트",
  "bathroomCount": 2,
  "analysisDescription": "본 도면은 3베이 구조의...",
  "embedding": [0.123, -0.456, ...]
}
```

**Response 필드 설명**

| 필드 | 타입 | 설명 |
|------|------|------|
| topologyJson | String | 공간 위상 그래프 JSON |
| topologyImageUrl | String | 위상 그래프 이미지 (Base64) |
| llmAnalysisJson | String | LLM 분석 결과 전체 |
| windowlessRatio | Float | 무창실 비율 |
| hasSpecialSpace | Boolean | 특수 공간 존재 여부 |
| bayCount | Integer | 베이 개수 |
| balconyRatio | Float | 발코니 비율 |
| livingRoomRatio | Float | 거실 비율 |
| bathroomRatio | Float | 욕실 비율 |
| kitchenRatio | Float | 주방 비율 |
| roomCount | Integer | 방 개수 |
| complianceGrade | String | 법적 준수 등급 |
| ventilationQuality | String | 환기 품질 |
| hasEtcSpace | Boolean | 기타 공간 존재 여부 |
| structureType | String | 구조 타입 |
| bathroomCount | Integer | 욕실 개수 |
| analysisDescription | String | 상세 분석 설명 |
| embedding | Float[] | 임베딩 벡터 (512차원) |

**Status Codes**

| 코드 | 설명 |
|------|------|
| 200 | 분석 성공 |
| 400 | 파일 없음 또는 잘못된 형식 |
| 500 | AI 서버 오류 |

---

### 3.2 도면 저장

🔒 **인증 필요**

분석된 도면을 DB에 저장

```http
POST /api/floorplan/save
Content-Type: multipart/form-data
Authorization: Bearer {token}
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| file | File | ✅ | 도면 이미지 |
| name | String | ✅ | 도면 이름 |
| assessmentJson | String | ✅ | LLM 분석 JSON (llmAnalysisJson) |

**Response**

```json
{
  "floorplanId": 1,
  "analysisId": 1,
  "message": "저장 성공"
}
```

**Status Codes**

| 코드 | 설명 |
|------|------|
| 200 | 저장 성공 |
| 401 | 인증 실패 |
| 500 | 저장 실패 |

---

## 4. 챗봇 API

### 4.1 챗봇 질의응답

⭕ **인증 선택** (인증 시 기록 저장)

```http
POST /api/chatbot/chat
```

**Headers** (선택)

```
Authorization: Bearer {token}
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| chatRoomId | Long | ❌ | 채팅방 ID (없으면 새 방 생성) |
| question | String | ✅ | 질문 내용 |

**Response**

```json
{
  "answer": "건축법에 따르면...",
  "chatRoomId": 123
}
```

---

### 4.2 채팅방 목록 조회

🔒 **인증 필요**

```http
POST /api/chatbot/sessionuser
Authorization: Bearer {token}
```

**Response**

```json
[
  {
    "id": 123,
    "name": "건축법규 문의",
    "createdAt": "2024-01-15T10:30:00"
  },
  {
    "id": 124,
    "name": "도면 분석 질문",
    "createdAt": "2024-01-15T11:00:00"
  }
]
```

---

### 4.3 채팅 기록 조회

🔒 **인증 필요**

```http
POST /api/chatbot/roomhistory
Authorization: Bearer {token}
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| chatRoomId | Long | ✅ | 채팅방 ID |

**Response**

```json
[
  {
    "id": 1,
    "question": "건축법규란?",
    "answer": "건축법규는...",
    "createdAt": "2024-01-15T10:30:00"
  },
  {
    "id": 2,
    "question": "채광 기준은?",
    "answer": "채광 기준은...",
    "createdAt": "2024-01-15T10:31:00"
  }
]
```

---

### 4.4 채팅방 이름 수정

🔒 **인증 필요**

```http
POST /api/chatbot/editroomname
Authorization: Bearer {token}
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| chatRoomId | Long | ✅ | 채팅방 ID |
| newName | String | ✅ | 새 이름 |

**Response**

```json
"success"
```

---

### 4.5 채팅방 삭제

🔒 **인증 필요**

```http
POST /api/chatbot/deleteroom
Authorization: Bearer {token}
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| chatRoomId | Long | ✅ | 채팅방 ID |

**Response**

```json
"success"
```

---

### 4.6 전체 채팅방 삭제

🔒 **인증 필요**

```http
POST /api/chatbot/deleteallrooms
Authorization: Bearer {token}
```

**Response**

```json
"success"
```

---

## 5. Python AI 서버 API

> Base URL: `http://localhost:8000`

### 5.1 도면 분석

```http
POST /analyze
Content-Type: multipart/form-data
```

**Request**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| file | File | ✅ | 도면 이미지 |

**Response**

```json
{
  "topology_json": "{...}",
  "topology_image_url": "data:image/png;base64,...",
  "llm_analysis_json": "{...}"
}
```

---

### 5.2 메타데이터 생성

```http
POST /generate-metadata
Content-Type: application/json
```

**Request**

```json
{
  "llm_analysis_json": "{...}"
}
```

**Response**

```json
{
  "document_id": "uuid",
  "metadata": {
    "windowless_ratio": 0.15,
    "bay_count": 3,
    ...
  },
  "document": "본 도면은 3베이 구조의...",
  "embedding": [0.123, -0.456, ...]
}
```

---

### 5.3 RAG 챗봇 질의

```http
POST /ask
Content-Type: application/json
```

**Request**

```json
{
  "email": "user@example.com",
  "question": "건축법규에서 채광 기준은?"
}
```

**Response**

```json
{
  "summaryTitle": "건축법규 채광 기준",
  "answer": "건축법 시행령 제51조에 따르면..."
}
```

---

### 5.4 헬스 체크

```http
GET /health
```

**Response**

```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## 6. JWT 인증 흐름

### 6.1 토큰 설정

| 항목 | 값 |
|------|-----|
| 알고리즘 | HS256 |
| 만료 시간 | 24시간 |
| 저장 위치 | localStorage / sessionStorage |

### 6.2 인증 흐름도

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              로그인 흐름                                  │
└──────────────────────────────────────────────────────────────────────────┘

  Frontend                         Backend                         Database
     │                               │                                │
     │  1. POST /api/auth/login      │                                │
     │  { email, password }          │                                │
     │──────────────────────────────▶│                                │
     │                               │  2. SELECT * FROM users        │
     │                               │     WHERE email = ?            │
     │                               │───────────────────────────────▶│
     │                               │                                │
     │                               │  3. User 정보 반환              │
     │                               │◀───────────────────────────────│
     │                               │                                │
     │                               │  4. BCrypt.matches(pw, hash)   │
     │                               │  5. JwtUtil.generateToken()    │
     │                               │                                │
     │  6. { token, email, ... }     │                                │
     │◀──────────────────────────────│                                │
     │                               │                                │
     │  7. localStorage.setItem()    │                                │
     │                               │                                │


┌──────────────────────────────────────────────────────────────────────────┐
│                            API 요청 흐름                                  │
└──────────────────────────────────────────────────────────────────────────┘

  Frontend                         Backend                         Database
     │                               │                                │
     │  1. GET /api/auth/me          │                                │
     │  Authorization: Bearer xxx    │                                │
     │──────────────────────────────▶│                                │
     │                               │                                │
     │                               │  2. JwtAuthenticationFilter    │
     │                               │     - 토큰 추출                 │
     │                               │     - 서명 검증                 │
     │                               │     - 만료 확인                 │
     │                               │                                │
     │                               │  3. 유효하면 → Controller 실행  │
     │                               │     무효하면 → 401 반환         │
     │                               │                                │
     │  4. Response                  │                                │
     │◀──────────────────────────────│                                │
     │                               │                                │
```

### 6.3 토큰 저장 전략

```javascript
// rememberMe = true (자동 로그인)
localStorage.setItem('auth_token', token);

// rememberMe = false (브라우저 종료 시 삭제)
sessionStorage.setItem('auth_token', token);
```

### 6.4 Axios 인터셉터 설정

```javascript
// Request 인터셉터: 토큰 자동 추가
axios.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response 인터셉터: 401 처리
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      removeToken();
      // 로그인 페이지로 리다이렉트
    }
    return Promise.reject(error);
  }
);
```

---

## 7. 에러 코드

### 7.1 HTTP 상태 코드

| 코드 | 설명 | 대응 방법 |
|------|------|----------|
| 200 | 성공 | - |
| 400 | 잘못된 요청 | 파라미터 확인 |
| 401 | 인증 실패 | 토큰 갱신 또는 재로그인 |
| 403 | 권한 없음 | 권한 확인 |
| 404 | 리소스 없음 | URL 확인 |
| 500 | 서버 오류 | 서버 로그 확인 |

### 7.2 에러 응답 형식

```json
{
  "success": false,
  "message": "에러 메시지",
  "error": "상세 오류 (개발 환경)"
}
```

---

## 8. 데이터 모델

### 8.1 User

```sql
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  pw VARCHAR(255) NOT NULL,
  name VARCHAR(100),
  phonenumber VARCHAR(20),
  role VARCHAR(20) DEFAULT 'USER',
  create_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  update_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 8.2 FloorPlan

```sql
CREATE TABLE floorplan (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT REFERENCES users(id),
  created_at TIMESTAMP NOT NULL,
  name VARCHAR(255),
  image_url VARCHAR(500),
  assessment_json TEXT
);
```

### 8.3 FloorplanAnalysis

```sql
CREATE TABLE floorplan_analysis (
  id BIGSERIAL PRIMARY KEY,
  floorplan_id BIGINT UNIQUE REFERENCES floorplan(id),
  windowless_ratio FLOAT,
  has_special_space BOOLEAN,
  bay_count INTEGER,
  balcony_ratio FLOAT,
  living_room_ratio FLOAT,
  bathroom_ratio FLOAT,
  kitchen_ratio FLOAT,
  room_count INTEGER,
  compliance_grade VARCHAR(50),
  ventilation_quality VARCHAR(50),
  has_etc_space BOOLEAN,
  structure_type VARCHAR(50),
  bathroom_count INTEGER,
  analysis_description TEXT,
  embedding vector(512)  -- pgvector 확장 필요
);
```

### 8.4 ChatRoom

```sql
CREATE TABLE chatroom (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT REFERENCES users(id),
  name TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 8.5 ChatHistory

```sql
CREATE TABLE chat_history (
  id BIGSERIAL PRIMARY KEY,
  chatroom_id BIGINT REFERENCES chatroom(id),
  question TEXT,
  answer TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 9. 서버 간 통신 상세

### 9.1 통신 구간별 상세

| 구간 | URL | 프로토콜 | Content-Type | 인증 방식 |
|------|-----|----------|--------------|----------|
| **프론트 → 백엔드** | `http://localhost:8080/api/*` | HTTP | `application/json`, `multipart/form-data` | JWT Bearer Token |
| **백엔드 → Python AI** | `http://localhost:8000/*` | HTTP | `application/json`, `multipart/form-data` | 없음 (내부망) |
| **백엔드 → PostgreSQL** | `jdbc:postgresql://localhost:5432/arae` | TCP/IP | SQL | username/password |
| **백엔드 → 이미지 저장** | 로컬 파일 시스템 | 파일 I/O | Binary | 없음 |

### 9.2 프론트엔드 → 백엔드

```
┌─────────────────────────────────────────────────────────────────┐
│  구간: Frontend (React) → Backend (Spring Boot)                  │
├─────────────────────────────────────────────────────────────────┤
│  Base URL    : http://localhost:8080                            │
│  프로토콜     : HTTP (개발) / HTTPS (프로덕션)                    │
│  인증 방식    : JWT Bearer Token (Authorization 헤더)            │
│  타임아웃     : 600초 (10분) - CV 분석 시간 고려                  │
├─────────────────────────────────────────────────────────────────┤
│  Content-Type:                                                  │
│  - JSON 요청      : application/json                            │
│  - 파일 업로드    : multipart/form-data                         │
│  - 폼 파라미터    : application/x-www-form-urlencoded           │
└─────────────────────────────────────────────────────────────────┘
```

### 9.3 백엔드 → Python AI 서버

```
┌─────────────────────────────────────────────────────────────────┐
│  구간: Backend (Spring Boot) → AI Server (FastAPI)              │
├─────────────────────────────────────────────────────────────────┤
│  Base URL    : http://localhost:8000                            │
│  프로토콜     : HTTP (내부망 통신)                                │
│  인증 방식    : 없음 (내부 서버 간 통신)                          │
│  연결 타임아웃 : 30초                                            │
│  읽기 타임아웃 : 5분 (300초) - CV 모델 처리 시간 고려             │
├─────────────────────────────────────────────────────────────────┤
│  엔드포인트:                                                     │
│  - POST /analyze           : multipart/form-data (이미지 전송)   │
│  - POST /generate-metadata : application/json                   │
│  - POST /ask               : application/json                   │
└─────────────────────────────────────────────────────────────────┘
```

### 9.4 백엔드 → PostgreSQL

```
┌─────────────────────────────────────────────────────────────────┐
│  구간: Backend (Spring Boot) → Database (PostgreSQL)            │
├─────────────────────────────────────────────────────────────────┤
│  JDBC URL    : jdbc:postgresql://localhost:5432/arae            │
│  프로토콜     : TCP/IP                                           │
│  포트        : 5432                                              │
│  인증 방식    : username/password                                │
│  드라이버     : org.postgresql.Driver                            │
├─────────────────────────────────────────────────────────────────┤
│  특이사항:                                                       │
│  - pgvector 확장 사용 (임베딩 벡터 저장)                          │
│  - DDL Auto: update (스키마 자동 업데이트)                        │
│  - Batch Size: 10                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. 데이터 저장 위치

### 10.1 저장 위치 요약

| 데이터 | 저장 위치 | 형식 | 비고 |
|--------|-----------|------|------|
| **JWT Access Token** | localStorage / sessionStorage | JWT 문자열 | rememberMe 설정에 따라 결정 |
| **Refresh Token** | ❌ 미구현 | - | 현재 사용 안함 |
| **사용자 정보 (프론트)** | localStorage / sessionStorage | JSON | `user_info` 키 |
| **사용자 정보 (백엔드)** | PostgreSQL `users` 테이블 | Row | BCrypt 암호화 |
| **도면 이미지 파일** | 로컬 파일 시스템 | PNG/JPG | `Backend/src/main/resources/image/floorplan/` |
| **도면 이미지 URL** | PostgreSQL `floorplan.image_url` | String | 상대 경로 저장 |
| **AI 분석 JSON** | PostgreSQL `floorplan.assessment_json` | TEXT | llmAnalysisJson 전체 |
| **13개 분석 지표** | PostgreSQL `floorplan_analysis` 테이블 | 각 컬럼 | 개별 필드로 저장 |
| **임베딩 벡터** | PostgreSQL `floorplan_analysis.embedding` | vector(512) | pgvector 타입 |
| **채팅 기록** | PostgreSQL `chat_history` 테이블 | TEXT | question, answer 컬럼 |

### 10.2 프론트엔드 저장소

```
┌─────────────────────────────────────────────────────────────────┐
│  localStorage (rememberMe = true)                               │
├─────────────────────────────────────────────────────────────────┤
│  auth_token   : "eyJhbGciOiJIUzI1NiJ9..."  (JWT)                │
│  user_info    : {"id":1,"email":"...","name":"..."}  (JSON)     │
│  remember_me  : "true"                                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  sessionStorage (rememberMe = false)                            │
├─────────────────────────────────────────────────────────────────┤
│  auth_token   : "eyJhbGciOiJIUzI1NiJ9..."  (JWT)                │
│  user_info    : {"id":1,"email":"...","name":"..."}  (JSON)     │
└─────────────────────────────────────────────────────────────────┘
```

### 10.3 파일 저장 구조

```
Backend/
└── src/main/resources/
    └── image/
        └── floorplan/
            ├── 1_1707123456789_floor1.png     # {userId}_{timestamp}_{filename}
            ├── 1_1707123456790_floor2.jpg
            └── 2_1707123456791_myplan.png
```

---

## 11. 이미지 업로드/조회 흐름

### 11.1 이미지 업로드 흐름

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           이미지 업로드 전체 흐름                               │
└──────────────────────────────────────────────────────────────────────────────┘

1. 프론트엔드: 파일 선택
   ┌─────────────────────────────────────────────────────────────────┐
   │  <input type="file" accept=".jpg,.jpeg,.png" />                 │
   │                                                                 │
   │  const formData = new FormData();                               │
   │  formData.append('file', selectedFile);                         │
   └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
2. API 요청 (axios)
   ┌─────────────────────────────────────────────────────────────────┐
   │  POST /api/floorplan/analyze                                    │
   │  Content-Type: multipart/form-data                              │
   │  Body: file=[이미지 바이너리]                                    │
   └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
3. 백엔드: 파일 수신 (FloorPlanController.java)
   ┌─────────────────────────────────────────────────────────────────┐
   │  @PostMapping("/analyze")                                       │
   │  public FloorplanPreviewResponse analyze(                       │
   │      @RequestParam("file") MultipartFile file                   │
   │  )                                                              │
   └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
4. Python AI 서버로 전송 (FloorPlanService.java)
   ┌─────────────────────────────────────────────────────────────────┐
   │  MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();  │
   │  body.add("file", new ByteArrayResource(file.getBytes()));      │
   │                                                                 │
   │  POST http://localhost:8000/analyze                             │
   └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
5. AI 분석 결과 반환 (프리뷰 - DB 저장 X)
   ┌─────────────────────────────────────────────────────────────────┐
   │  {                                                              │
   │    topologyJson: "...",                                         │
   │    topologyImageUrl: "data:image/png;base64,...",               │
   │    llmAnalysisJson: "..."                                       │
   │  }                                                              │
   └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
6. 사용자가 "저장" 클릭 → DB 저장
   ┌─────────────────────────────────────────────────────────────────┐
   │  POST /api/floorplan/save                                       │
   │  - file: 이미지 파일                                             │
   │  - name: 도면 이름                                               │
   │  - assessmentJson: LLM 분석 결과                                 │
   └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
7. 파일 저장 (FloorPlanService.saveImageFile)
   ┌─────────────────────────────────────────────────────────────────┐
   │  저장 경로: Backend/src/main/resources/image/floorplan/         │
   │  파일명: {userId}_{timestamp}_{originalFilename}                 │
   │  예: 1_1707123456789_floorplan.png                              │
   │                                                                 │
   │  DB 저장값: /image/floorplan/1_1707123456789_floorplan.png      │
   └─────────────────────────────────────────────────────────────────┘
```

### 11.2 이미지 조회 흐름

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           이미지 조회 전체 흐름                                │
└──────────────────────────────────────────────────────────────────────────────┘

1. DB에서 이미지 URL 조회
   ┌─────────────────────────────────────────────────────────────────┐
   │  SELECT image_url FROM floorplan WHERE id = ?                   │
   │  결과: /image/floorplan/1_1707123456789_floorplan.png           │
   └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
2. 프론트엔드에서 이미지 표시
   ┌─────────────────────────────────────────────────────────────────┐
   │  const imageUrl = `http://localhost:8080${floorplan.imageUrl}`; │
   │                                                                 │
   │  <img src={imageUrl} alt="도면" />                              │
   │                                                                 │
   │  최종 URL: http://localhost:8080/image/floorplan/1_xxx.png      │
   └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
3. 정적 리소스 서빙 (Spring Boot)
   ┌─────────────────────────────────────────────────────────────────┐
   │  Spring Boot가 /image/** 경로를                                 │
   │  src/main/resources/image/ 폴더에서 서빙                        │
   └─────────────────────────────────────────────────────────────────┘
```

### 11.3 이미지 저장 위치 상세

| 항목 | 값 |
|------|-----|
| **저장 방식** | 로컬 파일 시스템 (S3 미사용) |
| **저장 경로** | `Backend/src/main/resources/image/floorplan/` |
| **파일명 규칙** | `{userId}_{timestamp}_{originalFilename}` |
| **DB 저장값** | 상대 경로 (예: `/image/floorplan/1_xxx.png`) |
| **접근 URL** | `http://localhost:8080/image/floorplan/1_xxx.png` |

---

## 12. 시스템 설정값

### 12.1 타임아웃 설정

| 구간 | 설정 | 값 | 설명 |
|------|------|-----|------|
| **프론트 → 백엔드** | axios timeout | 600초 (10분) | CV 분석 시간 고려 |
| **백엔드 → AI서버** | connectTimeout | 30초 | 연결 대기 시간 |
| **백엔드 → AI서버** | readTimeout | 5분 (300초) | CV 모델 처리 시간 |
| **메일 서버** | connectiontimeout | 5초 | SMTP 연결 |
| **메일 서버** | timeout | 5초 | SMTP 읽기 |
| **메일 서버** | writetimeout | 5초 | SMTP 쓰기 |

### 12.2 파일 업로드 제한

| 항목 | 값 |
|------|-----|
| **최대 파일 크기** | 50MB |
| **최대 요청 크기** | 50MB |
| **허용 확장자** | PNG, JPG, JPEG |

```properties
# application.properties
spring.servlet.multipart.max-file-size=50MB
spring.servlet.multipart.max-request-size=50MB
```

### 12.3 JWT 설정

| 항목 | 값 |
|------|-----|
| **알고리즘** | HS256 (HMAC SHA-256) |
| **만료 시간** | 24시간 (86,400,000ms) |
| **비밀키** | 환경변수로 관리 필요 |
| **Refresh Token** | ❌ 미구현 |

```properties
# application.properties
jwt.secret=skn20-dev-secret-key-please-change-in-production
jwt.expiration=86400000
```

### 12.4 확인 사항 요약

| 질문 | 답변 |
|------|------|
| 도면 이미지 저장 위치? | **로컬 서버** (`Backend/src/main/resources/image/floorplan/`) - S3 미사용 |
| Refresh Token 있음? | **❌ 없음** - Access Token만 사용 (24시간 만료) |
| AI 서버 호출 타임아웃? | **연결 30초, 읽기 5분** (RestTemplateConfig.java) |
| 파일 업로드 용량 제한? | **50MB** (application.properties) |

---

## 부록: API 요약 테이블 (총 20개)

| 영역 | 메서드 | 엔드포인트 | 인증 | 설명 |
|------|--------|-----------|:----:|------|
| **인증** | POST | `/api/auth/login` | ❌ | 로그인 |
| | POST | `/api/auth/signup` | ❌ | 회원가입 |
| | POST | `/api/auth/check-email` | ❌ | 이메일 중복 확인 |
| | GET | `/api/auth/me` | ✅ | 현재 사용자 정보 |
| | POST | `/api/auth/profile` | ✅ | 프로필 수정 |
| | POST | `/api/auth/change-password` | ✅ | 비밀번호 변경 |
| | POST | `/api/auth/mailSend` | ❌ | 인증 메일 발송 |
| | GET | `/api/auth/mailCheck` | ❌ | 인증번호 확인 |
| **도면** | POST | `/api/floorplan/analyze` | ❌ | 도면 분석 |
| | POST | `/api/floorplan/save` | ✅ | 도면 저장 |
| **챗봇** | POST | `/api/chatbot/chat` | ⭕ | 챗봇 질의 |
| | POST | `/api/chatbot/sessionuser` | ✅ | 채팅방 목록 |
| | POST | `/api/chatbot/roomhistory` | ✅ | 채팅 기록 |
| | POST | `/api/chatbot/editroomname` | ✅ | 방 이름 수정 |
| | POST | `/api/chatbot/deleteroom` | ✅ | 채팅방 삭제 |
| | POST | `/api/chatbot/deleteallrooms` | ✅ | 전체 삭제 |
| **AI** | POST | `/analyze` | ❌ | CV+LLM 분석 |
| | POST | `/generate-metadata` | ❌ | 메타데이터 생성 |
| | POST | `/ask` | ❌ | RAG 챗봇 |
| | GET | `/health` | ❌ | 헬스체크 |

> **범례**: ✅ 필수 | ❌ 불필요 | ⭕ 선택적

---

*Last Updated: 2024-02*
