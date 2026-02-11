# Qwen3 파인튜닝용 학습 데이터 생성 파이프라인 v2

## Context

ARAE 시스템은 도면 분석 시 GPT-4o-mini를 사용하여 topology_graph.json → FloorPlanAnalysis(llm_analysis.json)를 생성합니다.
이를 로컬 Qwen3 모델로 대체하기 위해, **Dual-Model Teacher 방식**으로 학습 데이터를 생성하고 품질 비교 후 최적 데이터셋으로 파인튜닝합니다.

**핵심 변경사항 (v1 대비)**:
- 9,991장 전체 → **2,000장 대표 샘플** (모델당)
- 단일 모델(GPT-4o-mini) → **OpenAI GPT-4o + Gemini 3 Pro 듀얼 모델**
- 품질 비교 후 우수 데이터셋 선택
- 실행 환경 분리: **로컬 GPU (Phase 0-1) + RunPod A100 (Phase 2-6)**
- 임베딩 모델: OpenAI → **Qwen3-Embedding-0.6B** (학습-추론 일관성)
- Qwen3 파인튜닝 단계 통합 (Phase 6)

## 전략

```
=== 로컬 환경 (Phase 0-1) ===
Phase 0: 데이터 샘플링 (로컬 CPU, ~1분)
  9,991장 중 2,000장 대표 샘플 선정 → sampled_images.json

Phase 1: CV 추론 (로컬 GPU, ~6-12시간)
  2,000장 → InferencePipeline → topology_graph.json

Phase 1.5: RunPod 업로드 (~10-30분)
  sampled_images.json + topology_graph.json 2,000개 → RunPod Volume

=== RunPod A100 환경 (Phase 2-6) ===
Phase 2: RAG 컨텍스트 생성 (A100 GPU, ~15초)
  사내_평가_문서 15개 chunk → Qwen3-Embedding-0.6B (768차원) → cosine similarity → rag_context

Phase 3A: OpenAI GPT-4o 라벨링 (API, ~4-8시간, ~$40-60)
  topology + rag_context → GPT-4o → llm_analysis_openai.json (2,000개)

Phase 3B: Gemini 3 Pro 라벨링 (API, ~4-8시간, ~$15-30)
  topology + rag_context → Gemini 3 Pro → llm_analysis_gemini.json (2,000개)

Phase 4: 품질 비교 평가 (~30분)
  100개 샘플 자동 + 수동 평가 → 최적 데이터셋 선택

Phase 5: JSONL 변환 (~2분)
  선택된 데이터셋 → train.jsonl (90%) + val.jsonl (10%)

Phase 6: Qwen3 파인튜닝 (RunPod A100, ~2-4시간)
  Unsloth + LoRA로 Qwen3-8B 파인튜닝 → 모델 저장
```

## 파일 구조

```
python/CV/llm_finetuning/              # 신규 생성
├── config.py                          # 통합 설정 (경로, 모델, API 키)
├── step0_sample_images.py             # Phase 0: 대표 샘플 2,000장 선정
├── step1_cv_batch.py                  # Phase 1: CV 배치 추론
├── step2_rag_context.py               # Phase 2: RAG 컨텍스트 생성
├── step3a_openai_labeling.py          # Phase 3A: OpenAI GPT-4o 라벨링
├── step3b_gemini_labeling.py          # Phase 3B: Gemini 3 Pro 라벨링
├── step4_quality_compare.py           # Phase 4: 품질 비교 평가
├── step5_build_jsonl.py               # Phase 5: JSONL 변환
├── step6_qwen3_finetune.py            # Phase 6: Qwen3 파인튜닝
├── run_all.py                         # 오케스트레이터 (단계별/전체 실행)
└── utils/
    ├── __init__.py
    ├── progress_tracker.py            # 중단/재개 지원
    ├── local_vector_search.py         # numpy 기반 로컬 벡터 검색
    ├── retry.py                       # API 재시도 (exponential backoff)
    └── quality_metrics.py             # 품질 평가 메트릭 함수
```

출력 디렉토리:
```
python/training_data/                  # 신규 생성
├── progress/                          # 단계별 진행률 JSON
├── sampled_images.json                # 선정된 2,000장 이미지 목록
├── output/{image_stem}/               # 이미지별 중간 산출물
│   ├── topology_graph.json            # Phase 1
│   ├── rag_context.json               # Phase 2
│   ├── llm_analysis_openai.json       # Phase 3A
│   └── llm_analysis_gemini.json       # Phase 3B
├── embedding_cache.npy                # chunk 임베딩 캐시
├── quality_report.json                # Phase 4 품질 비교 리포트
├── selected_model.txt                 # 선택된 모델 ("openai" 또는 "gemini")
├── train.jsonl                        # 최종 학습 데이터
├── val.jsonl                          # 최종 검증 데이터
├── stats_report.json                  # 통계 리포트
└── qwen3_finetuned/                   # Phase 6 모델 출력
    ├── adapter_model/                 # LoRA 어댑터
    └── merged_model/                  # 머지된 전체 모델 (선택사항)
```

---

## 상세 구현 계획

