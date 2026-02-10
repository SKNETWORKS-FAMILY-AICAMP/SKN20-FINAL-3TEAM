import re

class RealEstateQueryParser:
    """
    자연어 질문을 분석하여 부동산 도면 검색 SQL 쿼리에 필요한 파라미터를 추출하는 파서
    """
    def __init__(self):
        # SQL 쿼리의 변수 기본값 설정 ('NULL'은 SQL에서 해당 필터를 건너뛰기 위함)
        self.defaults = {
            'bay_cnt': 'NULL',      # 예: '2' 또는 '2,3'
            'struc_type': 'NULL',   # 예: '판상형' 또는 '판상형,타워형'
            'comp_grade': 'NULL',   # 예: '우수', '미흡', '불합격'
            'k_op': 'NULL',         # 주방 연산자
            'k_val': 'NULL',        # 주방 기준값
            'lr_op': 'NULL',        # 거실 연산자
            'lr_val': 'NULL',       # 거실 기준값
            'wl_op': 'NULL',        # 무창공간 연산자
            'wl_val': 'NULL',       # 무창공간 기준값
            'keyword': 'NULL',      # 공간 키워드
            'vent_grade': 'NULL',   # 환기 등급 (우수, 미흡, 불량)
            'light_grade': 'NULL',  # 채광 등급 (적합, 보통, 부족, 부적합)
            'storage_grade': 'NULL',# 수납 등급 (적합, 보통, 부족, 부적합)
            'val_op': 'NULL',       # 발코니 연산자
            'val_val': 'NULL',      # 발코니 기준값
            'to_op': 'NULL',        # 화장실 연산자
            'to_val': 'NULL'        # 화장실 기준값
        }
        
        # 자연어 표현을 데이터베이스 연산자로 매핑
        self.op_map = {
            '이상': '이상', '넘는': '초과', '초과': '초과', '큰': '초과',
            '이하': '이하', '안되는': '미만', '미만': '미만', '작은': '미만',
            '동일': '동일', '같은': '동일', '딱': '동일'
        }
        
        # 수치/등급 추출 시 다른 키워드 영역을 침범하지 않도록 경계 키워드 설정
        self.boundary_keywords = ['주방', '거실', '무창', '안방', '침실', '드레스룸', '팬트리', '현관', '욕실', '화장실', '발코니']

    def parse(self, user_query: str) -> dict:
        """
        사용자 질문(user_query)을 받아 SQL 파라미터 딕셔너리를 반환합니다.
        """
        params = self.defaults.copy()
        
        # 1. 베이(Bay) 수 추출
        bay_set = set()
        
        # (1) 범위 표현 (예: "2~4베이")
        range_match = re.search(r'(\d+)\s*[~-]\s*(\d+)\s*(?:베이|bay)', user_query, re.IGNORECASE)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if start < end:
                bay_set.update(str(i) for i in range(start, end + 1))

        # (2) 나열 표현 (예: "2, 3, 4 베이")
        list_match = re.search(r'((?:\d+\s*,\s*)+\d+)\s*(?:베이|bay)', user_query, re.IGNORECASE)
        if list_match:
            bay_set.update(re.findall(r'\d+', list_match.group(1)))

        # (3) 단일/개별 표현 (예: "2베이", "3bay")
        single_matches = re.findall(r'(\d+)\s*(?:베이|bay)', user_query, re.IGNORECASE)
        bay_set.update(single_matches)

        if bay_set:
            params['bay_cnt'] = ','.join(sorted(bay_set, key=int))

        # 2. 구조 유형 추출 (유의어 포함)
        struc_types = []
        
        # 판상형 유의어 리스트
        plate_keywords = [
            '판상형', '맞통풍 구조','맞통풍구조', '편복도', '판상', '일자형', '일자형 구조', '일자형구조'
            '성냥갑 구조', '성냥갑구조', '성냥갑 아파트', '성냥갑아파트', '전면 베이', '전면베이'
        ]
        # 타워형 유의어 리스트
        tower_keywords = [
            '타워형', '탑상형', '중앙코어', '타워', 'Y자형', 'y자형', 'X자형', 'x자형' "'+'자형",'십자형','+자형',
            '이면개방','이면 개방', '이면개방', '조망형','삼면 개방','삼면','이면'
        ]

        # 리스트 중 하나라도 포함되어 있는지 확인 (any 사용)
        if any(k in user_query for k in plate_keywords):
            struc_types.append('판상형')
            
        if any(k in user_query for k in tower_keywords):
            struc_types.append('타워형')
        
        if struc_types:
            params['struc_type'] = ','.join(struc_types)
        
        if struc_types:
            params['struc_type'] = ','.join(struc_types)

        # 3. 종합 등급 추출
        if '우수' in user_query: params['comp_grade'] = '우수'
        elif '미흡' in user_query: params['comp_grade'] = '미흡'
        elif '불합격' in user_query: params['comp_grade'] = '불합격'

        # 4. 면적/비율 추출 (주방, 거실, 무창공간, 발코니, 화장실)
        # scale_type: 'ratio' (0~1), 'percent' (0~100)
        params.update(self._extract_metric(user_query, '주방', 'k', 'ratio'))
        params.update(self._extract_metric(user_query, '거실', 'lr', 'ratio'))
        params.update(self._extract_metric(user_query, '무창', 'wl', 'percent'))
        params.update(self._extract_metric(user_query, '발코니', 'val', 'percent'))
        params.update(self._extract_metric(user_query, '(?:화장실|욕실)', 'to', 'ratio'))

        # 5. 상세 등급 추출 (환기, 채광, 수납)
        # 예: "환기 우수한 곳", "채광 나쁨", "수납 보통"
        self.grade_map = {
        '좋은': '우수', '잘 되는': '우수', '넉넉한': '우수', '훌륭한': '우수', 
        '잘되는': '우수', '괜찮은': '우수', '풍부한': '우수', '많은': '우수',
        '나쁜': '불량', '안좋은': '미흡', '부족한': '부족'
        }

        natural_keywords = list(self.grade_map.keys())
        grade_keywords = ['우수', '적합', '보통', '부적합', '불합격', '부족', '미흡', '불량', '양호']
        all_keywords = grade_keywords + natural_keywords

        # 환기, 채광, 수납 키워드 뒤에 등급이 오는지 확인
        # 1) 단어를 추출한다 (환기 양호, 채광 좋은 등)
        raw_vent = self._extract_grade(user_query, '환기', all_keywords)
        raw_light = self._extract_grade(user_query, '채광', all_keywords)
        raw_storage = self._extract_grade(user_query, '수납', all_keywords)

        # 2) 추출된 단어를 DB 등급으로 번역해서 저장한다 (없으면 NULL)
        params['vent_grade'] = self.grade_map.get(raw_vent, raw_vent) if raw_vent else 'NULL'
        params['light_grade'] = self.grade_map.get(raw_light, raw_light) if raw_light else 'NULL'
        params['storage_grade'] = self.grade_map.get(raw_storage, raw_storage) if raw_storage else 'NULL'

        # 6. 키워드 검색 (예: "안방", "드레스룸" 등 특정 단어가 포함되었는지)
        # 검색 대상 키워드 목록
        target_keywords = ['안방', '침실', '드레스룸', '팬트리', '현관', '욕실', '화장실', '알파룸', '발코니', '거실', '주방', '부부욕실', '가족욕실', '팬트리룸']
        found_keywords = [k for k in target_keywords if k in user_query]
        
        # 사용자가 명시적으로 "주방 검색해줘"라고 했으나 수치 조건이 없는 경우 키워드 검색에 포함
        if '주방' in user_query and params['k_val'] == 'NULL': found_keywords.append('주방')
        if '거실' in user_query and params['lr_val'] == 'NULL': found_keywords.append('거실')
        
        if found_keywords:
            params['keyword'] = ','.join(found_keywords)

        return params

    def _extract_metric(self, text: str, keyword: str, prefix: str, scale_type: str = 'ratio') -> dict:
        """
        특정 키워드(주방, 거실 등)와 관련된 수치와 연산자를 추출합니다.
        scale_type: 'ratio' (0~1 범위), 'percent' (0~100 범위)
        """
        result = {}
        op_pattern = '|'.join(self.op_map.keys())
        
        # Case A: "주방 15 이상", "주방 비율 15.5% 넘는" (키워드 -> 숫자 -> 연산자)
        # 경계 키워드 체크를 포함한 안전한 검색
        # Group 1: Keyword, Group 2: Number, Group 3: Percent(optional), Group 4: Operator
        pattern_a = f"({keyword}).*?(\d+(?:\.\d+)?)\s*(%)?.*?({op_pattern})"
        for match in re.finditer(pattern_a, text):
            full_match = match.group(0)
            # 키워드 이후 부분에 다른 경계 키워드가 포함되어 있는지 확인 (오탐 방지)
            matched_kw = match.group(1)
            content_after = full_match[len(matched_kw):]
            if not any(bk in content_after for bk in self.boundary_keywords if bk != matched_kw):
                val = float(match.group(2))
                has_percent = bool(match.group(3))
                op_txt = match.group(4)
                
                val = self._normalize_value(val, has_percent, scale_type)
                
                result[f'{prefix}_val'] = val
                result[f'{prefix}_op'] = self.op_map.get(op_txt, '이상')
                return result

        # Case B: "15% 이상인 주방" (숫자 -> 연산자 -> 키워드)
        # Group 1: Number, Group 2: Percent(optional), Group 3: Operator, Group 4: Keyword
        pattern_b = f"(\d+(?:\.\d+)?)\s*(%)?.*?({op_pattern}).*?({keyword})"
        for match in re.finditer(pattern_b, text):
            full_match = match.group(0)
            matched_kw = match.group(4)
            # 키워드 이전 부분에 다른 경계 키워드가 포함되어 있는지 확인
            content_before = full_match[:-len(matched_kw)]
            if not any(bk in content_before for bk in self.boundary_keywords if bk != matched_kw):
                val = float(match.group(1))
                has_percent = bool(match.group(2))
                op_txt = match.group(3)
                
                val = self._normalize_value(val, has_percent, scale_type)

                result[f'{prefix}_val'] = val
                result[f'{prefix}_op'] = self.op_map.get(op_txt, '이상')
                return result
            
        return result

    def _normalize_value(self, val: float, has_percent: bool, scale_type: str) -> float:
        """
        수치를 DB 저장 포맷에 맞게 변환합니다.
        """
        if has_percent:
            # 퍼센트 기호가 있으면 무조건 퍼센트 단위
            if scale_type == 'ratio':
                return val / 100.0
            else: # percent
                return val
        else:
            # 퍼센트 기호가 없으면 값의 크기로 추론
            if scale_type == 'ratio':
                # 1.0 이상이면 퍼센트로 간주하여 비율로 변환 (예: 20 -> 0.2, 1 -> 0.01)
                if val >= 1.0:
                    return val / 100.0
                return val
            else: # percent
                # 1.0 미만이면 비율로 간주하여 퍼센트로 변환 (예: 0.2 -> 20)
                if val < 1.0:
                    return val * 100.0
                return val

    def _extract_grade(self, text: str, category: str, grades: list) -> str:
        # 등급 추출 시에도 다른 카테고리가 끼어들지 않도록 확인
        categories = ['환기', '채광', '수납']
        other_categories = [c for c in categories if c != category]
        pattern = f"({category}).*?({'|'.join(grades)})"
        for match in re.finditer(pattern, text):
            content = match.group(0)[len(category):]
            if not any(oc in content for oc in other_categories):
                return match.group(2)
        return None

