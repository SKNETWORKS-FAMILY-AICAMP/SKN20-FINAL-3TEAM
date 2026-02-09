# CV 파이프라인 LLM 로컬 모델(sLLM) 교체 계획

## 목표
- 현재 OpenAI GPT-4o-mini를 허깅페이스 파인튜닝 모델로 교체
- OpenAI text-embedding-3-small을 로컬 임베딩 모델로 교체
- 환경변수로 OpenAI/로컬 모델 전환 가능하도록 설계

---

## 하드웨어 환경

| 항목 | 사양 |
|------|------|
| GPU | RTX 3070 |
| VRAM | 8GB |
| 제약 | 7B 모델 학습 어려움, 3B 모델 권장 |

---

## 현재 구조 (교체 대상)

| 항목 | 현재 | 교체 후 |
|------|------|---------|
| LLM | GPT-4o-mini | 허깅페이스 파인튜닝 모델 |
| Embedding | text-embedding-3-small (512d) | sentence-transformers |
| 구조화 출력 | OpenAI response_format | Outlines 라이브러리 |

**관련 파일:**
- `python/CV/rag_system/llm_client.py` - LLM 클라이언트 (LocalLLMClient 스텁 존재)
- `python/CV/rag_system/embeddings.py` - 임베딩 매니저
- `python/CV/rag_system/config.py` - RAG 설정
- `python/services/rag_service.py` - RAG 서비스
- `python/services/chatbot_service.py` - 챗봇 서비스

---

## 현실적 전략 (2단계) - 한국어 특화

### Stage 1: 로컬 EXAONE 2.4B로 파이프라인 검증
- **목표**: 로컬 LLM 파이프라인 구축 및 검증
- **모델**: EXAONE-3.5-2.4B-Instruct (LG AI, 한국어 특화)
- **환경**: RTX 3070 8GB (로컬)
- **예상 성능**: GPT-4o-mini 대비 **70-80%**

### Stage 2: 클라우드 EXAONE 7.8B로 품질 향상 (필요 시)
- **조건**: Stage 1 성능이 부족할 경우
- **모델**: EXAONE-3.5-7.8B-Instruct
- **환경**: RunPod A100 ($50 예산)
- **예상 성능**: GPT-4o-mini 대비 **85-95%**

---

## 구현 단계

### Phase 1: 추상화 레이어 구축

#### 1.1 LLM 클라이언트 확장
**파일:** `python/CV/rag_system/llm_client.py`

- [ ] `LocalLLMClient` 구현 완성 (현재 스텁만 존재)
  - transformers로 모델 로드
  - Outlines 연동하여 구조화 출력 지원
- [ ] `LLMClientFactory` 팩토리 클래스 추가

```python
class LocalLLMClient(LLMClient):
    def __init__(self, model_path: str, device: str = "cuda"):
        self.model = AutoModelForCausalLM.from_pretrained(model_path)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self._outlines_model = models.Transformers(self.model, self.tokenizer)

    def query(self, messages, response_model=None):
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False)
        if response_model:
            generator = generate.json(self._outlines_model, response_model)
            return generator(prompt)
        # ...
```

#### 1.2 임베딩 추상화
**파일:** `python/CV/rag_system/embeddings.py`

- [ ] `BaseEmbeddingManager` ABC 추가
- [ ] 기존 `EmbeddingManager` → `OpenAIEmbeddingManager`로 리네임
- [ ] `LocalEmbeddingManager` 구현 (sentence-transformers)
- [ ] `EmbeddingManagerFactory` 팩토리 클래스 추가

```python
class LocalEmbeddingManager(BaseEmbeddingManager):
    def __init__(self, model_name: str, device: str = "cuda"):
        self._model = SentenceTransformer(model_name, device=device)

    def embed_text(self, text: str) -> List[float]:
        return self._model.encode(text).tolist()
```

### Phase 2: 설정 확장

**파일:** `python/CV/rag_system/config.py`

- [ ] Provider 선택 설정 추가
- [ ] 로컬 모델 경로 설정 추가

