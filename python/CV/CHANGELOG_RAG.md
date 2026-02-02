# Changelog - RAG System

RAG (Retrieval-Augmented Generation) 시스템 관련 변경사항을 기록합니다.

## [V1.3.0] - 2026-02-02

### Added - 사내 평가 기준 적합성 평가
- **파일**: `rag_system/schemas.py`, `rag_system/prompts.py`, `rag_system/rag_pipeline.py`
- **새 스키마**:
  - `NonCompliantItem`: 부적합 항목 (category, item, reason, recommendation)
  - `ComplianceEvaluation`: 적합성 평가 (overall_grade, compliant_items, non_compliant_items, summary)
- **FloorPlanAnalysis 필드 추가**: `compliance`
- **평가 기준**:
  - 채광: Bay 수, 무창 공간 비율, 안방 외기창
  - 환기: 맞통풍 구조, 주방/욕실 환기창
  - 가족 융화: LDK 비율 30-40%
  - 수납: 수납공간 비율 10% 이상
- **종합 등급**: 최우수/우수/보통/미흡/불합격
- **메타데이터 추가**: `compliance_grade`

---

## [V1.2.0] - 2026-02-02

### Added - 통합 실행 스크립트
- **파일**: `run_inference.py`
- **기능**: CV 추론 + RAG 분석을 한번에 실행
- **옵션**:
  - `--cv-only`: CV 추론만 실행
  - `--rag-only`: RAG 분석만 실행
  - `--batch`: 배치 처리
  - `--index-eval`: 사내 평가 문서 색인

### Added - 메타데이터 필드 추가
- **파일**: `rag_system/rag_pipeline.py`
- **추가 필드**:
  - `kitchen_ratio`: 주방 면적 비율 (%)
  - `bathroom_ratio`: 화장실 면적 비율 (%, 욕실/화장실 합산)
- **효과**: 주방/화장실 비율 기반 검색 가능

---

## [V1.1.0] - 2026-02-02

### Changed - 프로젝트 구조 정리
- **사내 평가 문서 이동**:
  - `사내_평가_문서.json` → `rag_data/사내_평가_문서.json`
  - **파일**: `run_rag_inference.py`, `rag_system/rag_pipeline.py`
  - 기본 경로 업데이트로 일관성 향상

### Changed - 의존성 통합
- **requirements 파일 병합**:
  - `requirements_rag.txt` → `requirements.txt`에 통합
  - CV 의존성과 RAG 의존성을 하나의 파일로 관리

### Changed - CV 파이프라인 통합 개선
- **통계 계산 자동화**:
  - `balcony_ratio`, `windowless_ratio`를 CV 파이프라인에서 계산
  - **파일**: `cv_inference/aggregator.py`
  - **효과**: LLM이 정확한 값을 topology.json에서 직접 읽어옴
  - **이전 문제**: LLM이 직접 계산 시 오류 발생 (단일 발코니만 계산, 0.0 잘못 출력 등)

---

## [V1.0.1] - 2026-02-02

### Fixed - 윈도우 콘솔 인코딩 문제 해결
- **파일**: `run_rag_inference.py`, `rag_system/rag_pipeline.py`
- **문제**: 이모지(📚, 🔍, ✅) 출력 시 `cp949` 코덱 오류
- **수정**: 모든 이모지를 일반 텍스트로 변경
```python
# Before: print("📚 Indexing evaluation document...")
# After:  print("Indexing evaluation document...")
```

### Fixed - ChromaDB 메타데이터 리스트 지원 문제
- **파일**: `rag_system/rag_pipeline.py`
- **문제**: ChromaDB가 메타데이터에 리스트를 지원하지 않음
- **수정**: keywords 리스트를 쉼표로 구분된 문자열로 변환
```python
keywords = chunk.get('keywords', [])
keywords_str = ', '.join(keywords) if isinstance(keywords, list) else str(keywords)
```

### Fixed - OpenAI Structured Outputs API 호환성
- **파일**: `rag_system/schemas.py`
- **문제**: OpenAI API의 엄격한 스키마 검증 오류
- **수정 사항**:
  1. `dict` → `Dict[str, str]`: 명시적 타입 지정
  2. `default_factory=list` → `default=[]`: 기본값 표현 변경
  3. 필드를 `Optional`로 변경하여 유연성 확보
```python
# Before: design_evaluation: dict = Field(default_factory=dict)
# After:  design_evaluation: Optional[Dict[str, str]] = Field(default=None)
```

---

## [V1.0.0] - 2026-02-02

### Added - RAG 시스템 초기 구현

#### 시스템 아키텍처
```
[사내_평가_문서.json] → [Embedding] → [ChromaDB]
                                         ↓
[topology.json] → [RAG 검색 + LLM] → [analysis_result.json] → [ChromaDB]
```

#### 핵심 모듈 생성
**디렉토리**: `rag_system/`

