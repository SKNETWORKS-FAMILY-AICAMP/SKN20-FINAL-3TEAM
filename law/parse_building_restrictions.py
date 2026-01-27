"""
건축불가 목록 파싱 스크립트

토지이음 HTML에서 별표(건축불가 건축물)를 파싱하여
깔끔한 JSON으로 변환

실행:
    python parse_building_restrictions.py

출력:
    zones/ 폴더의 각 파일에 건축불가_용도 업데이트
"""

import os
import re
import json
import time
from eum_land_collector import EumLandCollector


# 용도지역별 별표 번호 매핑
ZONE_BYULPYO = {
    "제1종전용주거지역": {"별표": "2", "유형": "가능"},   # 건축할 수 있는
    "제2종전용주거지역": {"별표": "3", "유형": "가능"},
    "제1종일반주거지역": {"별표": "4", "유형": "가능"},
    "제2종일반주거지역": {"별표": "5", "유형": "가능"},
    "제3종일반주거지역": {"별표": "6", "유형": "가능"},
    "준주거지역": {"별표": "7", "유형": "불가"},         # 건축할 수 없는
    "중심상업지역": {"별표": "8", "유형": "불가"},
    "일반상업지역": {"별표": "9", "유형": "불가"},
    "근린상업지역": {"별표": "10", "유형": "불가"},
    "유통상업지역": {"별표": "11", "유형": "불가"},
    "전용공업지역": {"별표": "12", "유형": "가능"},
    "일반공업지역": {"별표": "13", "유형": "가능"},
    "준공업지역": {"별표": "14", "유형": "불가"},
    "보전녹지지역": {"별표": "15", "유형": "가능"},
    "생산녹지지역": {"별표": "16", "유형": "가능"},
    "자연녹지지역": {"별표": "17", "유형": "가능"},
    "보전관리지역": {"별표": "18", "유형": "가능"},
    "생산관리지역": {"별표": "19", "유형": "가능"},
    "계획관리지역": {"별표": "20", "유형": "불가"},
    "농림지역": {"별표": "21", "유형": "가능"},
    "자연환경보전지역": {"별표": "22", "유형": "가능"},
}

# 용도지역 코드
ZONE_CODES = {
    "제1종전용주거지역": "UQA110",
    "제2종전용주거지역": "UQA120",
    "제1종일반주거지역": "UQA130",
    "제2종일반주거지역": "UQA140",
    "제3종일반주거지역": "UQA150",
    "준주거지역": "UQA160",
    "중심상업지역": "UQA210",
    "일반상업지역": "UQA220",
    "근린상업지역": "UQA230",
    "유통상업지역": "UQA240",
    "전용공업지역": "UQA310",
    "일반공업지역": "UQA320",
    "준공업지역": "UQA330",
    "보전녹지지역": "UQA410",
    "생산녹지지역": "UQA420",
    "자연녹지지역": "UQA430",
    "보전관리지역": "UQA510",
    "생산관리지역": "UQA520",
    "계획관리지역": "UQA530",
    "농림지역": "UQA600",
    "자연환경보전지역": "UQA700",
}


