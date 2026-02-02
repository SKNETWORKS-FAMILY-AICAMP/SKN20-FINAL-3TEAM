# Changelog

C_Vision 프로젝트의 모든 변경사항을 기록합니다.

## [V1.5.0] - 2026-02-02

### Changed - topology_result.png 시각화 개선
- **파일**: `cv_inference/visualizer.py`
- **변경 내용**:
  - SPA segmentation 영역 제거 (배경 도면 + 노드/엣지만 표시)
  - 배경 도면 어둡게 처리 (50%)
  - 노드 텍스트 스타일 변경: 흰색 → 검정색 (굵은 글씨, 흰색 외곽선)
  - Edge Legend 추가 (좌측 상단)
    - Door: 초록 실선
    - Window: 파랑 점선
    - Open: 노랑 점선
  - Legend 크기 확대 (280x180px, 큰 폰트)

### Changed - 프로젝트 경로 동적 설정
- **파일**: `cv_inference/config.py`
- **변경 전**: `BASE_PATH = Path(r"c:\Users\ansck\Desktop\C_Vision")` (하드코딩)
- **변경 후**: `BASE_PATH = Path(__file__).parent.parent` (동적 경로)
- **효과**: 프로젝트 폴더 이동 시에도 자동으로 경로 설정

---

## [V1.4.0] - 2026-02-02

### Changed - structure_type 판단 로직 개선 (맞통풍 기준)
- **파일**: `cv_inference/aggregator.py`
- **변경 전**: 발코니 centroid 분포로 판단 (부정확)
- **변경 후**: 맞통풍(Cross-ventilation) 가능 여부로 판단
  - **판상형**: 거실↔주방 창문이 180° 반대 (맞통풍 가능)
  - **타워형**: 이면개방 OR 주방 창문 없음 OR 같은 방향 (맞통풍 불가)
  - **혼합형**: 90° 직각 (Edge Case)
- **새 함수**:
  - `_is_opposite_direction()`: 두 방향이 180° 반대인지 확인
  - `_is_perpendicular_direction()`: 두 방향이 90° 직각인지 확인
  - `_get_space_window_direction()`: 공간의 주요 창문 방향 반환
  - `_get_all_window_directions()`: 공간의 모든 창문 방향 반환 (이면개방 판별용)
  - `_has_perpendicular_windows()`: 이면개방 여부 확인
- **효과**: 건축적 정의에 부합하는 정확한 구조 유형 판단

---

## [V1.3.0] - 2026-02-02

### Changed - 프로젝트 구조 개편 (RAG 시스템 통합)
- **디렉토리 이름 변경**:
  - `cv_output/` → `output/`: 추론 결과 출력 디렉토리
  - `test_image/` → `test_images/`: 테스트 이미지 디렉토리
- **실행 스크립트 이름 변경**:
  - `run_inference.py` → `run_cv_inference.py`: CV 추론 전용 스크립트로 명확화

### Changed - 설정 파일 업데이트
- **파일**: `cv_inference/config.py`
- `OUTPUT_PATH = self.BASE_PATH / "cv_output"` → `OUTPUT_PATH = self.BASE_PATH / "output"`

### Changed - 문서 업데이트
- **파일**: `CLAUDE.md`, `run_cv_inference.py`
- 모든 예제 코드 및 경로 참조 업데이트

### Added - statistics에 발코니 비율 추가
- **파일**: `cv_inference/aggregator.py`
- **필드**: `balcony_ratio` (float)
- **계산**: `(총 발코니 면적 / 전체 내부 면적) * 100`
- **효과**: RAG 시스템에서 발코니 비율 기반 검색 가능

### Added - statistics에 창 없는 공간 비율 추가
- **파일**: `cv_inference/aggregator.py`
- **필드**: `windowless_ratio` (float)
- **계산**: `(창문 없는 공간 수 / 전체 내부 공간 수) * 100`
- **제외 조건**: OCR 라벨이 "기타"인 공간은 계산에서 제외
- **효과**: RAG 시스템에서 환기 품질 관련 검색 정확도 향상

---

## [V1.2.1] - 2026-01-31

### Changed - area_ratio 계산 로직 개선
- **파일**: `cv_inference/aggregator.py`
- **기존**: `area_ratio = space_area / total_image_area` (전체 이미지 면적 기준)
- **변경**: `area_ratio = space_area / total_inside_area` (세대 내부 공간 면적 기준)
- **효과**: 내부 공간들의 area_ratio 합이 1.0 (100%)이 됨
- **외부 공간**: `area_ratio = null` (계산 제외)