1. **config.py**: RAG 시스템 설정
   - OpenAI API 설정 (임베딩, LLM)
   - ChromaDB 경로 설정
   - RAG 파라미터 (TOP_K, 온도 등)

2. **embeddings.py**: 임베딩 관리자
   - OpenAI `text-embedding-3-small` (512-dim)
   - 배치 임베딩 지원
   - 비용 효율적 ($0.02/1M tokens)

3. **vector_store.py**: ChromaDB 벡터 저장소
   - 2개 컬렉션: `evaluation_docs`, `topology_analyses`
   - 메타데이터 필터링 지원
   - 유사도 검색 (cosine similarity)

4. **llm_client.py**: LLM API 추상화
   - OpenAI `gpt-4o-mini` 기본 모델
   - Structured Outputs API 지원 (Pydantic 스키마)
   - 향후 로컬 모델 교체 가능 (Qwen 3 등)

5. **schemas.py**: Pydantic 데이터 스키마
   - `FloorPlanAnalysis`: 전체 평면도 분석 결과
   - `SpaceAnalysis`: 개별 공간 분석 결과
   - `to_natural_language()`: 벡터 임베딩용 자연어 변환

6. **prompts.py**: 프롬프트 템플릿
   - `SYSTEM_PROMPT`: 건축 평면도 분석 전문가 역할 정의
   - `ANALYSIS_PROMPT_TEMPLATE`: topology.json 분석 지시사항

7. **rag_pipeline.py**: RAG 파이프라인 메인 로직
   - `index_evaluation_document()`: 사내 평가 문서 색인
   - `analyze_topology()`: topology.json 분석 (RAG + LLM)
   - `_index_analysis()`: 분석 결과 벡터 DB 색인

#### 실행 스크립트
**파일**: `run_rag_inference.py`

- CLI 인터페이스 제공
- 평가 문서 색인: `--index-eval`
- 평면도 분석: `--topology <path>`
- JSON 출력: `--output <path>`

#### 검색 요구사항 (query.md)
**파일**: `information_etc/query.md`

다음 9가지 질문 유형을 처리할 수 있도록 메타데이터 설계:
1. Bay 수 + 구조 유형 (`bay_count`, `structure_type`)
2. 거실 면적 비율 (`living_room_ratio`)
3. 기타공간/특화공간 유무 (`has_etc_space`, `has_special_space`)
4. 방/화장실 수 (`room_count`, `bathroom_count`)
5. 발코니 비율 (`balcony_ratio`)
6. 창 없는 공간 비율 (`windowless_ratio`)
7-9. 환기 품질 (`ventilation_quality`)

### Added - 메타데이터 vs 문서 역할 분리
- **메타데이터**: 숫자/비율/카테고리 → 정확한 필터링용
- **문서 (document)**: 의미적 내용 (요약, 평가, 코멘트) → 유사도 검색용
- **효과**: 하이브리드 검색 (필터링 + 벡터 유사도) 가능

### Added - 자연어 변환 로직
**함수**: `FloorPlanAnalysis.to_natural_language()`

숫자/비율은 제외하고 의미적 내용만 추출:
- 전체 요약 (summary)
- 설계 평가 (lighting, ventilation, family_harmony, storage)
- 공간별 평가 코멘트 (evaluation_comment)

### Added - 기술 스택
- **Vector DB**: ChromaDB (>=0.5.0, pydantic 2.x 지원)
- **Embedding**: OpenAI text-embedding-3-small (512-dim)
- **LLM**: OpenAI gpt-4o-mini (가성비)
- **Validation**: Pydantic 2.x (구조화된 출력)
- **Config**: python-dotenv (.env 파일 지원)

### Added - 환경 설정
**파일**: `.env`

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.1
```

### Added - 유틸리티 스크립트
**파일**: `check_chromadb.py`

- ChromaDB 저장 내용 확인
- JSON 파일로 내보내기
- 디버깅 및 검증 용도

---

## 향후 계획

### Phase 2 (1-2개월 후)
- PostgreSQL + pgvector (확장성 필요 시)
- 프롬프트 최적화
- 캐싱 전략 추가

### Phase 3 (3-6개월 후)
- Qwen 3 로컬 모델 교체 (비용 절감)
- GraphRAG (공간 관계 그래프 활용)
- FastAPI 서버화 (웹 API 제공)

---

## 비용 분석

**기준**: 100개 평면도 분석/월

| 항목 | 수량 | 단가 | 월비용 |
|------|------|------|--------|
| Embedding (text-embedding-3-small) | ~13K tokens | $0.02/1M | ~$0.0003 |
| LLM 입력 (gpt-4o-mini) | 200K tokens | $0.15/1M | ~$0.03 |
| LLM 출력 (gpt-4o-mini) | 100K tokens | $0.60/1M | ~$0.06 |
| Vector DB (ChromaDB 로컬) | - | $0 | $0 |
| **합계** | - | - | **~$0.10/월** |

✅ OpenAI 무료 티어로 충분 (초기 단계)
