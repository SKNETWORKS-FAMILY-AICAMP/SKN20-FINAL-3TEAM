# 멀티 에이전트 아키텍처 구조 변경 계획서

## 개요

현재 서비스 레이어 기반 구조를 **오케스트레이터 1개 + 에이전트 3개**의 멀티 에이전트 아키텍처로 전환한다.
프론트엔드 구조는 유지하되, 챗봇 페이지에 이미지 업로드 기능을 추가한다.

---

## 모델 전략

| 용도 | 현재 모델 | 비고 |
|------|----------|------|
| 의도 분류 | `gpt-4o-mini` | 오케스트레이터 내부 Tool 2에서 사용 |
| 답변 생성 (도면 검색/이미지) | pipeline.py 기존 모델 | 추후 파인튜닝된 로컬 모델로 전환 예정 |
| 법/조례 답변 생성 | chatbot_service_v2 기존 모델 | 추후 파인튜닝된 로컬 모델로 전환 예정 |
| LLM 분석 (CV 파이프라인) | rag_service 기존 모델 | 추후 파인튜닝된 로컬 모델로 전환 예정 |
| 임베딩 | **Qwen3-Embedding-0.6B** (1024차원) | 기존 1536차원에서 변경 |

> **참고:** 현재 프로젝트에서 사용하는 모든 LLM은 최종적으로 파인튜닝된 로컬 모델로 전환될 예정이다.
> 임베딩 모델은 `Qwen3-Embedding-0.6B`(1024차원)을 전체 프로젝트에서 통일하여 사용한다.

---

## 현재 구조 (AS-IS)

```
[도면 저장 페이지]                          [챗봇 페이지]
     │                                        │
     ▼                                        ▼
Spring Boot                             Spring Boot
/api/floorplan/analyze                  /api/chatbot/chat
/api/floorplan/save                          │
     │                                       ▼
     ▼                                  Python /ask (직접 호출)
Python /analyze → cv_service                 │
Python /generate-metadata → rag_service      ▼
                                        chatbot_service_v2
                                        + law_verification

                                        ※ /orchestrate 엔드포인트 존재하지만
                                          Spring Boot에서 미사용 중
```

### 현재 문제점
1. Spring Boot `ChatbotService`가 `/ask`를 직접 호출 → `/orchestrate`를 우회
2. CV 분석 로직이 서비스 레이어에 분산 (`cv_service` + `rag_service` + `embedding_service`)
3. 의도 분류와 오케스트레이션이 하나의 클래스에 혼재 (`IntentClassifierService`)
4. 도면 검색 에이전트 내 답변 생성이 재사용 불가능한 구조
5. 챗봇 페이지에서 이미지 입력 불가

---

## 목표 구조 (TO-BE)

```
[도면 저장 페이지]                    [챗봇 페이지 - 텍스트/이미지]
     │                                        │
     ▼                                        ▼
Spring Boot                             Spring Boot
/api/floorplan/analyze                  /api/chatbot/chat (텍스트+이미지 지원)
/api/floorplan/save                          │
     │                                       ▼
     ▼                                  Python /orchestrate (텍스트+이미지 지원)
Python /analyze                              │
→ CV 도면 분석 에이전트                       ▼
                              ┌──────────────────────────────┐
                              │        오케스트레이터          │
                              │  ┌────────────────────────┐  │
                              │  │ 내부 Tool:              │  │
                              │  │ ① 입력 유형 판단        │  │
                              │  │ ② 의도 분류 (LLM)      │  │
                              │  └────────────────────────┘  │
                              └──────┬───────────┬───────────┘
                                     │           │
                    ┌────────────────┼───┐       │
                    │                │   │       │
                    ▼                ▼   │       ▼
           ┌──────────────┐  ┌──────────┴┐  ┌──────────┐
           │ CV 도면 분석  │  │ 도면 검색  │  │ 법/조례   │
           │ 에이전트      │  │ 에이전트   │  │ 검색     │
           └──────┬───────┘  └───────────┘  │ 에이전트  │
                  │               ▲          └──────────┘
                  └───────────────┘
               (CV 결과 → 섹션 2,3 생성)
```