### 0. `CV/llm_finetuning/config.py` - 통합 설정

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class PipelineConfig:
    # === 경로 설정 (RunPod 환경) ===
    IMAGE_DIR: Path = Path("/workspace/data/APT_FP_Cleaned/training")
    OUTPUT_DIR: Path = Path("/workspace/training_data/output")
    RAG_DOC_PATH: Path = Path("/workspace/python/CV/rag_data/사내_평가_문서.json")
    PROJECT_ROOT: Path = Path("/workspace/python")

    # === 샘플링 설정 ===
    TOTAL_IMAGES: int = 9991
    SAMPLE_SIZE: int = 2000
    RANDOM_SEED: int = 42
    STRATIFY_BY: str = "filename_prefix"  # 파일명 접두사로 층화 샘플링

    # === CV 추론 설정 (로컬 GPU) ===
    SAVE_VISUALIZATION: bool = False
    CUDA_CACHE_CLEAR_INTERVAL: int = 50  # 매 50건마다 캐시 정리

    # === RAG 임베딩 설정 (Qwen3-Embedding) ===
    EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-0.6B"
    EMBEDDING_DIM: int = 768              # 768 또는 1024 (768 권장)
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_MAX_LENGTH: int = 512
    TOP_K: int = 5

    # === OpenAI API 설정 ===
    OPENAI_API_KEY: Optional[str] = None  # 환경변수에서 로드
    OPENAI_MODEL: str = "gpt-4o"          # 최고 품질 모델
    OPENAI_TEMPERATURE: float = 0.1
    OPENAI_MAX_RETRIES: int = 3
    OPENAI_CONCURRENT_REQUESTS: int = 5   # 동시 요청 수

    # === Gemini API 설정 ===
    GOOGLE_API_KEY: Optional[str] = None  # 환경변수에서 로드
    GEMINI_MODEL: str = "gemini-3-pro"    # Gemini 3 Pro
    GEMINI_TEMPERATURE: float = 0.1
    GEMINI_MAX_RETRIES: int = 3
    GEMINI_CONCURRENT_REQUESTS: int = 5

    # === 품질 비교 설정 ===
    QUALITY_SAMPLE_SIZE: int = 100        # 품질 비교용 샘플 수
    MIN_SCHEMA_COMPLIANCE: float = 0.95   # 최소 스키마 준수율

    # === JSONL 설정 ===
    TRAIN_RATIO: float = 0.9

    # === Qwen3 파인튜닝 설정 ===
    QWEN3_BASE_MODEL: str = "Qwen/Qwen3-8B"
    LORA_R: int = 64
    LORA_ALPHA: int = 128
    LORA_DROPOUT: float = 0.05
    LEARNING_RATE: float = 2e-4
    NUM_EPOCHS: int = 3
    BATCH_SIZE: int = 2                   # A100 80GB 기준
    GRADIENT_ACCUMULATION: int = 8        # effective batch = 16
    MAX_SEQ_LENGTH: int = 4096
    WARMUP_RATIO: float = 0.03
    SAVE_STEPS: int = 100
    LOGGING_STEPS: int = 10
```

### 1. `CV/llm_finetuning/step0_sample_images.py` - 대표 샘플 2,000장 선정

**목적**: 9,991장에서 다양성을 보장하는 2,000장 선정

**로직**:
- 파일명 접두사 기반 층화 샘플링 (아파트 단지/동별 균등 분포)
- 파일 크기 분포 유지 (극단적 크기 제외)
- 결과를 `sampled_images.json`에 저장 (재현 가능)

```python
def sample_images(config: PipelineConfig) -> List[Path]:
    """
    층화 샘플링으로 2,000장 선정

    전략:
    1. 파일명 접두사(아파트 단지)별 그룹화
    2. 각 그룹에서 비례 할당
    3. 그룹 수 < 비례 할당분인 경우 전수 포함
    4. 잔여분은 가장 큰 그룹에서 랜덤 추출
    """
    all_images = sorted(config.IMAGE_DIR.glob("*.PNG"))
    # ... 층화 샘플링 로직
    # 결과를 sampled_images.json에 저장
    return sampled_images
```

### 2. `CV/llm_finetuning/step1_cv_batch.py` - CV 배치 추론 (로컬 GPU)

**실행 환경**: 로컬 GPU (RTX 3090, 4090, A6000 등)

**로직**:
- 기존 `InferencePipeline` 재사용 (`python/CV/cv_inference/pipeline.py`)
- `save_visualization=False`로 시각화 건너뛰기 (속도 2-3배 향상)
- 중단/재개: `progress/cv_batch_progress.json`에 완료 목록 관리
- 매 50건마다 `torch.cuda.empty_cache()` 호출
- 실패 이미지는 `failed_images` 목록에 기록 후 continue
- topology_graph.json만 `training_data/output/{stem}/`에 저장
- **2,000장 대상** (sampled_images.json 참조)

**GPU 메모리 요구사항**:
- RTX 3090 (24GB): 배치 크기 1, 메모리 사용 ~18-20GB
- RTX 4090 (24GB): 배치 크기 1, 메모리 사용 ~18-20GB
- A6000 (48GB): 배치 크기 2 가능

**예상 시간** (로컬 GPU 기준):
- RTX 3090/4090: ~6-12시간 (이미지당 ~10-20초)
- A6000: ~4-8시간 (이미지당 ~7-15초)

**야간 실행 권장**:
```bash
# tmux 세션에서 실행
tmux new-session -s cv_batch
python CV/llm_finetuning/step1_cv_batch.py
# Ctrl+B, D로 detach
```

### 3. `CV/llm_finetuning/step2_rag_context.py` - RAG 컨텍스트 생성

**핵심 변경**: OpenAI embedding → **Qwen3-Embedding-0.6B** (학습-추론 일관성 확보)

**로직**:
- `사내_평가_문서.json`의 15개 chunk 로드
- **Qwen3-Embedding-0.6B**로 1회 임베딩 → `embedding_cache.npy` 캐시 (768차원)
- 2,000개 topology별 쿼리 생성 → numpy cosine similarity → TOP_K=5
- `rag_context.json` 저장

**핵심 구현**:
```python
from transformers import AutoModel, AutoTokenizer
import torch
import torch.nn.functional as F
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