```python
class RAGConfig(BaseSettings):
    # Provider 선택
    LLM_PROVIDER: str = "openai"  # "openai" | "local"
    EMBEDDING_PROVIDER: str = "openai"  # "openai" | "local"

    # 로컬 LLM 설정
    LOCAL_LLM_MODEL_PATH: str = ""
    LOCAL_LLM_DEVICE: str = "cuda"
    LOCAL_LLM_MAX_NEW_TOKENS: int = 4096

    # 로컬 Embedding 설정 (한국어 특화)
    LOCAL_EMBEDDING_MODEL: str = "BM-K/KoSimCSE-roberta"
    LOCAL_EMBEDDING_DEVICE: str = "cuda"
```

### Phase 3: 서비스 레이어 수정

- [ ] `python/services/rag_service.py` - 팩토리 패턴 적용
- [ ] `python/services/embedding_service.py` - 팩토리 패턴 적용
- [ ] `python/services/chatbot_service.py` - OpenAI 직접 호출 → LLMClient 인터페이스로 변경

### Phase 4: 파인튜닝 인프라 구축

**새 디렉토리 생성:** `python/CV/llm_finetuning/`

```
python/CV/llm_finetuning/
├── PLAN.md                      # 이 계획서
├── __init__.py
├── config.py                    # 파인튜닝 설정
├── data/
│   ├── prepare_dataset.py       # 데이터 전처리
│   └── processed/               # 학습 데이터 저장
└── scripts/
    ├── finetune_lora.py         # LoRA 파인튜닝
    └── merge_lora.py            # 가중치 병합
```

**학습 데이터 형식 (JSONL):**
```json
{
  "conversations": [
    {"role": "system", "content": "당신은 건축 평면도 분석 전문가입니다..."},
    {"role": "user", "content": "{topology_json + RAG context}"},
    {"role": "assistant", "content": "{FloorPlanAnalysis JSON}"}
  ]
}
```

### Phase 5: 의존성 추가

**파일:** `python/requirements.txt`

```
# 로컬 LLM
outlines>=0.0.40
transformers>=4.36.0
accelerate>=0.25.0
bitsandbytes>=0.41.0

# 로컬 Embedding
sentence-transformers>=2.2.0

# 파인튜닝
peft>=0.7.0
datasets>=2.15.0
```

---

## 모델 추천 (한국어 특화)

### LLM 모델 (RTX 3070 8GB 기준)

#### Stage 1: 로컬 학습용
| 모델 | VRAM (QLoRA) | 한국어 | 예상 성능 |
|------|-------------|--------|----------|
| **EXAONE-3.5-2.4B-Instruct** | ~4GB | **최상** | **70-80%** |
| Polyglot-Ko-1.3B | ~3GB | 상 | 55-65% |
| Qwen2.5-3B-Instruct | ~5GB | 중상 | 60-70% |

#### Stage 2: 클라우드 학습용
| 모델 | VRAM (QLoRA) | 한국어 | 예상 성능 |
|------|-------------|--------|----------|
| **EXAONE-3.5-7.8B-Instruct** | ~10GB | **최상** | **85-95%** |
| SOLAR-10.7B-Instruct | ~14GB | 상 | 80-90% |
| Qwen2.5-14B-Instruct | ~16GB | 중상 | 80-90% |
| Qwen3.0


### Embedding 모델 (한국어 특화)
| 모델 | 차원 | 한국어 | VRAM |
|------|------|--------|------|
| **KoSimCSE-roberta** | 768 | **최상** | ~1.5GB | 리서치 더 필요
| multilingual-e5-base | 768 | 상 | ~1GB |
| paraphrase-multilingual-MiniLM-L12-v2 | 384 | 중 | ~0.5GB |

### 왜 EXAONE인가?
- LG AI Research 개발 (한국 기업)
- 한국어 벤치마크 1위급
- 2.4B 모델도 한국어 성능 우수
- Apache 2.0 라이선스 (상업적 사용 가능)
- 구조화 출력 잘 따름

---

## 파인튜닝 설정 (RTX 3070 8GB)

### Stage 1: EXAONE-3.5-2.4B 로컬 학습

