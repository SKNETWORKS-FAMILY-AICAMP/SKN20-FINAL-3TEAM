# data_processor.py
# 토지 이용 규제 법령/조례 데이터 자동 처리 스크립트
# 사용법: python data_processor.py

import pandas as pd
import os
from difflib import SequenceMatcher

def load_file(file_path):
    """파일 불러오기 (CSV 또는 Excel 지원)"""
    if file_path.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_path)
    elif file_path.endswith('.csv'):
        return pd.read_csv(file_path)
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {file_path}")

def standardize_name(name):
    """용도지역지구명 표준화 함수"""
    name = str(name).strip()
    name = name.replace('지구', '지역')
    # 추가 규칙 가능
    return name

def combine_ordnances(file_list):
    """조례 파일 리스트를 하나로 합침"""
    dfs = []
    for file in file_list:
        if os.path.exists(file):
            df = load_file(file)
            print(f"불러옴: {file} ({len(df)}행), 컬럼: {list(df.columns)}")
            dfs.append(df)
        else:
            print(f"파일 없음: {file}")
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        print(f"조례 합침 완료: 총 {len(combined)}행")
        
        # 용도지역지구명 컬럼 확인
        if '용도지역지구명' in combined.columns:
            # 향토유적보호구역 통합
            combined['용도지역지구명'] = combined['용도지역지구명'].apply(
                lambda x: '향토유적보호구역' if str(x).endswith('향토유적보호구역') else x
            )
            print("향토유적보호구역 통합 완료")
        else:
            print("경고: '용도지역지구명' 컬럼이 없습니다. 컬럼명을 확인하세요.")
        
        return combined
    return pd.DataFrame()

def analyze_and_merge(ordinance_file_list, law_file):
    """메인 처리 함수"""
    print("=== 데이터 처리 시작 ===")
    
    # 1. 조례 데이터 합치기
    ord_data = combine_ordnances(ordinance_file_list)
    if ord_data.empty:
        return "조례 데이터 없음"

    # 2. 법령 데이터 로드
    if not os.path.exists(law_file):
        return f"법령 파일 없음: {law_file}"
    law_data = load_file(law_file)
    print(f"법령 데이터 불러옴: {len(law_data)}행")

    # 3. 표준화
    ord_data['용도지역지구명_표준'] = ord_data['용도지역지구명'].apply(standardize_name)
    law_data['용도지역지구명_표준'] = law_data['용도지역지구명'].apply(standardize_name)
    print("표준화 완료")

    # 4. 고유 값 분석
    ord_unique = set(ord_data['용도지역지구명_표준'].unique())
    law_unique = set(law_data['용도지역지구명_표준'].unique())
    common = ord_unique & law_unique
    ord_only = ord_unique - law_unique
    law_only = law_unique - ord_unique

    print(f"고유 값 분석: 공통 {len(common)}, 조례만 {len(ord_only)}, 법령만 {len(law_only)}")

    # 5. 전체 합치기
    merged = pd.concat([law_data, ord_data], ignore_index=True, sort=False)
    print(f"데이터 합침 완료: 총 {len(merged)}행")

    # 6. 결과 저장
    merged.to_csv('final_merged_all_columns.csv', index=False)
    with open('ordinance_only.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(sorted(list(ord_only))))
    with open('law_only.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(sorted(list(law_only))))
    with open('common_values.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(sorted(list(common))))

    print("결과 파일 저장 완료")
    print("=== 처리 완료 ===")

    return {
        '조례 행 수': len(ord_data),
        '법령 행 수': len(law_data),
        '합친 행 수': len(merged),
        '공통 값': len(common),
        '조례만': len(ord_only),
        '법령만': len(law_only),
        '저장 파일': ['final_merged_all_columns.csv', 'ordinance_only.txt', 'law_only.txt', 'common_values.txt']
    }

# 사용 예시 (이 부분을 수정해서 사용)
if __name__ == "__main__":
    # 폴더 경로를 입력하면 자동으로 모든 CSV/Excel 파일 합침
    folder_path = 'python/csv/'  # 조례 파일들이 있는 폴더
    law_file = 'python/csv/법령_전처리2(특수문자 제거).csv'  # 법령 파일
    
    # 폴더 안의 모든 CSV/Excel 파일 리스트 생성
    ordinance_files = []
    if os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            if file.endswith(('.csv', '.xlsx', '.xls')) and file != '법령_전처리2(특수문자 제거).csv':
                ordinance_files.append(os.path.join(folder_path, file))
    
    print(f"발견된 조례 파일: {ordinance_files}")
    
    if ordinance_files:
        result = analyze_and_merge(ordinance_files, law_file)
        print("결과:", result)
    else:
        print("조례 파일이 없습니다. csv 폴더에 파일을 추가하세요.")