class Qwen3EmbeddingManager:
    """Qwen3-Embedding-0.6B 임베딩 매니저 (768차원)"""

    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        self.model.eval()

    def embed_text(self, text: str) -> np.ndarray:
        """단일 텍스트 임베딩"""
        with torch.no_grad():
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            ).to(self.device)

            outputs = self.model(**inputs)
            # Mean pooling
            embeddings = outputs.last_hidden_state.mean(dim=1)
            embeddings = F.normalize(embeddings, p=2, dim=1)

            return embeddings.cpu().numpy()[0]

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """배치 임베딩 (효율적)"""
        all_embeddings = []

        for i in tqdm(range(0, len(texts), batch_size), desc="임베딩 생성"):
            batch_texts = texts[i:i+batch_size]

            with torch.no_grad():
                inputs = self.tokenizer(
                    batch_texts,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=512
                ).to(self.device)

                outputs = self.model(**inputs)
                embeddings = outputs.last_hidden_state.mean(dim=1)
                embeddings = F.normalize(embeddings, p=2, dim=1)

                all_embeddings.append(embeddings.cpu().numpy())

        return np.vstack(all_embeddings)

def run_rag_context_generation(config: PipelineConfig):
    """2,000개 topology에 대해 RAG 컨텍스트 생성"""

    print("=" * 60)
    print("Phase 2: RAG 컨텍스트 생성 (Qwen3-Embedding-0.6B)")
    print("=" * 60)

    # 1. 임베딩 매니저 초기화
    embedding_mgr = Qwen3EmbeddingManager(model_name=config.EMBEDDING_MODEL)
    print(f"✅ 임베딩 모델 로드: {config.EMBEDDING_MODEL} (차원: {config.EMBEDDING_DIM})")

    # 2. 사내 문서 로드 및 임베딩 (1회만)
    cache_path = config.OUTPUT_DIR.parent / "embedding_cache.npy"
    doc_metadata_path = config.OUTPUT_DIR.parent / "doc_metadata.json"

    if cache_path.exists() and doc_metadata_path.exists():
        print("📦 캐시된 임베딩 로드 중...")
        chunk_embeddings = np.load(cache_path)
        chunks = json.loads(doc_metadata_path.read_text(encoding='utf-8'))
        print(f"✅ 캐시 로드 완료: {len(chunks)}개 chunk")
    else:
        print("📄 사내 평가 문서 로드 중...")
        chunks = load_internal_eval_docs(config.RAG_DOC_PATH)  # 15개 chunk
        print(f"✅ {len(chunks)}개 chunk 로드 완료")

        print("🔄 Qwen3-Embedding으로 임베딩 생성 중...")
        chunk_texts = [c['content'] for c in chunks]
        chunk_embeddings = embedding_mgr.embed_batch(
            chunk_texts,
            batch_size=config.EMBEDDING_BATCH_SIZE
        )

        # 캐시 저장
        np.save(cache_path, chunk_embeddings)
        doc_metadata_path.write_text(
            json.dumps(chunks, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        print(f"✅ 임베딩 캐시 저장: {cache_path}")
        print(f"   Shape: {chunk_embeddings.shape}")

    # 3. sampled_images.json 로드
    sampled_images_path = config.OUTPUT_DIR.parent / "sampled_images.json"
    sampled_images = json.loads(sampled_images_path.read_text())
    print(f"✅ {len(sampled_images)}개 이미지에 대해 RAG 컨텍스트 생성 시작")

    # 4. 각 topology별 RAG 검색
    success_count = 0
    failed_count = 0

    for image_stem in tqdm(sampled_images, desc="RAG 검색"):
        try:
            topology_path = config.OUTPUT_DIR / image_stem / "topology_graph.json"
            if not topology_path.exists():
                failed_count += 1
                continue

            topology = json.loads(topology_path.read_text(encoding='utf-8'))

            # 쿼리 생성
            stats = topology.get('statistics', {})
            query_text = (
                f"{stats.get('structure_type', '혼합형')} 건축물 "
                f"{stats.get('bay_count', 0)}Bay "
                f"침실 {stats.get('room_count', 0)}개"
            )

            # 쿼리 임베딩
            query_emb = embedding_mgr.embed_text(query_text)

            # Cosine similarity 계산
            similarities = cosine_similarity([query_emb], chunk_embeddings)[0]
            top_k_idx = np.argsort(similarities)[-config.TOP_K:][::-1]

            # RAG 컨텍스트 구성
            rag_context = {
                "query": query_text,
                "retrieved_chunks": [
                    {
                        "rank": i+1,
                        "content": chunks[idx]['content'],
                        "similarity": float(similarities[idx]),
                        "source": chunks[idx].get('source', 'unknown')
                    }
                    for i, idx in enumerate(top_k_idx)
                ]
            }

            # 저장
            rag_path = config.OUTPUT_DIR / image_stem / "rag_context.json"
            rag_path.parent.mkdir(parents=True, exist_ok=True)
            rag_path.write_text(
                json.dumps(rag_context, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )

            success_count += 1

        except Exception as e:
            print(f"⚠️  {image_stem} 실패: {e}")
            failed_count += 1

    print("\n" + "=" * 60)
    print(f"✅ RAG 컨텍스트 생성 완료!")
    print(f"   성공: {success_count}개")
    print(f"   실패: {failed_count}개")
    print("=" * 60)

def load_internal_eval_docs(doc_path: Path) -> List[dict]:
    """사내_평가_문서.json 로드"""
    data = json.loads(doc_path.read_text(encoding='utf-8'))
    # 15개 chunk로 구조화 (실제 구조에 맞게 조정 필요)
    return data.get('chunks', data)
```

**예상 시간** (A100 기준):
- 15개 chunk 임베딩: **~0.5초** (1회만)
- 2,000개 쿼리 임베딩: **~10초** (batch=32)
- 2,000개 검색 (numpy): **~3초**
- **총: ~15초** (기존 5분 → 20배 단축!)

**메모리 사용** (A100 80GB 기준):
- Qwen3-Embedding-0.6B: **~1.2GB**
- 임베딩 캐시 (15 + 2000) × 768 × 4bytes: **~6MB**
- **총: ~1.5GB** (매우 여유)

### 4. `CV/llm_finetuning/step3a_openai_labeling.py` - OpenAI GPT-4o 라벨링

**모델 선택 근거**: GPT-4o는 GPT-4o-mini 대비 ~3배 비싸지만 구조화 출력 품질이 현저히 높음. 2,000개로 수량을 줄였으므로 비용 허용 범위.

**핵심 구현**:
```python
class OpenAILabeler:
    def __init__(self, config: PipelineConfig):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.OPENAI_MODEL  # "gpt-4o"

    async def label_single(self, topology_data: dict, rag_context: str) -> FloorPlanAnalysis:
        """
        단일 topology에 대해 GPT-4o로 FloorPlanAnalysis 생성

        기존 코드 재사용:
        - SYSTEM_PROMPT (python/CV/rag_system/prompts.py)
        - build_analysis_prompt() (python/CV/rag_system/prompts.py)
        - FloorPlanAnalysis (python/CV/rag_system/schemas.py)
        """
        prompt = build_analysis_prompt(topology_data, rag_context)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=FloorPlanAnalysis,
            temperature=0.1
        )
        return response.choices[0].message.parsed

    async def label_batch(self, items: List[dict]) -> List[FloorPlanAnalysis]:
        """
        asyncio.Semaphore로 동시 요청 수 제한 (5개)
        재시도: exponential backoff (2→4→8초), 429 시 60초 대기
        """
```

**비용 추정**:
- 입력: topology(~1.5K tokens) + rag_context(~1K tokens) + system_prompt(~500 tokens) = ~3K tokens
- 출력: FloorPlanAnalysis JSON ~1.5K tokens
- GPT-4o: 입력 $2.50/1M, 출력 $10.00/1M
- 2,000건: (3K * 2000 * $2.50 + 1.5K * 2000 * $10.00) / 1M = **~$45**

### 5. `CV/llm_finetuning/step3b_gemini_labeling.py` - Gemini 3 Pro 라벨링

**핵심 차이점**:
- Google AI SDK (`google-generativeai`) 사용
- Gemini 3 Pro는 `response_schema` 파라미터로 구조화 출력 지원
- Pydantic 스키마를 JSON Schema로 변환하여 전달
- 프롬프트는 OpenAI와 **동일** (공정한 비교를 위해)

**핵심 구현**:
```python
import google.generativeai as genai

class GeminiLabeler:
    def __init__(self, config: PipelineConfig):
        genai.configure(api_key=config.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,  # "gemini-3-pro"
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=self._build_schema()
            )
        )

    def _build_schema(self) -> dict:
        """FloorPlanAnalysis Pydantic 스키마 → Gemini JSON Schema 변환"""
        return FloorPlanAnalysis.model_json_schema()

    async def label_single(self, topology_data: dict, rag_context: str) -> FloorPlanAnalysis:
        """
        동일한 SYSTEM_PROMPT + build_analysis_prompt() 사용
        Gemini 3 Pro API로 구조화 출력 생성
        """
        prompt = build_analysis_prompt(topology_data, rag_context)
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

        response = self.model.generate_content(full_prompt)
        result_dict = json.loads(response.text)
        return FloorPlanAnalysis(**result_dict)

    async def label_batch(self, items: List[dict]) -> List[FloorPlanAnalysis]:
        """
        asyncio.Semaphore로 동시 요청 수 제한 (5개)
        Gemini API rate limit 대응
        """
```

**비용 추정**:
- Gemini 3 Pro: 가격은 공개된 시점의 최신 요금 참조
- 예상: 입력 ~$1-2/1M, 출력 ~$5-10/1M
- 2,000건 예상: **~$20-40**

### 6. `CV/llm_finetuning/step4_quality_compare.py` - 품질 비교 평가

**평가 방법론**: 100개 랜덤 샘플에 대해 자동 + 수동 평가

**자동 평가 메트릭** (8개):

| 메트릭 | 설명 | 측정 방법 |
|--------|------|----------|
| schema_compliance | Pydantic 스키마 준수율 | FloorPlanAnalysis 파싱 성공률 |
| field_completeness | 필수 필드 완성률 | None/빈값이 아닌 필드 비율 |
| space_count_accuracy | 공간 수 정합성 | topology의 nodes 수와 spaces 수 비교 |
| bay_count_consistency | Bay 수 일관성 | topology 통계와 분석 결과 일치 여부 |
| compliance_reasoning | 적합성 평가 논리성 | compliant_items + non_compliant_items 수 > 0 |
| analysis_depth | 분석 깊이 | spaces[].evaluation_comment 평균 길이 |
| recommendation_quality | 개선 제안 품질 | recommendations 수 및 구체성 (길이) |
| json_validity | JSON 유효성 | 파싱 오류 없는 비율 |

**비교 알고리즘**:
```python
def compare_quality(openai_results: List, gemini_results: List, sample_ids: List[str]) -> QualityReport:
    """
    100개 샘플에 대해 8개 메트릭으로 비교

    반환:
    - 메트릭별 점수 (OpenAI vs Gemini)
    - 가중 평균 종합 점수
    - 승자 결정 (차이가 5% 이내면 비용 효율 높은 쪽 선택)
    """
    metrics = {}
    for metric_fn in [schema_compliance, field_completeness, space_count_accuracy,
                      bay_count_consistency, compliance_reasoning, analysis_depth,
                      recommendation_quality, json_validity]:
        openai_score = metric_fn(openai_results, sample_ids)
        gemini_score = metric_fn(gemini_results, sample_ids)
        metrics[metric_fn.__name__] = {
            "openai": openai_score,
            "gemini": gemini_score
        }

    # 가중 평균 (schema_compliance 30%, field_completeness 20%, 나머지 각 ~7%)
    weights = {
        "schema_compliance": 0.30,
        "field_completeness": 0.20,
        "space_count_accuracy": 0.10,
        "bay_count_consistency": 0.10,
        "compliance_reasoning": 0.10,
        "analysis_depth": 0.07,
        "recommendation_quality": 0.06,
        "json_validity": 0.07
    }

    openai_total = sum(metrics[k]["openai"] * w for k, w in weights.items())
    gemini_total = sum(metrics[k]["gemini"] * w for k, w in weights.items())

    # 5% 이내 차이 → 비용 효율 높은 쪽 선택
    if abs(openai_total - gemini_total) < 0.05:
        winner = "gemini"  # 비용 효율
    else:
        winner = "openai" if openai_total > gemini_total else "gemini"

    return QualityReport(metrics=metrics, winner=winner, ...)
```

**출력**: `quality_report.json` + `selected_model.txt`

### 7. `CV/llm_finetuning/step5_build_jsonl.py` - JSONL 변환

선택된 모델의 결과를 학습 데이터로 변환:

```jsonl
{
  "messages": [
    {"role": "system", "content": "<SYSTEM_PROMPT>"},
    {"role": "user", "content": "<build_analysis_prompt(topology, rag_context)>"},
    {"role": "assistant", "content": "<llm_analysis JSON>"}
  ]
}
```

- `selected_model.txt`에서 선택된 모델 확인
- 해당 모델의 llm_analysis 파일만 수집
- 3개 파일(topology, rag_context, llm_analysis) 모두 존재하는 이미지만 수집
- FloorPlanAnalysis 스키마 유효성 검증
- 셔플 + train/val 분할 (90:10, seed=42)
- 통계 리포트 생성

### 8. `CV/llm_finetuning/step6_qwen3_finetune.py` - Qwen3 파인튜닝

**RunPod A100 80GB 환경에서 실행**

**프레임워크**: Unsloth (LoRA 최적화, 2배 빠른 학습, 메모리 60% 절감)

```python
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import load_dataset

def run_finetune(config: PipelineConfig):
    # 1. 모델 로드 (4-bit 양자화 + LoRA)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config.QWEN3_BASE_MODEL,  # "Qwen/Qwen3-8B"
        max_seq_length=config.MAX_SEQ_LENGTH,  # 4096
        load_in_4bit=True,
        dtype=None,  # auto-detect
    )

    # 2. LoRA 어댑터 추가
    model = FastLanguageModel.get_peft_model(
        model,
        r=config.LORA_R,                      # 64
        lora_alpha=config.LORA_ALPHA,          # 128
        lora_dropout=config.LORA_DROPOUT,      # 0.05
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    # 3. 데이터 로드
    dataset = load_dataset("json", data_files={
        "train": str(config.OUTPUT_DIR.parent / "train.jsonl"),
        "validation": str(config.OUTPUT_DIR.parent / "val.jsonl"),
    })

    # 4. 채팅 템플릿 적용
    def apply_chat_template(example):
        text = tokenizer.apply_chat_template(
            example["messages"],
            tokenize=False,
            add_generation_prompt=False
        )
        return {"text": text}

    dataset = dataset.map(apply_chat_template)

    # 5. 학습 설정
    training_args = TrainingArguments(
        output_dir=str(config.OUTPUT_DIR.parent / "qwen3_finetuned" / "checkpoints"),
        num_train_epochs=config.NUM_EPOCHS,              # 3
        per_device_train_batch_size=config.BATCH_SIZE,    # 2
        gradient_accumulation_steps=config.GRADIENT_ACCUMULATION,  # 8
        learning_rate=config.LEARNING_RATE,               # 2e-4
        warmup_ratio=config.WARMUP_RATIO,                 # 0.03
        lr_scheduler_type="cosine",
        logging_steps=config.LOGGING_STEPS,               # 10
        save_steps=config.SAVE_STEPS,                     # 100
        save_total_limit=3,
        fp16=True,
        optim="adamw_8bit",
        seed=42,
        report_to="none",
        evaluation_strategy="steps",
        eval_steps=100,
    )

    # 6. SFTTrainer로 학습
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        args=training_args,
        dataset_text_field="text",
        max_seq_length=config.MAX_SEQ_LENGTH,
        packing=True,  # 짧은 시퀀스 패킹으로 효율 극대화
    )

    trainer.train()

    # 7. LoRA 어댑터 저장
    model.save_pretrained(str(config.OUTPUT_DIR.parent / "qwen3_finetuned" / "adapter_model"))
    tokenizer.save_pretrained(str(config.OUTPUT_DIR.parent / "qwen3_finetuned" / "adapter_model"))

    # 8. (선택) 머지된 전체 모델 저장
    # merged_model = model.merge_and_unload()
    # merged_model.save_pretrained(str(config.OUTPUT_DIR.parent / "qwen3_finetuned" / "merged_model"))