---

## 에이전트 정의

### 오케스트레이터 (`OrchestratorAgent`)

| 항목 | 내용 |
|------|------|
| 역할 | 사용자 입력을 판단하고 적절한 에이전트로 라우팅 |
| 내부 Tool 1 | 입력 유형 판단: `has_image` 플래그로 이미지/텍스트 구분 (단순 로직) |
| 내부 Tool 2 | 의도 분류: GPT-4o-mini로 `FLOORPLAN_SEARCH` / `REGULATION_SEARCH` 분류 |
| 비즈니스 로직 | 없음. 판단 + 라우팅 + 에이전트 간 데이터 전달만 수행 |

**라우팅 규칙:**
```
입력 → 이미지 있음?
  ├─ YES → CV 도면 분석 에이전트 호출 → 결과를 도면 검색 에이전트에 전달 (mode=image)
  └─ NO  → 의도 분류 (LLM)
           ├─ FLOORPLAN_SEARCH → 도면 검색 에이전트 (mode=text_search)
           └─ REGULATION_SEARCH → 법/조례 검색 에이전트
```

### 에이전트 1: CV 도면 분석 에이전트 (`CVAnalysisAgent`)

| 항목 | 내용 |
|------|------|
| 입력 | 도면 이미지 (numpy array 또는 파일) + `mode` (`"preview"` / `"full"`) |
| 처리 (공통) | CV 추론 → 토폴로지 생성 → LLM 분석 → topology 이미지 base64 |
| 처리 (full만) | + 메트릭 추출 + document 생성 + 임베딩 생성 (Qwen3-Embedding-0.6B, 1024차원) |
| 출력 | `CVAnalysisResult(topology_data, topology_image_base64, llm_analysis, metrics, document, embedding)` |
| 자율성 | 호출 목적(mode)에 따라 실행 범위를 에이전트가 자율 판단 |

**mode별 동작:**
| mode | 호출자 | 실행 단계 | 용도 |
|------|--------|----------|------|
| `"preview"` | `/analyze` (도면 저장 페이지) | step 1,2,6만 | 미리보기 전용. metrics/document/embedding은 `/generate-metadata`에서 생성 |
| `"full"` (기본값) | `/orchestrate` (챗봇 이미지) | step 1~6 전체 | 챗봇 분석용. 모든 결과를 도면 검색 에이전트에 전달 |

**현재 코드 기반:**
- `cv_service.analyze_image()` (CV 추론)
- `rag_service.analyze_topology()` (LLM 분석)
- `rag_service.extract_metrics()` (메트릭 추출)
- `FloorPlanAnalysis.to_natural_language()` (document 생성)
- `embedding_service.generate_embedding()` (임베딩 생성 — `mode="full"`일 때만)
- 위 5개 서비스 호출을 하나의 에이전트로 통합

### 에이전트 2: 도면 검색 에이전트 (`FloorplanSearchAgent`)

| 항목 | 내용 |
|------|------|
| 입력 모드 1 (text_search) | 텍스트 쿼리 + email |
| 입력 모드 2 (image) | CV 분석 결과 (`CVAnalysisResult`) |
| 처리 (text_search) | 쿼리 분석 → 필터 생성 → 하이브리드 검색 → 리랭킹 → 답변 생성 (섹션 1,2,3) |
| 처리 (image) | CV 결과의 metrics/document를 기반으로 답변 생성 (섹션 2,3만) |
| 출력 | `{answer, floorplan_ids}` — floorplan_ids는 text_search일 때만 `list[int]`, image일 때는 `None` |
| 자율성 | 입력 모드에 따라 자율적으로 처리 방식과 출력 범위 결정 |

