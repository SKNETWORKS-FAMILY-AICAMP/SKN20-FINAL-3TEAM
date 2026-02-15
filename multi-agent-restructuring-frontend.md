# Phase 3: 프론트엔드 — 챗봇 이미지 업로드 기능 추가

> 상위 계획서: `multi-agent-restructuring.md`

---

## 선행 조건

- Phase 1 (Python 백엔드) 완료
- Phase 2 (Spring Boot) 완료
- `/api/chatbot/chat`이 `multipart/form-data`로 이미지를 받을 수 있는 상태

## 완료 조건

- 챗봇 페이지 텍스트 입력 → 기존과 동일하게 동작
- 챗봇 페이지 이미지 업로드 → 미리보기 → 전송 → 분석 답변 수신
- 도면 저장 페이지 → 기존과 동일하게 동작 (영향 없음)

---

## Task Type

- [x] Frontend (React + TypeScript)

---

## 현재 구조 분석

### 현재 채팅 입력 흐름

```
ChatPage.tsx
  └─ handleSendMessage()
       └─ sendChat({ chatRoomId, question })     ← params 방식 (URL query string)
            └─ apiClient.post("/api/chatbot/chat", null, { params })
```

- `sendChat`은 `application/x-www-form-urlencoded` 방식 (params)
- 이미지 전송 불가

### 목표 흐름

```
ChatPage.tsx
  ├─ 텍스트만: handleSendMessage()
  │    └─ sendChat({ chatRoomId, question })     ← 기존 params 방식 유지
  │         └─ apiClient.post("/api/chatbot/chat", null, { params })
  │
  └─ 이미지 포함: handleSendMessage()
       └─ sendChat({ chatRoomId, question, image })
            └─ apiClient.post("/api/chatbot/chat", FormData)
```

---

## Step 3.1: 채팅 타입 업데이트

### 수정 파일: `final-frontend-ts/src/features/chat/types/chat.types.ts`

**변경 내용:**

```typescript
// 채팅 요청 — image 필드 추가
export interface ChatRequest {
  chatRoomId: number | null;
  question: string;
  image?: File;  // 추가: 도면 이미지 (PNG/JPG)
}
```

**변경되지 않는 타입:**
- `ChatRoom`, `ChatHistory`, `ChatResponse` — 변경 없음
- `EditRoomNameRequest`, `DeleteRoomRequest`, `RoomHistoryRequest` — 변경 없음
- `ChatImage`, `ChatMessage`, `ChatSession` — 변경 없음
- `ChatSidebarProps`, `ChatMessageProps` — 변경 없음

---

## Step 3.2: 채팅 API 업데이트

### 수정 파일: `final-frontend-ts/src/features/chat/api/chat.api.ts`

**변경 내용:** `sendChat` 함수만 수정

```typescript
// 3. 질문 → 답변 (QnA) 및 저장
// 변경: 이미지가 있으면 FormData로 전송
export const sendChat = async (params: ChatRequest): Promise<ChatResponse> => {
  if (params.image) {
    // 이미지 포함: FormData 방식
    const formData = new FormData();
    if (params.chatRoomId !== null) {
      formData.append('chatRoomId', String(params.chatRoomId));
    }
    formData.append('question', params.question);
    formData.append('image', params.image);

    const response = await apiClient.post<ChatResponse>(
      `${CHATBOT_BASE}/chat`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,  // 이미지 분석은 시간이 걸릴 수 있음 (2분)
      }
    );
    return response.data;
  }

  // 텍스트만: 기존 params 방식 유지
  const response = await apiClient.post<ChatResponse>(
    `${CHATBOT_BASE}/chat`,
    null,
    { params }
  );
  return response.data;
};
```

**변경되지 않는 API 함수:**
- `getChatRooms` — 변경 없음
- `getRoomHistory` — 변경 없음
- `editRoomName` — 변경 없음
- `deleteRoom` — 변경 없음
- `deleteAllRooms` — 변경 없음

### 확인 포인트
- 이미지 없을 때 기존 `params` 방식이 그대로 유지되는지 (하위 호환)
- `FormData` 전송 시 `Content-Type`을 명시적으로 설정 (axios가 boundary 자동 추가)
- 이미지 분석은 CV 파이프라인 + LLM 호출이므로 timeout을 120초로 넉넉하게 설정

---

## Step 3.3: ChatPage 이미지 업로드 UI 추가

### 수정 파일: `final-frontend-ts/src/features/chat/ChatPage.tsx`

**추가할 import:**