```

**A100 80GB 메모리 추정**:
- Qwen3-8B 4-bit: ~5GB
- LoRA 어댑터: ~0.5GB
- 활성화 메모리 (batch=2, seq=4096): ~15GB
- 옵티마이저 상태: ~5GB
- **총 사용량: ~25-30GB** (A100 80GB 충분)

### 9. `CV/llm_finetuning/run_all.py` - 오케스트레이터

```bash
# 전체 실행
python CV/llm_finetuning/run_all.py

# 특정 Phase만 실행
python CV/llm_finetuning/run_all.py --step 0        # 샘플링만
python CV/llm_finetuning/run_all.py --step 1        # CV만
python CV/llm_finetuning/run_all.py --step 2        # RAG만
python CV/llm_finetuning/run_all.py --step 3a       # OpenAI만
python CV/llm_finetuning/run_all.py --step 3b       # Gemini만
python CV/llm_finetuning/run_all.py --step 3a,3b    # 두 모델 동시 (병렬)
python CV/llm_finetuning/run_all.py --step 4        # 품질 비교만
python CV/llm_finetuning/run_all.py --step 5        # JSONL만
python CV/llm_finetuning/run_all.py --step 6        # Qwen3 학습만
python CV/llm_finetuning/run_all.py --step 1,2,3a,3b,4,5,6  # 전체
```

### 10. `CV/llm_finetuning/utils/` - 유틸리티

**progress_tracker.py**: JSON 기반 진행률 추적, 중단 시 재개 가능
**local_vector_search.py**: numpy cosine similarity 기반 TOP-K 검색
**retry.py**: API 재시도 데코레이터 (exponential backoff + rate limit 처리)
**quality_metrics.py**: 8개 품질 메트릭 함수 정의

---

## 로컬 → RunPod 워크플로우

### 로컬 환경 (Phase 0-1)

**필요 사항**:
- GPU: RTX 3090/4090 (24GB) 이상
- 디스크: ~50GB (이미지 + 중간 산출물)
- Python 3.11

**로컬 설정**:
```bash
# 프로젝트 루트에서
cd python