**text_search 모드 답변 구조 (현재와 동일):**
```
1. 도면 선택 근거 🔍 (검색 조건 + 일치 조건)
2. 도면 기본 정보 📊 (메트릭 13개)
3. 도면 공간 구성 설명 🧩 (공간별 설명)
```

**image 모드 답변 구조 (섹션 2,3만):**
```
2. 도면 기본 정보 📊 (CV 분석 메트릭)
3. 도면 공간 구성 설명 🧩 (LLM 분석 document 기반)
```

### 에이전트 3: 법/조례 검색 에이전트 (`RegulationSearchAgent`)

| 항목 | 내용 |
|------|------|
| 입력 | email + question |
| 처리 | 용도지역 매핑 → RAG 검색 → Cross-encoder 리랭킹 → 답변 생성 |
| 출력 | `{summaryTitle, answer}` |
| 변경사항 | 기존 `chatbot_service_v2.py` 로직을 에이전트 클래스로 래핑 |

---

## 구현 단계

### Phase 1: Python 백엔드 에이전트 구조 생성

#### Step 1.1: 에이전트 베이스 클래스 생성

**새 파일:** `python/agents/__init__.py`, `python/agents/base.py`

```python
# python/agents/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseAgent(ABC):
    """모든 에이전트의 베이스 클래스"""

    @property
    @abstractmethod
    def name(self) -> str:
        """에이전트 이름"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """에이전트 실행"""
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """에이전트 로드 상태 확인"""
        pass
```

#### Step 1.2: CV 도면 분석 에이전트 생성

**새 파일:** `python/agents/cv_analysis_agent.py`

- 기존 `cv_service.analyze_image()` + `rag_service.analyze_topology()` + `rag_service.extract_metrics()` + `FloorPlanAnalysis.to_natural_language()` + `embedding_service.generate_embedding()` 통합
- `execute(image, filename, mode)` → `CVAnalysisResult` 반환
- `mode="preview"`: 임베딩 스킵 (도면 저장 미리보기용)
- `mode="full"` (기본값): 임베딩 포함 (챗봇 이미지 분석용)

```python
# pseudo-code
class CVAnalysisResult(BaseModel):
    topology_data: dict
    topology_image_base64: str
    llm_analysis: dict               # FloorPlanAnalysis.model_dump() 결과
    metrics: dict                    # 13개 지표
    document: str                    # to_natural_language() 결과
    embedding: list[float]           # 1024차원 벡터 (full) 또는 빈 리스트 (preview)

class CVAnalysisAgent(BaseAgent):
    name = "cv_analysis"

    def execute(self, image, filename, mode: str = "full") -> CVAnalysisResult:
        # ===== 공통 (preview + full) =====
        # 1. CV 추론 (cv_service 내부 로직 활용)
        results = self.cv_pipeline.run(image_path)
        topology_data = results["topology_graph"]

        # 2. LLM 분석 (rag_service 내부 로직 활용)
        llm_analysis = self._analyze_topology(topology_data)

        # 6. topology 이미지 base64
        topology_image_base64 = self._encode_topology_image(filename)

        # ===== preview: 여기서 종료 =====
        if mode == "preview":
            return CVAnalysisResult(
                topology_data=topology_data,
                topology_image_base64=topology_image_base64,
                llm_analysis=llm_analysis.model_dump(),
                metrics={},      # 미사용
                document="",     # 미사용
                embedding=[],    # 미사용
            )

        # ===== full: 메트릭 + document + 임베딩까지 =====
        # 3. 메트릭 추출
        metrics = self._extract_metrics(llm_analysis)

        # 4. document 생성
        document = llm_analysis.to_natural_language()

        # 5. 임베딩 생성
        embedding = self._generate_embedding(document)

        return CVAnalysisResult(
            topology_data=topology_data,
            topology_image_base64=topology_image_base64,
            llm_analysis=llm_analysis.model_dump(),
            metrics=metrics,
            document=document,
            embedding=embedding,
        )
```

