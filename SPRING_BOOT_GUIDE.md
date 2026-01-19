# 스프링 부트 프로젝트 가이드

## 📁 프로젝트 구조

```
SKN20-final/
├── src/
│   ├── main/
│   │   ├── java/
│   │   │   └── com/
│   │   │       └── example/
│   │   │           └── skn20/
│   │   │               ├── Skn20Application.java (메인 실행 클래스)
│   │   │               ├── controller/        (REST API 컨트롤러)
│   │   │               ├── service/           (비즈니스 로직)
│   │   │               ├── repository/        (데이터 접근 계층)
│   │   │               └── model/             (엔티티, DTO)
│   │   └── resources/
│   │       ├── application.properties (설정 파일)
│   │       ├── static/                (정적 리소스)
│   │       └── templates/             (HTML 템플릿)
│   └── test/
│       └── java/                      (테스트 코드)
├── pom.xml                            (Maven 설정)
└── .gitignore
```

## 🚀 실행 방법

### 1. Maven으로 실행
```bash
mvnw spring-boot:run
```

### 2. JAR 파일로 실행
```bash
mvnw clean package
java -jar target/skn20-final-0.0.1-SNAPSHOT.jar
```

### 3. IDE에서 실행
- `Skn20Application.java` 파일을 열고 Run 버튼 클릭

## 🔧 Spring Initializr 사용 방법

웹에서 직접 프로젝트를 생성하려면:

1. **https://start.spring.io** 접속
2. 설정 선택:
   - Project: **Maven**
   - Language: **Java**
   - Spring Boot: **3.2.1**
   - Java: **17**
3. Dependencies 추가:
   - Spring Web
   - Spring Data JPA
   - H2 Database
   - Lombok
4. **Generate** 버튼 클릭하여 다운로드

## 📝 주요 의존성

- **Spring Web**: REST API 개발
- **Spring Data JPA**: 데이터베이스 연동
- **H2 Database**: 내장형 데이터베이스 (개발용)
- **Lombok**: 보일러플레이트 코드 자동 생성

## 🌐 테스트

서버 실행 후 브라우저에서 접속:
- API 테스트: http://localhost:8080/api/hello
- H2 Console: http://localhost:8080/h2-console
  - JDBC URL: `jdbc:h2:mem:testdb`
  - Username: `sa`
  - Password: (빈칸)

## 💡 다음 단계

1. **엔티티 생성**: `model` 패키지에 데이터 모델 추가
2. **Repository 생성**: JPA Repository 인터페이스 작성
3. **Service 생성**: 비즈니스 로직 구현
4. **Controller 생성**: REST API 엔드포인트 추가

## 🔗 유용한 링크

- [Spring Boot 공식 문서](https://spring.io/projects/spring-boot)
- [Spring Initializr](https://start.spring.io)
- [Spring Guides](https://spring.io/guides)
