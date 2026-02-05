# SKN20-FINAL 프로젝트 전체 설치 가이드

## 📋 목차
1. [필수 소프트웨어](#1-필수-소프트웨어)
2. [환경 변수 설정](#2-환경-변수-설정)
3. [Backend 설정](#3-backend-설정-spring-boot)
4. [Python 설정](#4-python-설정-fastapi--cv)
5. [Frontend 설정](#5-frontend-설정-react--typescript)
6. [Database 설정](#6-database-설정)
7. [전체 프로젝트 실행](#7-전체-프로젝트-실행)
8. [검증](#8-설치-검증)

---

## 1. 필수 소프트웨어

### 1.1 JDK 21
**Spring Boot 3.2.1 필수 요구사항**

- **다운로드**: [Eclipse Temurin JDK 21](https://adoptium.net/temurin/releases/?version=21)
- **설치 경로 예시**: `C:\Program Files\Java\jdk-21`
- **버전 확인**:
  ```bash
  java -version
  # 출력: openjdk version "21.x.x"
  ```

### 1.2 Maven 3.8+
**Spring Boot 빌드 도구**

- **다운로드**: [Apache Maven](https://maven.apache.org/download.cgi)
- **권장 버전**: 3.9.x
- **설치 경로 예시**: `C:\Program Files\Apache\maven`
- **버전 확인**:
  ```bash
  mvn -version
  # 출력: Apache Maven 3.9.x
  ```

### 1.3 Python 3.9+
**FastAPI 서버 및 CV 파이프라인**

- **다운로드**: [Python 공식 사이트](https://www.python.org/downloads/)
- **권장 버전**: 3.10 또는 3.11
- **설치 시 주의**: "Add Python to PATH" 체크
- **버전 확인**:
  ```bash
  python --version
  # 출력: Python 3.10.x 또는 3.11.x
  ```

### 1.4 Node.js 18+
**React 프론트엔드 빌드**

- **다운로드**: [Node.js LTS](https://nodejs.org/)
- **권장 버전**: 20.x LTS
- **버전 확인**:
  ```bash
  node --version
  # 출력: v20.x.x
  
  npm --version
  # 출력: 10.x.x
  ```

### 1.5 PostgreSQL 14+
**벡터 DB (pgvector 사용)**

- **다운로드**: [PostgreSQL](https://www.postgresql.org/download/)
- **필수 확장**: pgvector
- **설치 후**: pgvector 확장 설치
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```

### 1.6 MySQL 8.0+ (선택)
**Backend 데이터베이스 (H2로도 대체 가능)**

- **다운로드**: [MySQL Community Server](https://dev.mysql.com/downloads/mysql/)
- **개발용으로는 H2 In-Memory DB 사용 가능**

---

## 2. 환경 변수 설정

### Windows 환경 변수 설정

1. **시스템 환경 변수 편집**:
   - `Win + R` → `sysdm.cpl` → 고급 탭 → 환경 변수

2. **시스템 변수 추가**:
   ```
   JAVA_HOME=C:\Program Files\Java\jdk-21
   M2_HOME=C:\Program Files\Apache\maven
   ```

3. **Path 변수에 추가**:
   ```
   %JAVA_HOME%\bin
   %M2_HOME%\bin
   %USERPROFILE%\AppData\Local\Programs\Python\Python311
   %USERPROFILE%\AppData\Local\Programs\Python\Python311\Scripts
   ```

4. **확인**:
   ```bash
   echo %JAVA_HOME%
   echo %M2_HOME%
   ```

---

## 3. Backend 설정 (Spring Boot)

### 3.1 프로젝트 정보
- **Framework**: Spring Boot 3.2.1
- **Java Version**: 21
- **Build Tool**: Maven
- **Port**: 8080 (기본)

### 3.2 빌드 및 실행

```bash
# Backend 디렉토리로 이동
cd Backend

# 의존성 다운로드 및 빌드
mvn clean install

# 애플리케이션 실행
mvn spring-boot:run

# 또는 JAR 파일로 실행
java -jar target/skn20-final-0.0.1-SNAPSHOT.jar
```

### 3.3 데이터베이스 설정

#### H2 Database (개발용 - 기본 설정)
- 별도 설치 불필요
- In-Memory 모드로 자동 실행
- 콘솔: http://localhost:8080/h2-console

#### MySQL (운영용)
`src/main/resources/application.properties` 수정:
```properties
spring.datasource.url=jdbc:mysql://localhost:3306/skn20db
spring.datasource.username=root
spring.datasource.password=yourpassword
spring.jpa.hibernate.ddl-auto=update
```

---

## 4. Python 설정 (FastAPI + CV)

### 4.1 가상환경 생성 (권장)

```bash
# Python 디렉토리로 이동
cd python

# 가상환경 생성
python -m venv venv

# 가상환경 활성화 (Windows)
venv\Scripts\activate

# 가상환경 활성화 (Linux/Mac)
source venv/bin/activate
```

### 4.2 의존성 설치

```bash
# 통합 requirements.txt로 설치
pip install -r requirements.txt

# 또는 개별 설치
pip install --upgrade pip
pip install -r requirements.txt
```

### 4.3 환경 변수 설정

`.env` 파일 생성 (`python/.env`):
```env
# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vectordb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=yourpassword

# FastAPI 설정
API_HOST=0.0.0.0
API_PORT=8000
```

### 4.4 FastAPI 서버 실행

```bash
# Python 디렉토리에서
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

서버 실행 확인: http://localhost:8000/docs

---

## 5. Frontend 설정 (React + TypeScript)

### 5.1 프로젝트 정보
- **Framework**: React 19.2
- **Language**: TypeScript 5.9
- **Build Tool**: Vite 7.2
- **Port**: 5173 (기본)

### 5.2 의존성 설치 및 실행

```bash
# Frontend 디렉토리로 이동
cd final-frontend-ts

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev

# 빌드
npm run build

# 빌드된 파일 미리보기
npm run preview
```

### 5.3 환경 변수 설정

`.env.development` 파일 확인/생성:
```env
VITE_API_URL=http://localhost:8080
VITE_PYTHON_API_URL=http://localhost:8000
```

---

## 6. Database 설정

### 6.1 PostgreSQL + pgvector

```bash
# PostgreSQL 접속
psql -U postgres

# 데이터베이스 생성
CREATE DATABASE vectordb;

# pgvector 확장 설치
\c vectordb
CREATE EXTENSION IF NOT EXISTS vector;

# 테이블 생성 (Python 서비스가 자동 생성할 수도 있음)
```

### 6.2 MySQL (선택사항)

```bash
# MySQL 접속
mysql -u root -p

# 데이터베이스 생성
CREATE DATABASE skn20db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# 사용자 생성 및 권한 부여
CREATE USER 'skn20user'@'localhost' IDENTIFIED BY 'yourpassword';
GRANT ALL PRIVILEGES ON skn20db.* TO 'skn20user'@'localhost';
FLUSH PRIVILEGES;
```

---

## 7. 전체 프로젝트 실행

### 7.1 실행 순서

1. **PostgreSQL 시작**
   ```bash
   # Windows: 서비스에서 PostgreSQL 시작
   # 또는
   pg_ctl -D "C:\Program Files\PostgreSQL\14\data" start
   ```

2. **Backend 실행** (터미널 1)
   ```bash
   cd Backend
   mvn spring-boot:run
   ```
   - 실행 확인: http://localhost:8080

3. **Python FastAPI 실행** (터미널 2)
   ```bash
   cd python
   venv\Scripts\activate
   uvicorn main:app --reload
   ```
   - 실행 확인: http://localhost:8000/docs

4. **Frontend 실행** (터미널 3)
   ```bash
   cd final-frontend-ts
   npm run dev
   ```
   - 실행 확인: http://localhost:5173

### 7.2 포트 요약

| 서비스 | 포트 | URL |
|--------|------|-----|
| Frontend (React) | 5173 | http://localhost:5173 |
| Backend (Spring Boot) | 8080 | http://localhost:8080 |
| Python API (FastAPI) | 8000 | http://localhost:8000 |
| PostgreSQL | 5432 | localhost:5432 |
| MySQL (선택) | 3306 | localhost:3306 |

---

## 8. 설치 검증

### 8.1 소프트웨어 버전 확인

```bash
# Java
java -version
# 기대값: openjdk version "21.x.x"

# Maven
mvn -version
# 기대값: Apache Maven 3.8+ (Java version: 21)

# Python
python --version
# 기대값: Python 3.9+ (권장: 3.10 또는 3.11)

# Node.js
node --version
# 기대값: v18.x.x 이상 (권장: v20.x.x)

# npm
npm --version
# 기대값: 9.x.x 이상
```

### 8.2 서비스 접속 테스트

```bash
# Backend Health Check
curl http://localhost:8080/actuator/health

# Python API Docs
curl http://localhost:8000/docs

# Frontend
# 브라우저에서 http://localhost:5173 접속
```

### 8.3 Database 연결 확인

```bash
# PostgreSQL
psql -U postgres -d vectordb -c "SELECT version();"

# MySQL (선택)
mysql -u root -p -e "SHOW DATABASES;"
```

---

## 9. 문제 해결 (Troubleshooting)

### 9.1 Java 관련

**문제**: `JAVA_HOME is not set`
```bash
# 해결: 환경 변수 확인
echo %JAVA_HOME%
# 설정되어 있지 않으면 위의 "환경 변수 설정" 참조
```

**문제**: `Java version mismatch`
```bash
# 해결: Maven이 올바른 Java 사용하는지 확인
mvn -version
# JAVA_HOME 경로가 JDK 21을 가리키는지 확인
```

### 9.2 Python 관련

**문제**: `ModuleNotFoundError`
```bash
# 해결: 가상환경 활성화 확인 및 재설치
pip install -r requirements.txt --force-reinstall
```

**문제**: PyTorch 설치 실패
```bash
# 해결: CUDA 버전에 맞게 설치
# CPU만: 
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# GPU (CUDA 11.8):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### 9.3 Node.js 관련

**문제**: `npm install` 실패
```bash
# 해결: cache 정리 후 재시도
npm cache clean --force
npm install
```

### 9.4 Database 관련

**문제**: PostgreSQL 연결 실패
```bash
# 해결: 서비스 실행 확인
# Windows: services.msc에서 PostgreSQL 서비스 확인

# 포트 사용 확인
netstat -ano | findstr :5432
```

---

## 10. 추가 도구 (선택사항)

### 10.1 IDE

- **IntelliJ IDEA** (Java/Spring Boot 권장)
- **PyCharm** (Python 개발 권장)
- **VS Code** (전체 프로젝트 통합 개발)
  - 필수 확장:
    - Java Extension Pack
    - Python
    - ESLint
    - Vite

### 10.2 API 테스트

- **Postman** 또는 **Insomnia**
- **FastAPI Swagger UI**: http://localhost:8000/docs (자동 제공)

### 10.3 Database 관리

- **DBeaver** (PostgreSQL, MySQL 통합 관리)
- **pgAdmin** (PostgreSQL 전용)
- **MySQL Workbench** (MySQL 전용)

---

## 📝 체크리스트

실행 전 확인사항:

- [ ] JDK 21 설치 및 JAVA_HOME 설정
- [ ] Maven 3.8+ 설치 및 M2_HOME 설정
- [ ] Python 3.9+ 설치
- [ ] Node.js 18+ 설치
- [ ] PostgreSQL 설치 및 pgvector 확장 설치
- [ ] 모든 환경 변수 설정 완료
- [ ] Backend 빌드 성공 (`mvn clean install`)
- [ ] Python 의존성 설치 완료
- [ ] Frontend 의존성 설치 완료 (`npm install`)
- [ ] .env 파일 설정 (Python, Frontend)
- [ ] Database 생성 및 연결 확인

---

## 🚀 빠른 시작

모든 설치가 완료되었다면:

```bash
# 1. Backend 실행
cd Backend && mvn spring-boot:run

# 2. Python API 실행 (새 터미널)
cd python && venv\Scripts\activate && uvicorn main:app --reload

# 3. Frontend 실행 (새 터미널)
cd final-frontend-ts && npm run dev
```

---

**문의 사항이 있으면 팀원에게 연락하세요!**