def clean_text(text):
    """HTML 태그 제거 및 텍스트 정리"""
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', ' ', text)
    # HTML 엔티티 변환
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&#8228;', '·')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    # 공백 정리
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_byulpyo(html, byulpyo_num, zone_name):
    """
    별표에서 건축물 목록 파싱

    Args:
        html: 전체 HTML
        byulpyo_num: 별표 번호 (예: "9")
        zone_name: 용도지역명

    Returns:
        {
            "절대_불가": [...],      # 무조건 건축 불가
            "조례_불가": [...],      # 조례에 따라 불가
            "절대_가능": [...],      # 무조건 건축 가능 (녹지 등)
            "조례_가능": [...]       # 조례에 따라 가능
        }
    """
    result = {
        "절대_불가": [],
        "조례_불가": [],
        "절대_가능": [],
        "조례_가능": [],
        "원문_요약": ""
    }

    # 별표 섹션 찾기
    pattern = rf'\[별표\s*{byulpyo_num}\](.*?)(?:\[별표\s*\d+\]|국토의 계획 및 이용에 관한 법률|$)'
    match = re.search(pattern, html, re.DOTALL)

    if not match:
        print(f"  [경고] 별표 {byulpyo_num} 못 찾음")
        return result

    content = match.group(1)
    content = clean_text(content)

    # 원문 요약 저장
    result["원문_요약"] = content[:500] + "..." if len(content) > 500 else content

    # "건축할 수 없는" vs "건축할 수 있는" 구분
    is_cannot_build = "건축할 수 없는" in content[:100]

    # 건축물 유형 추출
    # 패턴: 「건축법 시행령」 별표 1 제XX호의 YYYY
    building_types = re.findall(
        r'「건축법 시행령」\s*별표\s*1\s*제(\d+)호(?:의\d+)?(?:의|에 따른)?\s*([가-힣\s]+?)(?:\s*중|\s*\(|\.|\s*다만)',
        content
    )

    # 간단한 버전: 제XX호의 YYYY
    building_types2 = re.findall(
        r'제(\d+)호의\s*([가-힣]+(?:\s*및\s*[가-힣]+)?)',
        content
    )

    # 건축물 유형 매핑 (건축법 시행령 별표1 기준)
    BUILDING_TYPES = {
        "1": "단독주택",
        "2": "공동주택",
        "3": "제1종근린생활시설",
        "4": "제2종근린생활시설",
        "5": "문화및집회시설",
        "6": "종교시설",
        "7": "판매시설",
        "8": "운수시설",
        "9": "의료시설",
        "10": "교육연구시설",
        "11": "노유자시설",
        "12": "수련시설",
        "13": "운동시설",
        "14": "업무시설",
        "15": "숙박시설",
        "16": "위락시설",
        "17": "공장",
        "18": "창고시설",
        "19": "위험물저장및처리시설",
        "20": "자동차관련시설",
        "21": "동물및식물관련시설",
        "22": "자원순환관련시설",
        "23": "교정시설",
        "24": "국방군사시설",
        "25": "방송통신시설",
        "26": "묘지관련시설",
        "27": "관광휴게시설",
        "28": "장례시설",
        "29": "야영장시설",
        "30": "복합건축물"
    }

    # 발견된 건축물 유형 정리
    found_types = set()

    for num, name in building_types + building_types2:
        # 번호로 매핑된 이름 우선
        type_name = BUILDING_TYPES.get(num, name.strip())
        if type_name:
            found_types.add(type_name)

    # 직접 언급된 건축물 유형
    direct_mentions = [
        ("숙박시설", "숙박시설"),
        ("위락시설", "위락시설"),
        ("공장", "공장"),
        ("위험물", "위험물저장및처리시설"),
        ("폐차장", "폐차장"),
        ("동물", "동물및식물관련시설"),
        ("자원순환", "자원순환관련시설"),
        ("묘지", "묘지관련시설"),
        ("단독주택", "단독주택"),
        ("공동주택", "공동주택"),
        ("수련시설", "수련시설"),
        ("교정시설", "교정시설"),
        ("야영장", "야영장시설"),
        ("창고", "창고시설"),
        ("근린생활시설", "근린생활시설"),
        ("판매시설", "판매시설"),
        ("의료시설", "의료시설"),
        ("교육연구시설", "교육연구시설"),
        ("운동시설", "운동시설"),
        ("업무시설", "업무시설"),
    ]

    for keyword, type_name in direct_mentions:
        if keyword in content:
            found_types.add(type_name)

    # 분류: 절대 불가 vs 조례 불가
    # "1. 건축할 수 없는" = 절대
    # "2. 지역 여건 등을 고려하여 도시·군계획조례로" = 조례

    section1_match = re.search(r'1\.\s*건축할 수 없는 건축물(.*?)(?:2\.\s*지역|$)', content, re.DOTALL)
    section2_match = re.search(r'2\.\s*지역\s*여건.*?조례로.*?건축할 수 없는 건축물(.*?)(?:국토|$)', content, re.DOTALL)

    if is_cannot_build:
        # 불가 목록인 경우
        if section1_match:
            sec1 = section1_match.group(1)
            for keyword, type_name in direct_mentions:
                if keyword in sec1:
                    result["절대_불가"].append(type_name)

        if section2_match:
            sec2 = section2_match.group(1)
            for keyword, type_name in direct_mentions:
                if keyword in sec2 and type_name not in result["절대_불가"]:
                    result["조례_불가"].append(type_name)

        # section 구분 못하면 전체를 절대_불가로
        if not section1_match and not section2_match:
            result["절대_불가"] = list(found_types)
    else:
        # 가능 목록인 경우 (녹지지역 등)
        if section1_match or "1." in content[:200]:
            sec1_match = re.search(r'1\.\s*건축할 수 있는 건축물(.*?)(?:2\.\s*|$)', content, re.DOTALL)
            if sec1_match:
                sec1 = sec1_match.group(1)
                for keyword, type_name in direct_mentions:
                    if keyword in sec1:
                        result["절대_가능"].append(type_name)

        # 구분 못하면 전체를 절대_가능으로
        if not result["절대_가능"]:
            result["절대_가능"] = list(found_types)

    # 중복 제거
    result["절대_불가"] = list(set(result["절대_불가"]))
    result["조례_불가"] = list(set(result["조례_불가"]))
    result["절대_가능"] = list(set(result["절대_가능"]))
    result["조례_가능"] = list(set(result["조례_가능"]))

    return result