# 의존성 설치
pip install -r requirements.txt

# Phase 0-1 실행
python CV/llm_finetuning/step0_sample_images.py
python CV/llm_finetuning/step1_cv_batch.py  # 야간 실행 권장 (6-12시간)
```

**산출물**:
```
python/training_data/
├── sampled_images.json           # 2,000개 이미지 목록
└── output/{image_stem}/
    └── topology_graph.json       # 2,000개 파일
```

### Phase 1.5: RunPod 업로드

**업로드 대상** (~500MB):
```bash
# 로컬에서 실행
# 방법 1: rsync (SSH)
rsync -avz --progress \
  python/training_data/sampled_images.json \
  python/training_data/output/ \
  python/CV/rag_data/사내_평가_문서.json \
  root@runpod-xxx:/workspace/training_data/

# 방법 2: RunPod CLI (추천)
runpod send python/training_data/ /workspace/training_data/

# 방법 3: 수동 업로드 (RunPod Web UI)
# 1. training_data 폴더를 zip 압축
# 2. RunPod Volume에 업로드
# 3. Pod에서 압축 해제
```

**예상 시간**: ~10-30분 (네트워크 속도에 따라)

---

## RunPod A100 환경 설정 (Phase 2-6)

### Pod 설정
```
GPU: NVIDIA A100 80GB SXM
이미지: runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04
디스크: Volume 100GB (/workspace)
네트워크 볼륨: 로컬 업로드 파일 접근
```

### 초기 환경 설정 스크립트
```bash
#!/bin/bash
# RunPod 초기 설정 (Phase 2-6만 실행)