### Added - statistics에 total_inside_area 추가
- `total_inside_area`: 세대 내부 공간 면적 합계

---

## [V1.2.0] - 2026-01-31

### Fixed - 드레스룸 공간 타입 오분류 수정
- **파일**: `cv_inference/aggregator.py`
- **문제**: "드레스룸"이 "개인공간"으로 분류됨 (침실 동의어 "룸" 부분 매칭)
- **수정**: `_get_space_type()`에서 정확한 매칭 우선 적용
```python
# 1차: 정확한 매칭 시도
if normalized_label in normalized_synonyms:
    standard_name = group
    break
# 2차: 정확한 매칭 실패 시 부분 매칭 시도
if not standard_name:
    if any(normalized_label in s or s in normalized_label ...):
```

### Fixed - 침실-침실 엣지 생성 버그 수정
- **파일**: `cv_inference/aggregator.py`
- **문제**: 3개+ 공간 교차 시 침실-침실 간 잘못된 엣지 생성
- **수정**: `_is_bedroom()` 헬퍼 함수 추가 및 필터링 로직 적용
```python
def _is_bedroom(self, node: Dict) -> bool:
    # category_name 또는 label의 침실 동의어 확인

# _analyze_connections()에서 3개+ 공간 교차 시
if self._is_bedroom(node_a) and self._is_bedroom(node_b):
    continue  # 침실-침실 연결 제외
```

### Added - 동의어 사전 확장
- **파일**: `cv_inference/config.py`
- **SPACE_SYNONYMS 추가**:
  - `엘리베이터홀`: 엘베홀, EV홀, E/V홀, EL홀, 승강기홀 등
  - `엘리베이터`: 엘베, EV, E/V, EL, 승강기 등
  - `계단실`: 계단, stair, stairs, stairwell
  - `실외기실`: 실외기룸, 에어컨실, AC실
  - `세탁실`: 세탁공간, 런드리, laundry, 빨래방

---

## [V1.1.9] - 2026-01-31

### Changed - 출력 폴더 구조 변경
- **파일**: `cv_inference/aggregator.py`, `cv_inference/visualizer.py`
- **기존**: `cv_output/source_result/`, `cv_output/topology_graph/` 등
- **변경**: `cv_output/{이미지명}/source_result.json`, `cv_output/{이미지명}/topology_graph.json` 등
- **효과**: 이미지별로 결과물이 한 폴더에 정리됨

---

## [V1.1.8] - 2026-01-31

### Changed - 폴더 구조 개편 및 동적 경로 적용
- **변경사항**:
  - `yolov5/`, `model/` 폴더를 `cv_inference/` 하위로 이동
  - `inference/` 폴더명을 `cv_inference/`로 변경
  - `output/` 폴더명을 `cv_output/`으로 변경

### Changed - 동적 경로 설정
- **파일**: `cv_inference/config.py`
- `__file__` 기반 동적 경로로 변경하여 폴더 위치 유연성 확보
```python
INFERENCE_PATH = Path(__file__).parent
self.MODEL_PATH = INFERENCE_PATH / "model"
self.YOLO_PATH = INFERENCE_PATH / "yolov5"
self.OUTPUT_PATH = self.BASE_PATH / "cv_output"
```

### Fixed - import 경로 수정
- **파일**: `run_inference.py`
- `from inference import ...` → `from cv_inference import ...`

---

## [V1.1.7] - 2026-01-31

### Changed - 상수 중앙화 리팩토링
- **파일**: `inference/config.py`, `inference/aggregator.py`, `inference/visualizer.py`
- **목적**: 설정 관리의 용이성 및 유지보수성 향상

### Moved - aggregator.py → config.py
- `SPACE_SYNONYMS`: 공간명 동의어 사전
- `SPACE_CLASSIFICATION`: 공간 타입 분류
- `OUTSIDE_SPACES`: 세대 외부 공간 목록

### Moved - visualizer.py → config.py
- `COLORS` → `CATEGORY_COLORS`: 카테고리별 시각화 색상 (BGR)
- `EDGE_COLORS`: 엣지 연결 타입별 색상

### Changed - import 구조 변경
- `aggregator.py`: `from .config import SPACE_SYNONYMS, SPACE_CLASSIFICATION, OUTSIDE_SPACES`
- `visualizer.py`: `from .config import CATEGORY_COLORS, EDGE_COLORS`

