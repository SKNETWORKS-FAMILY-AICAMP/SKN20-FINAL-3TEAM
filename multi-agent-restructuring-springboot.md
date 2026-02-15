# Phase 2: Spring Boot 미들웨어 — 오케스트레이터 연동

> 상위 계획서: `multi-agent-restructuring.md`

---

## 선행 조건

- Phase 1 (Python 백엔드) 완료
- `/orchestrate` 엔드포인트가 `Form` + `File` 방식으로 동작 확인됨

## 완료 조건

- `/api/chatbot/chat` (텍스트) → Python `/orchestrate` 호출 → 답변 반환
- `/api/chatbot/chat` (이미지) → Python `/orchestrate` 이미지 전달 → 답변 반환
- 기존 채팅방 생성/저장 로직 정상 동작

---

## Task Type

- [x] Backend (Spring Boot)

---

## 현재 구조 분석

### ChatbotService.java (현재)

```
프론트 → ChatbotController → ChatbotService.fastapiCommunicate()
                                    │
                                    ▼
                              Python /ask (JSON)
                              Content-Type: application/json
                              Body: {"email": "...", "question": "..."}
```

**문제점:**
- `/ask`를 직접 호출하여 `/orchestrate`를 우회
- 이미지 전송 불가 (JSON 방식)
- `RestTemplate`으로 `application/json` 전송만 지원

### 목표 구조

```
프론트 → ChatbotController → ChatbotService.orchestrate()
                                    │
                                    ▼
                              Python /orchestrate (Form + File)
                              텍스트: multipart/form-data (email, question)
                              이미지: multipart/form-data (email, question, file)
```

---

## Step 2.1: ChatbotService 수정

### 수정 파일: `Backend/src/main/java/com/example/skn20/service/ChatbotService.java`

**변경 내용:**

```java
@Slf4j
@Service
@RequiredArgsConstructor
public class ChatbotService {

    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    // 변경: /ask → /orchestrate
    private final String FASTAPI_ORCHESTRATE_URL = "http://localhost:8000/orchestrate";

    /**
     * 텍스트 전용 (기존 호환)
     */
    public Map<String, String> question2answer(User user, String question) {
        return orchestrate(user, question, null);
    }

    /**
     * 텍스트 + 이미지
     */
    public Map<String, String> question2answerWithImage(
            User user, String question, MultipartFile image) {
        return orchestrate(user, question, image);
    }

    /**
     * Python /orchestrate 호출 (Form + File)
     *
     * 응답 JSON 구조:
     * {
     *   "intent_type": "FLOORPLAN_SEARCH" | "REGULATION_SEARCH" | "FLOORPLAN_IMAGE",
     *   "confidence": 0.95,
     *   "agent_used": "floorplan_search",
     *   "response": {
     *     "summaryTitle": "...",
     *     "answer": "...",
     *     "floorplan_ids": [12, 45] | null
     *   },
     *   "metadata": { ... }
     * }
     */
    private Map<String, String> orchestrate(
            User user, String question, MultipartFile image) {

        Map<String, String> result = new HashMap<>();

        try {
            // 1. 헤더 설정 (multipart/form-data)
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.MULTIPART_FORM_DATA);

            // 2. Form 데이터 구성
            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
            body.add("email", user != null ? user.getEmail() : "anonymous");
            body.add("question", question != null ? question : "");

            // 3. 이미지가 있으면 file 필드 추가
            if (image != null && !image.isEmpty()) {
                body.add("file", new ByteArrayResource(image.getBytes()) {
                    @Override
                    public String getFilename() {
                        return image.getOriginalFilename();
                    }
                });
            }

            // 4. Python /orchestrate 호출
            HttpEntity<MultiValueMap<String, Object>> requestEntity =
                new HttpEntity<>(body, headers);

            log.info("Python /orchestrate 호출 - question: {}, hasImage: {}",
                question, image != null);

            ResponseEntity<String> response = restTemplate.postForEntity(
                FASTAPI_ORCHESTRATE_URL, requestEntity, String.class
            );

            // 5. 응답 파싱 (중첩 JSON에서 response.answer, response.summaryTitle 추출)
            JsonNode root = objectMapper.readTree(response.getBody());
            JsonNode responseNode = root.path("response");

            result.put("summaryTitle",
                responseNode.path("summaryTitle").asText("도면 분석 결과"));
            result.put("answer",
                responseNode.path("answer").asText("답변을 생성할 수 없습니다."));

            log.info("Python /orchestrate 응답 완료 - intent: {}, agent: {}",
                root.path("intent_type").asText(),
                root.path("agent_used").asText());

        } catch (Exception e) {
            log.error("Python /orchestrate 통신 오류: {}", e.getMessage());
            result.put("summaryTitle", "에러 발생");
            result.put("answer", "서버 통신 오류가 발생했습니다. 잠시 후 다시 시도해주세요.");
        }

        return result;
    }
}
```

### 필요한 추가 import

```java
import org.springframework.core.io.ByteArrayResource;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.multipart.MultipartFile;
```

### 확인 포인트
- `FASTAPI_URL` → `FASTAPI_ORCHESTRATE_URL`로 변경 (`/ask` → `/orchestrate`)
- `application/json` → `multipart/form-data` 전송 방식 변경
- 응답 파싱: 기존 `node.path("answer")` → `root.path("response").path("answer")` (중첩 구조)
- `ByteArrayResource`의 `getFilename()` 오버라이드 필수 (Spring이 파일명 필요)