**기존 서비스와의 관계:**
- `cv_service`, `rag_service`, `embedding_service`는 삭제하지 않음
- 에이전트가 내부적으로 이 서비스들의 로직을 조합하여 사용
- 기존 `/analyze`, `/generate-metadata` 엔드포인트는 이 에이전트를 호출하도록 변경

#### Step 1.3: 도면 검색 에이전트 리팩토링

**수정 파일:** `python/floorplan/pipeline.py` → `python/agents/floorplan_search_agent.py`

- `ArchitecturalHybridRAG` 클래스를 `FloorplanSearchAgent`로 래핑
- `execute()` 메서드에 `mode` 파라미터 추가

```python
# pseudo-code
class FloorplanSearchAgent(BaseAgent):
    name = "floorplan_search"

    def execute(self, mode: str, **kwargs) -> dict:
        if mode == "text_search":
            # 기존 ArchitecturalHybridRAG.run() 호출
            query = kwargs["query"]
            email = kwargs["email"]
            return self.rag.run(query, email)

        elif mode == "image":
            # CV 결과를 받아서 섹션 2,3 답변 생성
            cv_result = kwargs["cv_result"]  # CVAnalysisResult
            return self._generate_image_answer(cv_result)

    def _generate_image_answer(self, cv_result: CVAnalysisResult) -> dict:
        """CV 분석 결과로 섹션 2,3 답변 생성"""
        # cv_result.metrics → 섹션 2 (도면 기본 정보)
        # cv_result.llm_analysis → 섹션 3 (도면 공간 구성 설명)
        # LLM 호출로 정리된 답변 생성
        answer = self._generate_answer_sections_2_3(
            metrics=cv_result.metrics,
            llm_analysis=cv_result.llm_analysis,
            document=cv_result.document
        )
        # image 모드: floorplan_ids는 None (검색 자체를 수행하지 않음)
        return {"answer": answer, "floorplan_ids": None}
```

**섹션 2,3 전용 프롬프트:**
- 기존 `_generate_answer()` 시스템 프롬프트에서 섹션 1(선택 근거) 관련 부분 제외
- 섹션 2(기본 정보) + 섹션 3(공간 구성 설명)만 생성하도록 수정된 프롬프트 작성

#### Step 1.4: 법/조례 검색 에이전트 래핑

**새 파일:** `python/agents/regulation_search_agent.py`

```python
# pseudo-code
class RegulationSearchAgent(BaseAgent):
    name = "regulation_search"

    def execute(self, email: str, question: str) -> dict:
        result = self.chatbot_service.ask(email, question)
        return {
            "summaryTitle": result["summaryTitle"],
            "answer": result["answer"]
        }
```

- `chatbot_service_v2.py`의 기존 로직은 그대로 유지
- 에이전트가 싱글톤 서비스를 래핑

#### Step 1.5: 오케스트레이터 생성

**새 파일:** `python/agents/orchestrator.py`

```python
# pseudo-code
class OrchestratorAgent:
    """오케스트레이터: 판단 + 라우팅 + 에이전트 간 데이터 전달"""

    def __init__(self):
        self.cv_agent = CVAnalysisAgent()
        self.floorplan_agent = FloorplanSearchAgent()
        self.regulation_agent = RegulationSearchAgent()
        self.openai_client = None  # 의도 분류용

    # ===== 내부 Tool 1: 입력 유형 판단 =====
    def _detect_input_type(self, has_image: bool) -> str:
        return "image" if has_image else "text"

    # ===== 내부 Tool 2: 의도 분류 (텍스트 전용) =====
    def _classify_intent(self, question: str) -> IntentClassification:
        # 기존 IntentClassifierService.classify_intent() 로직 이동
        ...

    # ===== 메인 라우팅 =====
    def route(self, email: str, question: str = "",
              image=None, filename: str = "") -> dict:

        input_type = self._detect_input_type(has_image=image is not None)

        if input_type == "image":
            # 이미지 경로: CV 에이전트 (mode=full, 임베딩 포함) → 도면 검색 에이전트 (mode=image)
            cv_result = self.cv_agent.execute(image=image, filename=filename, mode="full")
            response = self.floorplan_agent.execute(
                mode="image", cv_result=cv_result
            )
            return {
                "intent_type": "FLOORPLAN_IMAGE",
                "agent_used": "cv_analysis + floorplan_search",
                "response": response,
            }

        else:
            # 텍스트 경로: 의도 분류 → 에이전트 라우팅
            intent = self._classify_intent(question)

            if intent.intent_type == "FLOORPLAN_SEARCH":
                response = self.floorplan_agent.execute(
                    mode="text_search", query=question, email=email
                )
                return {
                    "intent_type": intent.intent_type,
                    "agent_used": "floorplan_search",
                    "response": response,
                }

            else:  # REGULATION_SEARCH
                response = self.regulation_agent.execute(
                    email=email, question=question
                )
                return {
                    "intent_type": intent.intent_type,
                    "agent_used": "regulation_search",
                    "response": response,
                }
```