```typescript
import { IoSend, IoImageOutline, IoCloseCircle } from 'react-icons/io5';
// IoImageOutline: 이미지 첨부 버튼 아이콘
// IoCloseCircle: 이미지 미리보기 삭제 버튼 아이콘
```

**추가할 상태 (기존 상태 아래에 추가):**

```typescript
const [selectedImage, setSelectedImage] = useState<File | null>(null);
const [imagePreview, setImagePreview] = useState<string | null>(null);
const fileInputRef = useRef<HTMLInputElement>(null);
```

**추가할 핸들러:**

```typescript
// 이미지 선택
const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (!file) return;

  // PNG, JPG만 허용
  if (!['image/png', 'image/jpeg'].includes(file.type)) {
    alert('PNG 또는 JPG 이미지만 업로드할 수 있습니다.');
    return;
  }

  // 10MB 제한
  if (file.size > 10 * 1024 * 1024) {
    alert('이미지 크기는 10MB 이하여야 합니다.');
    return;
  }

  setSelectedImage(file);
  setImagePreview(URL.createObjectURL(file));
};

// 이미지 제거
const handleRemoveImage = () => {
  setSelectedImage(null);
  if (imagePreview) {
    URL.revokeObjectURL(imagePreview);  // 메모리 해제
  }
  setImagePreview(null);
  // file input 초기화
  if (fileInputRef.current) {
    fileInputRef.current.value = '';
  }
};

// 이미지 첨부 버튼 클릭
const handleImageButtonClick = () => {
  fileInputRef.current?.click();
};
```

**handleSendMessage 수정:**

```typescript
const handleSendMessage = async (e: React.FormEvent) => {
  e.preventDefault();
  // 변경: 이미지만 있어도 전송 가능
  if ((!inputMessage.trim() && !selectedImage) || isSending) return;

  // 이미지만 보낼 때 기본 질문 설정
  const question = inputMessage.trim() || (selectedImage ? '이 도면을 분석해주세요' : '');
  setInputMessage('');
  setIsSending(true);

  // 사용자 메시지 즉시 표시
  const userMessage: ChatMessageType = {
    id: `temp-user-${Date.now()}`,
    role: 'user',
    content: question,
    timestamp: new Date(),
    // 이미지가 있으면 미리보기 포함
    images: selectedImage ? [{
      url: imagePreview || '',
      name: selectedImage.name,
      description: '업로드한 도면 이미지',
    }] : undefined,
  };
  setMessages((prev) => [...prev, userMessage]);

  // 이미지 상태 먼저 초기화 (UI 반응성)
  const imageToSend = selectedImage;
  setSelectedImage(null);
  if (imagePreview) {
    URL.revokeObjectURL(imagePreview);
  }
  setImagePreview(null);
  if (fileInputRef.current) {
    fileInputRef.current.value = '';
  }

  try {
    const response = await sendChat({
      chatRoomId: currentRoomId,
      question,
      image: imageToSend || undefined,
    });

    // ... 이후 AI 응답 표시 로직은 기존과 동일
    // (다만 MOCK 이미지 데이터는 제거하거나 실제 데이터로 교체)
```

**입력 영역 JSX 변경:**

```tsx
<div
  className={styles.inputArea}
  style={{
    backgroundColor: '#FFFFFF',
    borderTop: `1px solid ${colors.border}`,
  }}
>
  {/* 이미지 미리보기 영역 (선택된 이미지가 있을 때만 표시) */}
  {imagePreview && (
    <div className={styles.imagePreviewContainer}>
      <div className={styles.imagePreviewWrapper}>
        <img
          src={imagePreview}
          alt="선택된 도면"
          className={styles.imagePreviewThumb}
        />
        <button
          type="button"
          className={styles.imageRemoveButton}
          onClick={handleRemoveImage}
        >
          <IoCloseCircle size={20} />
        </button>
        <span className={styles.imageFileName}>
          {selectedImage?.name}
        </span>
      </div>
    </div>
  )}

  <form onSubmit={handleSendMessage} className={styles.inputForm}>
    {/* 숨겨진 파일 input */}
    <input
      type="file"
      ref={fileInputRef}
      accept="image/png,image/jpeg"
      onChange={handleImageSelect}
      style={{ display: 'none' }}
    />

    {/* 이미지 첨부 버튼 */}
    <button
      type="button"
      className={styles.imageUploadButton}
      onClick={handleImageButtonClick}
      disabled={isSending}
      style={{ color: selectedImage ? colors.primary : colors.textSecondary }}
    >
      <IoImageOutline size={22} />
    </button>

    <input
      type="text"
      placeholder={selectedImage ? "도면에 대한 질문을 입력하세요..." : "메시지를 입력하세요..."}
      value={inputMessage}
      onChange={(e) => setInputMessage(e.target.value)}
      disabled={isSending}
      className={styles.input}
      style={{
        border: `1px solid ${colors.border}`,
        backgroundColor: colors.inputBg,
        color: colors.textPrimary,
      }}
    />
    <button
      type="submit"
      disabled={isSending || (!inputMessage.trim() && !selectedImage)}
      className={styles.sendButton}
      style={{
        backgroundColor: (isSending || (!inputMessage.trim() && !selectedImage))
          ? colors.textSecondary
          : colors.primary,
      }}
    >
      <IoSend size={18} color="#fff" />
    </button>
  </form>
</div>
```