# 1. 프로젝트 클론
cd /workspace
git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN20-FINAL-3TEAM.git
cd SKN20-FINAL-3TEAM/python

# 2. Python 환경
pip install -r requirements.txt

# 3. 추가 의존성 (학습용)
pip install transformers>=4.40.0      # Qwen3-Embedding
pip install torch>=2.0.0              # PyTorch
pip install scikit-learn>=1.3.0       # cosine_similarity
pip install google-generativeai>=0.8.0
pip install unsloth
pip install trl>=0.12.0
pip install datasets>=3.0.0
pip install accelerate>=1.0.0
pip install bitsandbytes>=0.44.0
pip install tqdm>=4.66.0

# 4. 환경변수 설정
cat > .env << 'EOF'
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
EOF

# 5. 업로드된 데이터 확인
ls -lh /workspace/training_data/sampled_images.json
ls -lh /workspace/training_data/output/ | head -10
ls -lh /workspace/python/CV/rag_data/사내_평가_문서.json

# 6. Phase 2부터 실행
python CV/llm_finetuning/run_all.py --step 2,3a,3b,4,5,6
```

**주의사항**:
- ❌ Phase 0-1은 로컬에서 이미 완료
- ✅ Phase 2-6만 RunPod에서 실행
- 💾 Volume에 업로드된 파일 확인 필수

---

## 재사용하는 기존 코드

| 기존 코드 | 용도 | 변경사항 |
|-----------|------|----------|
| `python/CV/cv_inference/pipeline.py` → `InferencePipeline` | CV 추론 | 그대로 사용 |
| `python/CV/cv_inference/config.py` → `InferenceConfig` | CV 설정 | OUTPUT_PATH 오버라이드 |
| `python/CV/rag_system/llm_client.py` → `OpenAIClient` | OpenAI LLM 호출 | 그대로 사용 |
| `python/CV/rag_system/schemas.py` → `FloorPlanAnalysis` | 구조화 출력 스키마 | 그대로 사용 |
| `python/CV/rag_system/prompts.py` → `SYSTEM_PROMPT`, `build_analysis_prompt` | 프롬프트 | 그대로 사용 |
| `python/CV/rag_system/config.py` → `RAGConfig` | API 키 등 설정 | 그대로 사용 |

**제거된 의존성**:
- ~~`python/CV/rag_system/embeddings.py` → `EmbeddingManager`~~ → **Qwen3EmbeddingManager**로 대체 (step2에 직접 구현)

---

## 추가 의존성 (requirements-training.txt)

```
# Gemini API
google-generativeai>=0.8.0