---

## Step 2.2: ChatbotController 수정

### 수정 파일: `Backend/src/main/java/com/example/skn20/controller/ChatbotController.java`

**변경 부분: `/chat` 엔드포인트만 수정**

```java
/**
 * 질문+이미지를 받고 LLM에 보낸뒤 값을 반환
 * 변경: @RequestParam MultipartFile image 추가
 */
@PostMapping("/chat")
@Transactional
public ResponseEntity<Map<String, Object>> question2answer(
        @AuthenticationPrincipal UD user,
        @RequestParam(required = false) Long chatRoomId,
        @RequestParam String question,
        @RequestParam(required = false) MultipartFile image  // 추가
) {

    // 인증되지 않은 사용자
    if (user == null) {
        Map<String, String> result;
        if (image != null && !image.isEmpty()) {
            result = chatbotService.question2answerWithImage(null, question, image);
        } else {
            result = chatbotService.question2answer(null, question);
        }
        String answer = result.get("answer");
        Map<String, Object> response = new HashMap<>();
        response.put("answer", answer);
        return ResponseEntity.ok(response);
    }

    User userinfo = userservice.findByEmail(user.getEmail());

    // 이미지 유무에 따라 분기
    Map<String, String> result;
    if (image != null && !image.isEmpty()) {
        result = chatbotService.question2answerWithImage(userinfo, question, image);
    } else {
        result = chatbotService.question2answer(userinfo, question);
    }

    String answer = result.get("answer");
    System.out.println(answer);

    Long responseChatRoomId = chatRoomId;

    if (chatRoomId == null) {
        // 새 채팅방 생성
        ChatRoom chatRoom = new ChatRoom();
        chatRoom.setName(result.get("summaryTitle"));
        chatRoom.setUser(userinfo);
        chatRoomRep.save(chatRoom);
        responseChatRoomId = chatRoom.getId();

        ChatHistory chatHistory = new ChatHistory();
        chatHistory.setAnswer(answer);
        chatHistory.setQuestion(question);
        chatHistory.setChatRoom(chatRoom);
        chatHistoryRep.save(chatHistory);
    } else {
        // 기존 채팅방에 히스토리 추가
        ChatRoom chatRoom = chatRoomRep.findChatRoomById(chatRoomId);
        ChatHistory chatHistory = new ChatHistory();
        chatHistory.setAnswer(answer);
        chatHistory.setQuestion(question);
        chatHistory.setChatRoom(chatRoom);
        chatHistoryRep.save(chatHistory);
    }

    Map<String, Object> response = new HashMap<>();
    response.put("answer", answer);
    response.put("chatRoomId", responseChatRoomId);

    return ResponseEntity.ok(response);
}
```

### 변경되지 않는 엔드포인트
- `POST /sessionuser` — 변경 없음
- `POST /roomhistory` — 변경 없음
- `POST /editroomname` — 변경 없음
- `POST /deleteroom` — 변경 없음
- `POST /deleteallrooms` — 변경 없음

### 필요한 추가 import

```java
import org.springframework.web.multipart.MultipartFile;
```

### 확인 포인트
- `@RequestParam(required = false) MultipartFile image` — 이미지가 없어도 기존 텍스트 요청이 정상 동작하는지
- 프론트엔드가 `multipart/form-data`로 보낼 때와 기존 `application/x-www-form-urlencoded`로 보낼 때 모두 동작하는지
- 채팅방 생성/저장 로직은 기존과 완전히 동일

---

## 파일 수정 요약

| 파일 | 변경 내용 |
|------|----------|
| `Backend/.../service/ChatbotService.java` | `/ask` → `/orchestrate` 호출, multipart 전송, 중첩 JSON 파싱 |
| `Backend/.../controller/ChatbotController.java` | `/chat` 엔드포인트에 `MultipartFile image` 파라미터 추가 |

---

## 주의사항

1. **RestTemplate Bean 확인**: `MultipartFile` → `ByteArrayResource` 변환 시 `RestTemplate`이 `FormHttpMessageConverter`를 포함하고 있어야 함. 보통 Spring Boot 기본 설정에 포함되어 있지만, 커스텀 Bean이면 확인 필요.

2. **파일 크기 제한**: `application.properties`에 업로드 제한 설정 확인
   ```properties
   spring.servlet.multipart.max-file-size=10MB
   spring.servlet.multipart.max-request-size=10MB
   ```

3. **CORS 설정**: `ChatbotController`의 `@CrossOrigin`에 이미 `localhost:3000` 포함되어 있으므로 추가 변경 불필요.

---

## 테스트 체크리스트

- [ ] `POST /api/chatbot/chat?question=3Bay 도면 찾아줘` (텍스트만) → 답변 정상 반환
- [ ] `POST /api/chatbot/chat` (FormData: question + image) → 이미지 분석 답변 반환
- [ ] 새 채팅방 생성 시 `chatRoomId` 정상 반환
- [ ] 기존 채팅방에 히스토리 추가 정상 동작
- [ ] 인증 없는 사용자 → 답변은 반환되나 저장은 안 됨
- [ ] Python 서버 다운 시 에러 메시지 정상 반환
