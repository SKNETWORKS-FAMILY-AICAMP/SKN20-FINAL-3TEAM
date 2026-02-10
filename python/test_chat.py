"""챗봇 서비스 테스트 스크립트"""

import sys
from services.chatbot_service_v2 import chatbot_service

print("=" * 60)
print("챗봇 서비스 테스트")
print("=" * 60)

# 컴포넌트 로드
try:
    chatbot_service.load_components()
    print("✓ 컴포넌트 로드 완료\n")
except Exception as e:
    print(f"✗ 컴포넌트 로드 실패: {e}")
    sys.exit(1)

# DB 상태 확인
print("-" * 60)
print("[DB 상태 확인]")
try:
    with chatbot_service.db_conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM land_char")
        land_count = cursor.fetchone()[0]
        print(f"  land_char 테이블: {land_count:,}건")

        cursor.execute("SELECT COUNT(*) FROM law")
        law_count = cursor.fetchone()[0]
        print(f"  law 테이블: {law_count:,}건")

        # 제1종일반주거지역 법규 확인
        cursor.execute("SELECT COUNT(*) FROM law WHERE zone_district_name LIKE '%제1종일반주거지역%'")
        zone_count = cursor.fetchone()[0]
        print(f"  제1종일반주거지역 법규: {zone_count:,}건")

        # 휴게음식점 법규 확인
        cursor.execute("SELECT COUNT(*) FROM law WHERE land_use_activity LIKE '%휴게음식점%'")
        activity_count = cursor.fetchone()[0]
        print(f"  휴게음식점 관련 법규: {activity_count:,}건")
except Exception as e:
    print(f"  DB 확인 오류: {e}")
print("-" * 60 + "\n")

# 대화형 테스트
while True:
    print("-" * 60)
    question = input("질문 입력 (종료: q): ").strip()

    if question.lower() in ['q', 'quit', 'exit']:
        print("테스트 종료")
        break

    if not question:
        continue

    print("\n[분석 중...]\n")

    # 전체 처리 (ask 내부에서 LLM 추출 1회만 수행)
    result = chatbot_service.ask("test@test.com", question)

    # ask()가 반환한 extraction으로 디스플레이 (2중 호출 방지)
    extraction = result.get("_extraction", {})
    address_info = extraction.get("address_info", {})
    zone_names = extraction.get("zone_names", [])
    activities = extraction.get("activities", [])
    query_fields = extraction.get("query_fields", [])
    law_reference = extraction.get("law_reference", "")
    intent = extraction.get("intent", {})

    depth_labels = {0: "주소없음", 1: "시/도만", 2: "구/군까지", 3: "동까지", 4: "지번까지"}
    depth = address_info.get("address_depth", 0)
    print(f"📍 주소 추출: {address_info}")
    print(f"📏 주소 상세도: Depth {depth} ({depth_labels.get(depth, '?')})")
    print(f"🏷️  용도지역: {zone_names}")
    print(f"🏗️  토지이용: {activities}")
    is_comparison = extraction.get("is_comparison", False)
    if is_comparison:
        print(f"🔄 비교 모드: {zone_names}")
    if query_fields:
        print(f"🔍 질문 핵심: {query_fields}")
    if law_reference:
        print(f"📖 법조문: {law_reference}")
    print(f"📋 케이스: {intent.get('case', '?')}-{intent.get('sub_case', '?')} ({intent.get('description', '')})")

    # 컨텍스트 디버깅 (있으면 표시)
    if result.get('_debug_context'):
        ctx = result['_debug_context']
        print(f"[DEBUG CONTEXT] 전체 길이: {len(ctx)}자")
        print(f"[DEBUG CONTEXT] '조례' 포함: {'조례' in ctx}")
        print(f"[DEBUG CONTEXT] '건축법 vs 조례' 포함: {'건축법 vs 조례' in ctx}")
        # 마지막 500자 보기
        print(f"[DEBUG CONTEXT 끝부분]")
        print(ctx[-500:])
        print("-" * 60)

    print("=" * 60)
    print(f"📝 제목: {result['summaryTitle']}")
    print("=" * 60)
    print(result['answer'])
    print("=" * 60 + "\n")