#### Step 1.6: 스키마 업데이트

**수정 파일:** `python/api_models/schemas.py`

```python
# 추가할 스키마

class OrchestrateRequest(BaseModel):
    """오케스트레이터 요청 - 텍스트+이미지 지원"""
    email: str
    question: str = ""         # 텍스트 질문 (이미지 전용일 때 빈 문자열)
    has_image: bool = False    # 이미지 첨부 여부 (멀티파트 시 True)

class OrchestrateResponse(BaseModel):
    """오케스트레이터 응답"""
    intent_type: str           # FLOORPLAN_SEARCH | REGULATION_SEARCH | FLOORPLAN_IMAGE
    confidence: float = 1.0
    agent_used: str
    response: Dict[str, Any]   # {summaryTitle, answer, ?floorplan_ids}
    metadata: Dict[str, Any] = {}
    # floorplan_ids 의미:
    #   list[int]  → text_search: 검색된 도면 ID 목록
    #   []         → text_search: 검색했으나 매칭 없음
    #   None/미포함 → image 모드, 법규 모드: 검색 자체 미수행
```

#### Step 1.7: 엔드포인트 업데이트

**수정 파일:** `python/main.py`

```python
# /orchestrate 엔드포인트를 이미지 지원으로 확장

@app.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate_query(
    email: str = Form(...),
    question: str = Form(""),
    file: Optional[UploadFile] = File(None),
):
    """통합 오케스트레이터 엔드포인트 (텍스트 + 이미지)"""
    image = None
    filename = ""

    if file is not None:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        filename = file.filename

    result = orchestrator.route(
        email=email, question=question,
        image=image, filename=filename
    )
    return OrchestrateResponse(**result)

# /analyze 엔드포인트는 CV 에이전트를 직접 호출하도록 변경
@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_floorplan(file: UploadFile = File(...)):
    """도면 분석 엔드포인트 (도면 저장 페이지용)"""
    # mode="preview": 임베딩 스킵 (미리보기 전용)
    # 임베딩은 저장 시 /generate-metadata에서 별도 생성
    cv_result = cv_analysis_agent.execute(
        image=image, filename=file.filename, mode="preview"
    )
    return AnalyzeResponse(
        topology_json=json.dumps(cv_result.topology_data),
        topology_image_url=cv_result.topology_image_base64,
        llm_analysis_json=json.dumps(cv_result.llm_analysis.model_dump()),
    )

# /generate-metadata 엔드포인트 — 기존 로직 유지
@app.post("/generate-metadata", response_model=SaveResponse)
async def generate_metadata(request: SaveRequest):
    """메타데이터 생성 (도면 저장 페이지용)"""
    # /analyze에서 mode="preview"로 임베딩을 스킵했으므로,
    # 저장 시점에 여기서 임베딩을 1회만 생성
    # 기존 로직 유지: llm_analysis → metrics + document + embedding
    ...

# /ask 엔드포인트 삭제
# 기존에 Spring Boot가 /ask를 직접 호출했으나,
# /orchestrate가 이를 완전히 대체하므로 삭제한다.
# 호출하는 클라이언트: Spring Boot ChatbotService → /orchestrate로 전환 완료
```