# Qwen3 생태계 (임베딩 + 파인튜닝)
transformers>=4.40.0              # Qwen3-Embedding 로드
torch>=2.0.0                      # PyTorch
scikit-learn>=1.3.0               # cosine_similarity
unsloth                           # Qwen3 파인튜닝 최적화
trl>=0.12.0                       # SFTTrainer
datasets>=3.0.0                   # JSONL 로드
accelerate>=1.0.0                 # 분산 학습
bitsandbytes>=0.44.0              # 4-bit 양자화
peft>=0.13.0                      # LoRA 어댑터

# 비동기 API 호출
aiohttp>=3.9.0
asyncio

# 유틸리티
tqdm>=4.66.0                      # 진행률 표시
```

---

## 예상 비용 및 시간

| Phase | 환경 | 소요시간 | 비용 | 비고 |
|-------|------|---------|------|------|
| **로컬 작업** | | | | |
| 0. 샘플링 | 로컬 CPU | ~1분 | $0 | 층화 샘플링 |
| 1. CV 추론 | **로컬 GPU** | **~6-12시간** | **$0** | 야간 실행 권장 |
| 1.5. 업로드 | 네트워크 | ~10-30분 | $0 | ~500MB |
| **RunPod 작업** | | | | |
| 2. RAG 컨텍스트 | A100 GPU | **~15초** | $0 | Qwen3-Embedding |
| 3A. OpenAI GPT-4o | A100 CPU | ~4-8시간 | **~$40-60** | API 병목 |
| 3B. Gemini 3 Pro | A100 CPU | ~4-8시간 | **~$20-40** | API 병목 |
| 4. 품질 비교 | A100 CPU | ~30분 | $0 | 메트릭 계산 |
| 5. JSONL 변환 | A100 CPU | ~2분 | $0 | 데이터 변환 |
| 6. Qwen3 학습 | A100 GPU | ~2-4시간 | RunPod 비용 | GPU 병목 |
| **합계** | | **~17-33시간** | **API: ~$60-100 + RunPod: ~$3-10** | - |

**RunPod A100 비용**: ~$1.64/hr (spot) ~ $2.49/hr (on-demand)
- Phase 2-6 GPU 시간: ~2-4시간 (Phase 1 제외!) → **~$3-10**
- 로컬 GPU로 Phase 1 실행 → **RunPod 비용 50-70% 절감** 🎉

**총 비용: ~$63-110** (기존 ~$68-125 대비 절감)

**비용 분석**:
- 로컬 GPU 전력비: ~0.5kWh × 10시간 × $0.15/kWh = **~$0.75** (무시 가능)
- RunPod 비용 절감: ~$5-15 (Phase 1을 로컬에서 실행)
- **순절감액: ~$4-14**

**성능 개선**:
- Phase 2 속도: 5분 → **15초** (20배 단축) 🚀
- 임베딩 비용: $0.01 → **$0** (완전 무료) 💰
- RunPod 비용: $8-25 → **$3-10** (50-70% 절감) 💸
- 학습-추론 일관성: **100% 보장** ✅

---

## Phase 3A/3B 병렬 실행 전략

3A(OpenAI)와 3B(Gemini)는 **완전 독립적**이므로 병렬 실행:

```bash
# 방법 1: tmux 분할
tmux new-session -s labeling
# Pane 1:
python CV/llm_finetuning/step3a_openai_labeling.py
# Pane 2:
python CV/llm_finetuning/step3b_gemini_labeling.py