def fetch_and_parse_zone(collector, zone_name, ucode, sample_pnu):
    """용도지역별 건축제한 정보 가져오기"""

    sggcd = sample_pnu[:5]

    # 토지이음에서 HTML 가져오기
    res = collector.session.get(
        "https://www.eum.go.kr/web/ar/lw/lwLawDetContentsAjax.jsp",
        params={
            "AREA_CODE": sggcd,
            "ucode": ucode,
            "carGbn": "all"
        },
        headers=collector.headers
    )
    res.encoding = 'euc-kr'
    html = res.text

    # 별표 번호 확인
    byulpyo_info = ZONE_BYULPYO.get(zone_name, {"별표": "0", "유형": "불가"})
    byulpyo_num = byulpyo_info["별표"]

    # 별표 파싱
    restrictions = parse_byulpyo(html, byulpyo_num, zone_name)

    return restrictions, byulpyo_info["유형"]


def update_zone_files(collector, sample_pnu):
    """zones/ 폴더의 파일들 업데이트"""

    print("\n" + "="*50)
    print("건축제한 목록 파싱 및 업데이트")
    print("="*50)

    for zone_name, ucode in ZONE_CODES.items():
        print(f"\n[{zone_name}]")

        filepath = f"zones/{zone_name}.json"
        if not os.path.exists(filepath):
            print(f"  -> 파일 없음: {filepath}")
            continue

        # 기존 데이터 로드
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 토지이음에서 파싱
        restrictions, restrict_type = fetch_and_parse_zone(
            collector, zone_name, ucode, sample_pnu
        )

        # 데이터 업데이트
        data["건축제한_유형"] = restrict_type  # "가능" 또는 "불가"
        data["건축불가_상세"] = {
            "절대_불가": restrictions["절대_불가"],
            "조례_불가": restrictions["조례_불가"],
        }
        data["건축가능_상세"] = {
            "절대_가능": restrictions["절대_가능"],
            "조례_가능": restrictions["조례_가능"],
        }

        # 기존 건축불가_용도 필드 업데이트
        if restrict_type == "불가":
            data["건축불가_용도"] = restrictions["절대_불가"] + restrictions["조례_불가"]
        else:
            data["건축불가_용도"] = []  # 가능 목록 지역은 불가 목록이 별도로 없음

        # 별표 원문 요약
        data["별표_요약"] = restrictions["원문_요약"]

        # 저장
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"  별표 유형: {restrict_type}")
        print(f"  절대 불가: {restrictions['절대_불가']}")
        print(f"  조례 불가: {restrictions['조례_불가']}")
        print(f"  절대 가능: {restrictions['절대_가능']}")
        print(f"  -> 저장 완료")

        time.sleep(0.3)


def main():
    collector = EumLandCollector()
    sample_pnu = "1168010100108250012"

    update_zone_files(collector, sample_pnu)

    print("\n" + "="*50)
    print("완료!")
    print("="*50)


if __name__ == "__main__":
    main()