# --- 실행 테스트 코드 ---
if __name__ == "__main__":
    parser = RealEstateQueryParser()

    # 테스트할 질문 목록
    test_questions = [
        "2베이 판상형 중에서 주방 비율 15.0 이상인 곳 찾아줘",
        "거실 30 미만이고 무창공간 25랑 동일한 불합격 도면 보여줘",
        "2~3베이인 안방, 드레스룸 있는 구조 검색해",
        "2, 3, 4베이 중에서 선택해줘",
        "타워형이고 주방 20 넘는거 있어?",
        "아무 조건 없이 침실이랑 현관 있는거만 보여줘",
        "발코니 10% 이상이고 화장실 5% 미만인 곳",
        "채광 적합하고 수납 부족한 도면"
    ]

    print(f"{'='*20} 파싱 테스트 시작 {'='*20}")
    
    for i, q in enumerate(test_questions, 1):
        print(f"\n[질문 {i}]: {q}")
        params = parser.parse(q)
        
        # 결과 출력 (가독성을 위해 NULL이 아닌 값만 출력하거나 전체 출력)
        print(">> 추출된 파라미터:")
        for key, value in params.items():
            if value != 'NULL':
                print(f"   - {key}: {value}")
        
        # 전체 딕셔너리 확인용
        # print(f"   (Raw): {params}")

    print(f"\n{'='*20} 테스트 종료 {'='*20}")