### 확인 포인트
- 이미지 없이 텍스트만 입력 → 기존과 동일하게 동작
- 이미지만 선택하고 텍스트 없이 전송 → "이 도면을 분석해주세요" 기본 질문
- 이미지 + 텍스트 같이 전송 → 이미지 분석 + 질문 함께 처리
- 이미지 미리보기 → X 버튼으로 제거 가능
- `URL.revokeObjectURL()` 호출로 메모리 누수 방지
- 전송 후 이미지 상태 자동 초기화
- MOCK 이미지 데이터(L264-L281) 제거 또는 실제 데이터로 교체 필요

---

## Step 3.4: ChatPage CSS 업데이트

### 수정 파일: `final-frontend-ts/src/features/chat/ChatPage.module.css`

**추가할 스타일:**

```css
/* ============================================
   이미지 업로드 관련 스타일
   ============================================ */

/* 이미지 미리보기 컨테이너 (입력창 위) */
.imagePreviewContainer {
  padding: 8px 16px;
  border-bottom: 1px solid #e0e0e0;
}

.imagePreviewWrapper {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background-color: #f5f5f5;
  border-radius: 8px;
  position: relative;
}

/* 썸네일 이미지 */
.imagePreviewThumb {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e0e0e0;
}

/* 파일명 텍스트 */
.imageFileName {
  font-size: 13px;
  color: #666;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 이미지 제거 (X) 버튼 */
.imageRemoveButton {
  position: absolute;
  top: -6px;
  right: -6px;
  background: white;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  transition: color 0.2s;
}

.imageRemoveButton:hover {
  color: #e53935;
}

/* 이미지 첨부 버튼 (입력창 왼쪽) */
.imageUploadButton {
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  transition: background-color 0.2s;
  flex-shrink: 0;
}

.imageUploadButton:hover {
  background-color: #f0f0f0;
}

.imageUploadButton:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

/* inputForm 수정: 이미지 버튼 공간 확보 */
/* 기존 .inputForm에 gap 추가 필요 */
```

### 확인 포인트
- 기존 `.inputForm` 스타일에 `gap` 또는 이미지 버튼 공간이 반영되는지
- 다크모드 대응: `ThemeContext`의 `colors`를 CSS 변수로 사용하거나 인라인 스타일로 처리
- 반응형: 작은 화면에서 이미지 미리보기가 깨지지 않는지

---

## 파일 수정 요약

| 파일 | 변경 내용 |
|------|----------|
| `final-frontend-ts/src/features/chat/types/chat.types.ts` | `ChatRequest`에 `image?: File` 추가 |
| `final-frontend-ts/src/features/chat/api/chat.api.ts` | `sendChat` FormData 분기 추가 |
| `final-frontend-ts/src/features/chat/ChatPage.tsx` | 이미지 상태/핸들러/UI 추가, handleSendMessage 수정 |
| `final-frontend-ts/src/features/chat/ChatPage.module.css` | 이미지 관련 CSS 추가 |

---

## 테스트 체크리스트

- [ ] 텍스트만 입력 → 기존과 동일하게 전송 및 답변 수신
- [ ] 이미지 첨부 버튼 → 파일 선택 다이얼로그 → PNG/JPG만 선택 가능
- [ ] 이미지 선택 → 입력창 위에 미리보기 썸네일 + 파일명 표시
- [ ] 미리보기 X 버튼 → 이미지 제거, file input 초기화
- [ ] 이미지만 전송 (텍스트 없음) → "이 도면을 분석해주세요" 기본 질문으로 전송
- [ ] 이미지 + 텍스트 전송 → FormData로 전송 → 답변 수신
- [ ] 전송 완료 후 이미지 상태 자동 초기화
- [ ] 전송 중(loading) 이미지 버튼 비활성화
- [ ] 10MB 초과 이미지 → alert 표시, 업로드 차단
- [ ] 도면 저장 페이지 → 영향 없음 확인