```python
# config.py
class FinetuneConfig:
    # 모델
    base_model = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"

    # QLoRA 설정
    load_in_4bit = True
    lora_r = 16
    lora_alpha = 32
    lora_dropout = 0.05

    # 학습 설정 (8GB VRAM 최적화)
    batch_size = 4                        # 2.4B라 여유 있음
    gradient_accumulation_steps = 4       # 실효 배치: 16
    max_seq_length = 2048
    gradient_checkpointing = True

    # 학습 파라미터
    num_epochs = 3
    learning_rate = 2e-4
    warmup_ratio = 0.03
```

### Stage 2: EXAONE-3.5-7.8B 클라우드 학습

```python
# 클라우드 GPU (A100 40GB) 설정
class FinetuneConfigCloud:
    base_model = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct"

    load_in_4bit = True  # 또는 False (LoRA)
    batch_size = 4
    gradient_accumulation_steps = 4
    max_seq_length = 4096
```

### 클라우드 GPU 옵션

| 서비스 | GPU | 비용 | 특징 |
|--------|-----|------|------|
| **Google Colab Pro+** | A100 40GB | ~$50/월 | 간편, 제한 있음 |
| **RunPod** | A100 80GB | ~$1.5/시간 | 유연, 종량제 |
| **Vast.ai** | A100 40GB | ~$1/시간 | 저렴, 커뮤니티 |
| **Lambda Labs** | A100 40GB | ~$1.5/시간 | 안정적 |

---

## 성능 예측 요약

| 단계 | 모델 | 환경 | 예상 성능 | 비용 |
|------|------|------|----------|------|
| **Stage 1** | EXAONE-3.5-2.4B | 로컬 RTX 3070 | **70-80%** | 무료 |
| **Stage 2** | EXAONE-3.5-7.8B | 클라우드 | **85-95%** | ~$3-5 |

*성능 = GPT-4o-mini 대비 상대적 품질*
*한국어 특화 모델로 기존 Qwen 대비 10% 이상 성능 향상 예상*

---

## 주의사항

### 임베딩 차원 호환성
- 현재 pgvector 테이블: 512차원 (OpenAI text-embedding-3-small)
- KoSimCSE-roberta: **768차원**
- **테이블 마이그레이션 필요** (512 → 768)

### VRAM 관리 (RTX 3070 8GB)
- CV 모델 + EXAONE 2.4B 동시 로드: **가능** (여유 있음, ~6GB)
- CV 모델 + EXAONE 7.8B 동시 로드: 불가 (추론 전용으로도 빠듯)
- 추론 시 4bit 양자화 필수
- 임베딩 (KoSimCSE): ~1.5GB 추가

### 롤백 전략
- 환경변수 `LLM_PROVIDER=openai`로 즉시 롤백 가능

---

## 검증 방법

1. **Stage 1 검증 (EXAONE 2.4B)**
   - LocalLLMClient가 FloorPlanAnalysis 스키마 출력하는지 확인
   - 5-10개 샘플로 품질 평가
   - GPT-4o-mini 결과와 비교

2. **Stage 2 전환 기준**
   - EXAONE 2.4B 성능이 GPT-4o-mini의 70% 미만
   - 핵심 필드(compliance, design_evaluation) 품질 부족
   - 사용자 피드백 기반 판단

3. **최종 통합 테스트**
   - POST /analyze 엔드포인트 테스트
   - 추론 시간 측정 (목표: 30초 이내)
   - 출력 품질 비교 (OpenAI vs 로컬)

---

## 진행 순서

```
1. Phase 1-3: 추상화 레이어 및 서비스 수정 (OpenAI로 테스트)
      ↓
2. Phase 4: 파인튜닝 인프라 구축
      ↓
3. Stage 1: EXAONE-3.5-2.4B 로컬 파인튜닝 및 검증
      ↓
4. 성능 평가: 70-80% 달성 여부 확인
      ↓
   ├─ 충분함 → 로컬 모델로 운영
   └─ 부족함 → Stage 2: 클라우드 EXAONE-7.8B 학습 (RunPod $50)
```

## 최종 모델 구성

| 용도 | 모델 |
|------|------|
| **LLM (Stage 1)** | LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct |
| **LLM (Stage 2)** | LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct |
| **Embedding** | BM-K/KoSimCSE-roberta |
