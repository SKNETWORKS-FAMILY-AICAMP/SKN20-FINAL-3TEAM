# ARAE - 건축 도면 검색 서비스 프론트엔드

React + TypeScript + Vite 기반의 건축 도면 검색 서비스 UI 프로젝트입니다.

## 프로젝트 구조

```
src/
├── features/                    # 기능별 모듈
│   ├── auth/                    # 인증 기능
│   │   ├── login/
│   │   │   ├── Login.tsx
│   │   │   └── Login.module.css
│   │   ├── signup/
│   │   │   ├── Signup.tsx
│   │   │   └── Signup.module.css
│   │   ├── password-reset/
│   │   │   ├── PasswordReset.tsx
│   │   │   └── PasswordReset.module.css
│   │   ├── api/                 # Auth API
│   │   ├── types/               # Auth 타입
│   │   ├── AuthLayout.tsx
│   │   ├── AuthLayout.module.css
│   │   ├── AuthPage.tsx
│   │   └── index.ts
│   │
│   ├── chat/                    # 채팅 기능
│   │   ├── ChatPage.tsx
│   │   ├── ChatPage.module.css
│   │   ├── ChatMessage.tsx
│   │   ├── ChatMessage.module.css
│   │   ├── ChatSidebar.tsx
│   │   ├── ChatSidebar.module.css
│   │   ├── api/
│   │   ├── types/
│   │   ├── data/
│   │   └── index.ts
│   │
│   ├── floor-plan/              # 도면 업로드 기능
│   │   ├── FileUploadPage.tsx
│   │   ├── FileUploadPage.module.css
│   │   ├── types/
│   │   ├── data/
│   │   └── index.ts
│   │
│   └── profile/                 # 프로필 기능
│       ├── ProfilePage.tsx
│       ├── ProfilePage.module.css
│       ├── types/
│       ├── data/
│       └── index.ts
│
├── shared/                      # 공유 모듈
│   ├── components/              # 공통 컴포넌트 (Button, Input, Logo 등)
│   ├── contexts/                # Context (Theme)
│   ├── styles/                  # 색상, 글로벌 스타일
│   ├── utils/                   # 유틸리티 (tokenManager)
│   └── api/                     # Axios 인스턴스
│
├── App.tsx                      # 라우팅 설정
└── main.tsx                     # 엔트리 포인트
```

## 시작하기

```bash
# 의존성 설치
npm install

# 개발 서버 실행
npm run dev

# 빌드
npm run build
```

브라우저에서 `http://localhost:5173` 접속

## 주요 기능

### 인증 시스템
- 로그인/회원가입
- 이메일 인증
- 비밀번호 찾기 및 재설정

### 채팅 인터페이스
- 도면 검색 챗봇 UI
- 채팅 세션 관리 (생성, 삭제, 전환)
- 메시지 히스토리

### 도면 업로드
- 드래그 앤 드롭 파일 업로드
- AI 자동 분석
- JSON 결과 출력

### 사용자 관리
- 프로필 조회 및 수정
- 로그아웃

## 페이지 라우트

| 경로 | 페이지 |
|------|--------|
| `/` | 로그인 (리다이렉트) |
| `/login` | 로그인 |
| `/main` | 메인 채팅 |
| `/profile` | 프로필 |
| `/file-upload` | 도면 업로드 |

---

## API 연동 가이드

### 환경 설정

`.env.development` 파일:
```env
VITE_API_BASE_URL=http://localhost:8080
```

### 사용 예시

```typescript
// 로그인
import { login } from '@/features/auth/api';

const response = await login({
  email: 'user@example.com',
  password: 'password123',
});

// 회원가입
import { signup, checkEmail, sendVerificationMail } from '@/features/auth/api';

await checkEmail({ email: 'user@example.com' });
await sendVerificationMail({ email: 'user@example.com' });
await signup({
  email: 'user@example.com',
  pw: 'password123',
  name: '홍길동',
  phonenumber: '01012345678',
});

// 사용자 정보 조회
import { getCurrentUser, updateProfile } from '@/features/auth/api';

const userInfo = await getCurrentUser();
await updateProfile({ name: '김철수', phonenumber: '01098765432' });

// 로그아웃
import { logout } from '@/shared/utils';

logout();
```

### 인증 처리

JWT 토큰이 `localStorage`에 자동 저장되며, 모든 API 요청에 자동 포함됩니다.

```typescript
// shared/api/axios.ts에서 자동 처리
Authorization: `Bearer ${token}`
```

### API 명세

| Method | URL | 설명 | 인증 |
|--------|-----|------|------|
| POST | `/api/auth/check-email` | 이메일 중복 검사 | - |
| POST | `/api/auth/signup` | 회원가입 | - |
| POST | `/api/auth/login` | 로그인 | - |
| GET | `/api/auth/me` | 현재 사용자 정보 | O |
| POST | `/api/auth/profile` | 프로필 수정 | O |
| POST | `/api/auth/change-password` | 비밀번호 변경 | - |
| POST | `/api/auth/mailSend` | 인증 메일 발송 | - |
| GET | `/api/auth/mailCheck` | 인증번호 확인 | - |

---

## 기술 스택

- **React 19** + **TypeScript**
- **Vite** - 빌드 도구
- **React Router DOM** - 라우팅
- **Axios** - HTTP 클라이언트
- **CSS Modules** - 스타일링

## 라이선스

SKN 4팀 최종 프로젝트