---

## [V1.1.6] - 2026-01-31

### Added - 공간 분류 체계 추가
- **파일**: `inference/aggregator.py`
- **상수 추가**:
  - `SPACE_CLASSIFICATION`: 공간 타입 분류 (기타공간/특화공간/습식공간/공통공간/개인공간)
  - `OUTSIDE_SPACES`: 세대 외부 공간 목록 (분석 제외 대상)

### Added - 공간 타입 관련 함수
- `_get_space_type()`: 공간 라벨 → 공간 타입 분류 반환
- `_is_outside_space()`: 세대 외부 공간 여부 확인

### Changed - 노드 필드 추가
- `space_type`: 공간 타입 (기타공간/특화공간/습식공간/공통공간/개인공간/외부공간/미분류)
- `is_outside`: 세대 외부 공간 여부 (boolean)

### Changed - statistics 필드 추가
- `space_type_count`: 공간 타입별 카운트
- `inside_space_count`: 외부 공간 제외한 내부 공간 수

---

## [V1.1.5] - 2026-01-31

### Changed - Bay 수 계산 로직 개선
- **파일**: `inference/aggregator.py`
- **기존**: `bay_count = balcony_count` (단순 발코니 수)
- **변경**: 거실 창문 방향 기준으로 같은 방향 침실 수 + 거실 수

### Added - 창문 방향 계산 함수
- **함수**: `_get_window_direction()`
- **기능**: 창문이 공간에서 어느 방향(외부)을 바라보는지 계산
- **방향 판단 기준**:
  - 가로 창문 (w > h): 공간 중심 대비 위치로 남/북 판단
  - 세로 창문 (h > w): 공간 중심 대비 위치로 동/서 판단

### Added - Bay 수 계산 함수
- **함수**: `_calculate_bay_count()`
- **계산 로직**:
  1. 거실 1개일 경우: 창문 중 가장 긴 너비의 창문 방향을 "남쪽"으로 정의
  2. Bay 수 = 거실 창문과 같은 방향을 바라보는 침실 수 + 거실 수

---

## [V1.1.4] - 2026-01-30

### Fixed - 문/창문 polygon intersection 개선 필요 (미구현)
- 문/창문 polygon이 공간 polygon과 1픽셀 차이로 교차하지 않는 문제 발견
- str_6 문 (y=1184~1303)과 주방 (y=1304~) 사이 1픽셀 gap 문제
- 해결 방안: 문/창문 intersection 검사 시 buffer 적용 필요

---

## [V1.1.3] - 2026-01-30

### Fixed - 2개 공간 교차 시 인접성 검사 제거
- **파일**: `inference/aggregator.py`
- **문제**: 문이 정확히 2개 공간과 교차할 때, 공간들이 인접하지 않아 edge가 생성되지 않음
- **원인**: 문이 두 공간 사이에 위치하면 gap이 발생하여 `touches()` 및 `buffer().intersects()` 실패
- **수정**: `_analyze_connections()`에서 정확히 2개 공간과 교차하는 경우 인접성 검사 생략
```python
elif len(connected_spaces) == 2:
    space_a, space_b = connected_spaces
    pair = tuple(sorted([space_a, space_b]))
    if pair not in edge_pairs:
        edge_pairs.add(pair)
        edges.append({...})  # 인접성 검사 없이 바로 edge 생성
```

---

## [V1.1.2] - 2026-01-30

### Fixed - 벽체 분할 실패 시 OCR 중간점 fallback 추가
- **파일**: `inference/aggregator.py`
- **문제**: 벽체가 발견되었지만 `_split_space_by_wall()`이 1개만 반환하여 분할 실패
- **원인**: 벽체 polygon과 공간 polygon의 정밀도 문제로 split 실패
- **수정**: `_process_space_splitting()`에서 벽체 분할 결과가 2개 미만일 때 OCR 중간점 fallback 적용
```python
if splitting_wall:
    split_spaces = self._split_space_by_wall(space, splitting_wall)
    if len(split_spaces) < 2:  # 벽체 분할 실패 시
        split_spaces = self._split_space_by_ocr_midpoint(space, ocr_positions)
```

---

## [V1.1.1] - 2026-01-30