---

### Phase 2: Spring Boot 미들웨어 변경

#### Step 2.1: ChatbotService 수정

**수정 파일:** `Backend/.../service/ChatbotService.java`

```java
// 변경점: /ask → /orchestrate 호출
// 이미지 파일 전달 지원 추가

@Service
public class ChatbotService {

    private final String FASTAPI_ORCHESTRATE_URL = "http://localhost:8000/orchestrate";

    // 텍스트 전용 (기존 호환)
    public Map<String, String> question2answer(User user, String question) {
        return orchestrate(user, question, null);
    }

    // 텍스트 + 이미지
    public Map<String, String> question2answerWithImage(User user, String question, MultipartFile image) {
        return orchestrate(user, question, image);
    }

    private Map<String, String> orchestrate(User user, String question, MultipartFile image) {
        // MultiValueMap으로 Form 데이터 구성
        // image가 있으면 multipart/form-data로 전송
        // image가 없으면 email + question만 전송
        // 응답에서 response.answer, response.summaryTitle 추출
        ...
    }
}
```

#### Step 2.2: ChatbotController 수정

**수정 파일:** `Backend/.../controller/ChatbotController.java`

```java
// 변경점: question 파라미터 외에 Optional<MultipartFile> 추가

@PostMapping("/chat")
@Transactional
public ResponseEntity<Map<String, Object>> question2answer(
        @AuthenticationPrincipal UD user,
        @RequestParam(required = false) Long chatRoomId,
        @RequestParam String question,
        @RequestParam(required = false) MultipartFile image  // 추가
) {
    Map<String, String> result;
    if (image != null && !image.isEmpty()) {
        result = chatbotService.question2answerWithImage(userinfo, question, image);
    } else {
        result = chatbotService.question2answer(userinfo, question);
    }
    // 나머지 로직 (채팅방 생성/저장) 동일
    ...
}
```

---

### Phase 3: 프론트엔드 변경

#### Step 3.1: 채팅 타입 업데이트

**수정 파일:** `final-frontend-ts/src/features/chat/types/chat.types.ts`

```typescript
// ChatRequest에 이미지 필드 추가 (FormData로 전송하므로 타입만 정의)
export interface ChatRequest {
  chatRoomId: number | null;
  question: string;
  image?: File;  // 추가
}
```

#### Step 3.2: 채팅 API 업데이트

**수정 파일:** `final-frontend-ts/src/features/chat/api/chat.api.ts`

```typescript
// sendChat을 FormData 지원으로 변경
export const sendChat = async (params: ChatRequest): Promise<ChatResponse> => {
  if (params.image) {
    // 이미지가 있으면 FormData로 전송
    const formData = new FormData();
    if (params.chatRoomId !== null) {
      formData.append('chatRoomId', String(params.chatRoomId));
    }
    formData.append('question', params.question);
    formData.append('image', params.image);

    const response = await apiClient.post<ChatResponse>(
      `${CHATBOT_BASE}/chat`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  }

  // 텍스트만 있으면 기존 방식
  const response = await apiClient.post<ChatResponse>(
    `${CHATBOT_BASE}/chat`,
    null,
    { params: { chatRoomId: params.chatRoomId, question: params.question } }
  );
  return response.data;
};
```

#### Step 3.3: ChatPage 이미지 업로드 UI 추가

**수정 파일:** `final-frontend-ts/src/features/chat/ChatPage.tsx`