# 방법 2: nohup 백그라운드
nohup python CV/llm_finetuning/step3a_openai_labeling.py > logs/openai.log 2>&1 &
nohup python CV/llm_finetuning/step3b_gemini_labeling.py > logs/gemini.log 2>&1 &
```

이렇게 하면 Phase 3 전체 시간이 ~4-8시간 (병렬)으로 단축됩니다.

---

## 위험 요소 및 대응

| 위험 | 대응 |
|------|------|
| GPU OOM (CV 추론) | 이미지별 개별 처리 + 매 50건 `torch.cuda.empty_cache()` |
| 장시간 실행 중 RunPod 중단 | progress.json 기반 중단/재개 + Volume 영구 스토리지 |
| OpenAI Rate Limit | exponential backoff + 429 시 60초 대기 + Semaphore(5) |
| Gemini Rate Limit | 동일 전략 + Gemini 고유 quota 확인 |
| Structured output 파싱 실패 | 텍스트 응답 → JSON 수동 파싱 fallback |
| 일부 이미지 CV 실패 | try/except 격리 + failed_images 기록 |
| 두 모델 품질이 거의 동일 | 5% 이내 차이 시 비용 효율 높은 쪽 선택 |
| Qwen3 학습 중 OOM | gradient checkpointing + batch=2 + accumulation=8 |
| Qwen3 과적합 | val loss 모니터링 + early stopping 고려 |
| RunPod Volume 용량 부족 | 중간 산출물 정리 + 100GB Volume 확보 |

---

## 검증 방법

### Phase별 검증

**로컬 환경**:
1. **Phase 0**:
   - sampled_images.json이 정확히 2,000개인지 확인
   - 층화 샘플링 분포 검증 (아파트 단지별 균등 분포)
2. **Phase 1**:
   - 10장 샘플로 CV 파이프라인 테스트 → topology_graph.json 생성 확인
   - GPU 메모리 사용량 모니터링 (nvidia-smi)
   - 2,000개 전체 완료 후 실패 이미지 확인
3. **Phase 1.5**:
   - 업로드 전 데이터 무결성 확인 (파일 수, 크기)
   - 압축 시 손상 여부 확인

**RunPod 환경**:
3. **Phase 2**:
   - Qwen3-Embedding 정상 로드 확인 (768차원)
   - 임베딩 캐시 생성 확인 (embedding_cache.npy)
   - RAG 컨텍스트 5개 수동 검토 → 관련성 확인
   - 유사도 점수 분포 확인 (TOP-5 평균 > 0.7 권장)
4. **Phase 3A/3B**: 각 10장 샘플로 라벨링 테스트 → FloorPlanAnalysis 파싱 확인
5. **Phase 4**: quality_report.json 메트릭 확인 → 승자 결정 근거 검토
6. **Phase 5**: train.jsonl 랜덤 10개 샘플 수동 검토 + 스키마 전수 검사
7. **Phase 6**: val loss 수렴 확인 + 10개 샘플 추론 품질 수동 평가

### 최종 검증

- 파인튜닝된 Qwen3 모델로 테스트셋 추론 실행
- GPT-4o/Gemini 3 Pro 원본 출력과 Qwen3 출력 비교 (BLEU, ROUGE, 또는 수동 평가)
- FloorPlanAnalysis 스키마 준수율 95%+ 확인

---

## 구현 순서

### 로컬 환경 (Day 1-2)
```
Day 1 (로컬):
1. config.py + utils/ (인프라) ──────────────────────────── 2-3시간
2. step0_sample_images.py → 실행 → sampled_images.json ── 1시간
3. step1_cv_batch.py → 10장 테스트 ─────────────────────── 1시간
4. step1_cv_batch.py → 전체 실행 (야간) ────────────────── 시작

Day 2 (로컬):
5. step1_cv_batch.py 완료 확인 ──────────────────────────── 오전
6. 결과 검증 (topology_graph.json 10개 샘플 확인) ─────── 30분
7. RunPod 업로드 준비 (압축 또는 rsync) ─────────────────── 1시간
```

### RunPod 환경 (Day 2-3)
```
Day 2 (RunPod):
8. RunPod Pod 생성 + 환경 설정 ──────────────────────────── 1시간
9. 로컬 데이터 업로드 (sampled_images.json + output/) ── 10-30분
10. step2_rag_context.py → 테스트 + 전체 실행 ──────────── 30분
11. step3a + step3b 10장 테스트 ─────────────────────────── 1시간
12. step3a + step3b 병렬 전체 실행 (야간) ────────────────── 시작

Day 3 (RunPod):
13. step3a/3b 완료 확인 ──────────────────────────────────── 오전
14. step4_quality_compare.py → 실행 → 선택 ───────────────── 1시간
15. step5_build_jsonl.py → 실행 + 검증 ───────────────────── 1시간
16. step6_qwen3_finetune.py → 실행 ───────────────────────── 2-4시간
17. 모델 평가 + 결과 다운로드 ────────────────────────────── 1시간

Day 4 (선택):
18. run_all.py (오케스트레이터) 개선 ─────────────────────── 필요 시
```

**총 예상 소요: 2-3일**
- 로컬 작업: 1-2일 (야간 실행 활용)
- RunPod 작업: 1-2일 (야간 실행 활용)
- RunPod 총 사용 시간: **~8-16시간** (대기 시간 포함)

---

## v1 → v2 변경 요약

| 항목 | v1 | v2 |
|------|-----|-----|
| 이미지 수 | 9,991장 | **2,000장** (대표 샘플) |
| 라벨링 모델 | GPT-4o-mini 1개 | **GPT-4o + Gemini 3 Pro** 2개 |
| 임베딩 모델 | OpenAI text-embedding-3-small | **Qwen3-Embedding-0.6B** (768차원) |
| 데이터 품질 보증 | 없음 | **8개 메트릭 자동 비교** |
| CV 추론 환경 | 로컬 | **로컬 GPU** (Phase 0-1) |
| 학습 환경 | 로컬 | **RunPod A100 80GB** (Phase 2-6) |
| Qwen3 학습 | 별도 계획 | **통합 (Phase 6)** |
| 학습-추론 일관성 | 없음 (불일치) | **완벽 일관성** (동일 임베딩) |
| 총 API 비용 | ~$25-30 | ~$60-100 |
| 총 RunPod 비용 | ~$8-25 | **~$3-10** (50-70% 절감) |
| 총 소요 시간 | ~22-50시간 | **~17-33시간** (병렬화 + 로컬 분산) |
| Phase 1 시간 | ~3-6시간 (A100) | **~6-12시간** (로컬 GPU, 야간 실행) |
| Phase 2 시간 | ~5분 | **~15초** (20배 단축) |
| 데이터 품질 | 중 (4o-mini) | **상 (4o + Gemini 3 Pro 비교 검증)** |
| 총 비용 | ~$33-55 | **~$63-110** (고품질 라벨링)