### Fixed - 인접성 검사 조건 단순화
- **파일**: `inference/aggregator.py`
- **문제**: 3개 이상 공간 교차 시 fallback 로직이 너무 엄격함
- **원인**: `intersection_a.intersects(intersection_b.buffer(15))` 조건이 복잡
- **수정**: 기본 인접성 검사로 단순화
```python
if poly_a.touches(poly_b) or poly_a.buffer(5).intersects(poly_b.buffer(5)):
```

---

## [V1.1.0] - 2026-01-30

### Added - 3개 이상 공간 교차 시 문/창문 분할 로직
- **파일**: `inference/aggregator.py`
- **함수**: `_split_structure_by_spaces()`
- **기능**: 문/창문이 3개 이상 공간과 교차할 때, 벽체 기준으로 분할하여 각 조각별로 edge 생성
```python
def _split_structure_by_spaces(self, structure: Dict, connected_nodes: List[Dict],
                               walls: List[Dict]) -> List[Tuple[Polygon, List[str]]]:
```

### Added - fallback 로직
- 분할 실패 시 인접한 공간 쌍에 대해 edge 생성하는 fallback 추가

---

## [V1.0.4] - 2026-01-30

### Added - OCR 중간점 기반 공간 분할 함수
- **파일**: `inference/aggregator.py`
- **함수**: `_split_space_by_ocr_midpoint()`
- **기능**: 두 OCR 위치의 중간점을 기준으로 공간 분할 (벽체 없을 때 fallback)
```python
def _split_space_by_ocr_midpoint(self, space: Dict, ocr_positions: List[Dict]) -> List[Dict]:
    # dx > dy → 수직선 분할
    # dx <= dy → 수평선 분할
```

---

## [V1.0.3] - 2026-01-30

### Added - 분할선 확장 함수
- **파일**: `inference/aggregator.py`
- **함수**: `_extend_line_through_polygon()`
- **기능**: 분할선을 polygon 경계를 넘어 확장하여 완전한 분할 보장
```python
def _extend_line_through_polygon(self, line: LineString, polygon: Polygon) -> LineString:
    # polygon 대각선 길이만큼 양방향 확장
```

---

## [V1.0.2] - 2026-01-30

### Added - 분할선 기반 공간 분할 함수
- **파일**: `inference/aggregator.py`
- **함수**: `_split_space_by_line()`
- **기능**: LineString으로 공간을 분할하여 새로운 공간 리스트 반환
```python
def _split_space_by_line(self, space: Dict, split_line: LineString, space_id_prefix: str) -> List[Dict]:
    # shapely split() 사용하여 polygon 분할
    # segmentation, bbox, area 업데이트
```

---

## [V1.0.1] - 2026-01-30

### Fixed - 모델 경로 수정
- **파일**: `inference/config.py`
- **수정**: `OBJ_BEST_Model.pt` → `OBJ_YOLO_model.pt`
- **원인**: 실제 모델 파일명과 불일치

### Added - 에러 처리 개선
- 모델 로딩 시 파일 존재 여부 확인 강화

---

## [V1.0.0] - 2026-01-30

### Added - 초기 추론 파이프라인 구현
- **디렉토리**: `inference/`

#### 핵심 파일
- `pipeline.py`: 추론 파이프라인 메인 클래스
- `aggregator.py`: 결과 통합 및 JSON 생성
- `visualizer.py`: 결과 시각화
- `config.py`: 설정 관리

#### 모델 래퍼
- `models/base_model.py`: 기본 모델 추상 클래스
- `models/obj_model.py`: 객체 탐지 모델 (YOLO)
- `models/ocr_model.py`: OCR 모델 (YOLO + CRNN)
- `models/spa_model.py`: 공간 분할 모델
- `models/str_model.py`: 구조물 탐지 모델

#### 실행 스크립트
- `run_inference.py`: CLI 실행 스크립트

### Added - 결과 출력 형식
- `source_result.json`: 모델별 원본 결과 (COCO 형식)
- `low_result.json`: 단순 통합 결과
- `topology_graph.json`: 노드 기반 토폴로지 그래프
  - nodes: 공간 노드 (공간 정보, 포함 객체/구조물)
  - edges: 연결 관계 (door/window/open)
  - statistics: 통계 정보

### Added - 주요 기능
- Polygon 기반 공간 분석 (Shapely 라이브러리)
- OCR 텍스트로 공간 분할 감지
- 공간-구조물 연결 관계 분석
- 동의어 사전 기반 공간명 정규화