```typescript
// 추가할 상태
const [selectedImage, setSelectedImage] = useState<File | null>(null);
const [imagePreview, setImagePreview] = useState<string | null>(null);
const fileInputRef = useRef<HTMLInputElement>(null);

// 이미지 선택 핸들러
const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (file && (file.type === 'image/png' || file.type === 'image/jpeg')) {
    setSelectedImage(file);
    setImagePreview(URL.createObjectURL(file));
  }
};

// 이미지 제거 핸들러
const handleRemoveImage = () => {
  setSelectedImage(null);
  if (imagePreview) {
    URL.revokeObjectURL(imagePreview);  // 메모리 해제
  }
  setImagePreview(null);
  if (fileInputRef.current) {
    fileInputRef.current.value = '';  // file input 초기화
  }
};

// handleSendMessage 수정: 이미지 포함 전송
const handleSendMessage = async (e: React.FormEvent) => {
  e.preventDefault();
  if ((!inputMessage.trim() && !selectedImage) || isSending) return;

  const question = inputMessage.trim() || "이 도면을 분석해주세요";
  // ...

  const response = await sendChat({
    chatRoomId: currentRoomId,
    question,
    image: selectedImage || undefined,
  });

  // 전송 후 이미지 초기화
  setSelectedImage(null);
  setImagePreview(null);
  // ...
};

// 입력 영역에 이미지 업로드 버튼 + 미리보기 추가
// <input type="file" accept="image/png,image/jpeg" ref={fileInputRef} />
// 이미지 미리보기 썸네일
// 삭제(X) 버튼
```

#### Step 3.4: ChatPage CSS 업데이트

**수정 파일:** `final-frontend-ts/src/features/chat/ChatPage.module.css`

```css
/* 추가할 스타일 */
.imageUploadButton { ... }      /* 이미지 첨부 아이콘 버튼 */
.imagePreviewContainer { ... }  /* 입력창 위 이미지 미리보기 영역 */
.imagePreviewThumb { ... }      /* 썸네일 이미지 */
.imageRemoveButton { ... }      /* X 버튼 */
```

---

## 파일 변경 요약

### 새로 생성하는 파일

| 파일 | 설명 |
|------|------|
| `python/agents/__init__.py` | 에이전트 패키지 초기화 |
| `python/agents/base.py` | BaseAgent 추상 클래스 |
| `python/agents/cv_analysis_agent.py` | CV 도면 분석 에이전트 |
| `python/agents/floorplan_search_agent.py` | 도면 검색 에이전트 (ArchitecturalHybridRAG 래핑) |
| `python/agents/regulation_search_agent.py` | 법/조례 검색 에이전트 |
| `python/agents/orchestrator.py` | 오케스트레이터 |

### 수정하는 파일

| 파일 | 수정 내용 |
|------|----------|
| `python/main.py` | 엔드포인트에서 에이전트 사용, /orchestrate 이미지 지원 |
| `python/api_models/schemas.py` | OrchestrateRequest/Response 확장, CVAnalysisResult 추가 |
| `Backend/.../service/ChatbotService.java` | /ask → /orchestrate 호출, 이미지 전달 지원 |
| `Backend/.../controller/ChatbotController.java` | /chat 엔드포인트에 MultipartFile 파라미터 추가 |
| `final-frontend-ts/.../chat/types/chat.types.ts` | ChatRequest에 image 필드 추가 |
| `final-frontend-ts/.../chat/api/chat.api.ts` | sendChat FormData 지원 |
| `final-frontend-ts/.../chat/ChatPage.tsx` | 이미지 업로드 UI 추가 |
| `final-frontend-ts/.../chat/ChatPage.module.css` | 이미지 관련 스타일 추가 |

### 삭제하지 않는 파일 (하위 호환)

| 파일 | 이유 |
|------|------|
| `python/services/cv_service.py` | CV 에이전트 내부에서 활용 |
| `python/services/rag_service.py` | CV 에이전트 내부에서 활용 |
| `python/services/embedding_service.py` | CV 에이전트 내부에서 활용 |
| `python/services/chatbot_service_v2.py` | 법/조례 에이전트 내부에서 활용 |
| `python/services/intent_classifier_service.py` | 오케스트레이터 내부 Tool로 로직 이전 후 deprecated 처리 |
| `python/floorplan/pipeline.py` | 도면 검색 에이전트 내부에서 활용 |

