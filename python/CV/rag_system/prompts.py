"""프롬프트 템플릿"""

SYSTEM_PROMPT = """
당신은 건축 평면도 분석 전문가입니다.

역할:
- 평면도의 공간 구조를 정확히 파악
- 사내 평가 기준에 따라 설계 적절성 분석
- 채광, 환기, 가족 융화, 수납의 4대 핵심 가치 평가

금지 사항:
- 제공된 정보 외 추측 금지
- 불확실한 경우 "확실하지 않습니다" 표현
"""

ANALYSIS_PROMPT_TEMPLATE = """
다음 평면도 정보를 분석하고 JSON 형식으로 출력하세요.

# 평면도 데이터
{topology_json}

# 참고: 사내 평가 기준 (RAG 검색 결과)
{rag_context}

# 작업
1. 각 공간의 특징과 기능 분석
2. 공간 간 연결 관계 파악
3. 설계 평가 (채광, 환기, 가족융화, 수납)
4. 개선 제안 작성
5. 사내 평가 기준 적합성 평가 (compliance 필드)

# 사내 평가 기준 적합성 평가 가이드

## 평가 기준 요약
1. **채광**:
   - 4Bay 이상: 최우수 / 3Bay: 우수 / 2Bay: 보통
   - 무창 공간 비율 30% 이하 권장
   - 안방(주침실) 외기창 필수 (없으면 불합격)

2. **환기**:
   - 맞통풍 가능 구조 권장 (판상형)
   - 주방 환기창 필수
   - 욕실 환기창 권장 (최소 1개 이상)

3. **가족 융화**:
   - LDK(거실+식당+주방) 비율 30-40% 적정
   - 공용공간이 중앙에 배치되어야 함

4. **수납**:
   - 수납공간(드레스룸, 팬트리 등) 비율 10% 이상 우수
   - 5-10% 보통, 5% 미만 부족

## 종합 등급 기준
- **최우수**: 4개 항목 모두 적합
- **우수**: 3개 항목 적합, 1개 경미한 부적합
- **보통**: 2개 항목 적합
- **미흡**: 1개 항목만 적합
- **불합격**: 안방 외기창 미확보 등 필수 조건 미충족

## compliance 필드 작성 요령
- compliant_items: 적합한 항목을 구체적으로 나열
- non_compliant_items: 부적합한 각 항목에 대해 category, item, reason, recommendation 작성
- summary: 전체 적합성 평가를 2-3문장으로 요약

출력 형식은 FloorPlanAnalysis 스키마를 따르세요.
"""

def build_analysis_prompt(topology_data: dict, rag_context: str) -> str:
    """분석 프롬프트 생성"""
    import json
    topology_json = json.dumps(topology_data, ensure_ascii=False, indent=2)

    return ANALYSIS_PROMPT_TEMPLATE.format(
        topology_json=topology_json,
        rag_context=rag_context
    )