---

## 리스크 및 대응

| 리스크 | 영향도 | 대응 방안 |
|--------|--------|----------|
| Spring Boot `multipart/form-data` 전환 시 기존 텍스트 전용 API 호환성 | 중 | 이미지 없을 때 기존 param 방식 유지, 이미지 있을 때만 FormData |
| CV 모델 메모리 (챗봇에서도 이미지 분석 시) | 중 | `cv_service` 싱글톤 재사용, 추가 메모리 부담 없음 |
| `/ask` 엔드포인트 삭제 | 저 | `/orchestrate`가 완전 대체하므로 삭제. Spring Boot가 유일한 호출자였으며 `/orchestrate`로 전환 |
| 도면 저장 페이지 기능 변경 우려 | 고 | `/analyze`, `/generate-metadata` 엔드포인트 입출력 동일하게 유지 |
| 이미지 답변 생성 프롬프트 품질 | 중 | 기존 섹션 2,3 프롬프트 재활용, 테스트 반복 |
| CVAnalysisAgent mode 파라미터 오용 | 저 | 기본값을 `"full"`로 설정하여 명시적으로 `"preview"`를 넘기지 않으면 임베딩 포함. `/analyze`만 `mode="preview"` 사용 |

---

## 구현 순서 (권장)

```
Phase 1 (Python 백엔드) — 우선 순위 높음
  1.1 BaseAgent 생성
  1.2 CV 도면 분석 에이전트 → 1.7 /analyze 엔드포인트 연결 → 도면 저장 페이지 동작 확인
  1.3 도면 검색 에이전트 (text_search 모드) → 기존 동작 확인
  1.4 법/조례 검색 에이전트
  1.5 오케스트레이터 (텍스트 전용) → /orchestrate 텍스트 동작 확인
  1.6 스키마 업데이트
  1.3+ 도면 검색 에이전트 (image 모드 추가)
  1.5+ 오케스트레이터 (이미지 지원 추가) → /orchestrate 이미지 동작 확인
  1.7 전체 엔드포인트 업데이트

Phase 2 (Spring Boot) — Phase 1 완료 후
  2.1 ChatbotService /orchestrate 호출로 변경
  2.2 ChatbotController 이미지 파라미터 추가

Phase 3 (프론트엔드) — Phase 2 완료 후
  3.1 타입 업데이트
  3.2 API 함수 업데이트
  3.3 ChatPage UI 변경
  3.4 CSS 추가
```

---

## 테스트 체크리스트

### Phase 1 완료 후
- [ ] `/analyze` — 도면 이미지 업로드 → 기존과 동일한 응답 확인
- [ ] `/generate-metadata` — llm_analysis_json → 기존과 동일한 응답 확인
- [ ] `/orchestrate` (텍스트, 도면 검색) — "3Bay 판상형 도면 찾아줘" → 섹션 1,2,3 답변
- [ ] `/orchestrate` (텍스트, 법규 검색) — "강남구에 미용실 지을 수 있어?" → 답변
- [ ] `/orchestrate` (이미지) — 도면 이미지 전송 → 섹션 2,3 답변
- [ ] `/ask` 엔드포인트 삭제 확인 (404 반환)

### Phase 2 완료 후
- [ ] Spring Boot `/api/chatbot/chat` (텍스트) → Python `/orchestrate` 호출 확인
- [ ] Spring Boot `/api/chatbot/chat` (이미지) → Python `/orchestrate` 이미지 전달 확인

### Phase 3 완료 후
- [ ] 챗봇 페이지 텍스트 입력 → 기존과 동일하게 동작
- [ ] 챗봇 페이지 이미지 업로드 → 미리보기 표시 → 전송 → 분석 답변 수신
- [ ] 도면 저장 페이지 → 기존과 동일하게 동작 (영향 없음)
