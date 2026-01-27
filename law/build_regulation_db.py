"""
토지 규제 데이터베이스 구축 스크립트

1. zones/  - 용도지역별 규제 기준 (21개)
2. laws/   - 법령 조문 전문

실행:
    python build_regulation_db.py

출력:
    zones/일반상업지역.json
    zones/제1종전용주거지역.json
    ...
    laws/건축법.json
    laws/국토계획법시행령.json
    ...
"""

import os
import json
import time
from collections import defaultdict
from eum_land_collector import EumLandCollector


# 용도지역 코드 매핑 (21개)
ZONE_CODES = {
    # 주거지역 (6개)
    "제1종전용주거지역": "UQA110",
    "제2종전용주거지역": "UQA120",
    "제1종일반주거지역": "UQA130",
    "제2종일반주거지역": "UQA140",
    "제3종일반주거지역": "UQA150",
    "준주거지역": "UQA160",

    # 상업지역 (4개)
    "중심상업지역": "UQA210",
    "일반상업지역": "UQA220",
    "근린상업지역": "UQA230",
    "유통상업지역": "UQA240",

    # 공업지역 (3개)
    "전용공업지역": "UQA310",
    "일반공업지역": "UQA320",
    "준공업지역": "UQA330",

    # 녹지지역 (3개)
    "보전녹지지역": "UQA410",
    "생산녹지지역": "UQA420",
    "자연녹지지역": "UQA430",

    # 관리지역 (3개)
    "보전관리지역": "UQA510",
    "생산관리지역": "UQA520",
    "계획관리지역": "UQA530",

    # 기타 (2개)
    "농림지역": "UQA600",
    "자연환경보전지역": "UQA700",
}

# 건폐율/용적률 기준 (국토계획법 시행령 기준)
ZONE_STANDARDS = {
    "제1종전용주거지역": {"건폐율": 50, "용적률": 100},
    "제2종전용주거지역": {"건폐율": 50, "용적률": 150},
    "제1종일반주거지역": {"건폐율": 60, "용적률": 200},
    "제2종일반주거지역": {"건폐율": 60, "용적률": 250},
    "제3종일반주거지역": {"건폐율": 50, "용적률": 300},
    "준주거지역": {"건폐율": 70, "용적률": 500},
    "중심상업지역": {"건폐율": 90, "용적률": 1500},
    "일반상업지역": {"건폐율": 80, "용적률": 1300},
    "근린상업지역": {"건폐율": 70, "용적률": 900},
    "유통상업지역": {"건폐율": 80, "용적률": 1100},
    "전용공업지역": {"건폐율": 70, "용적률": 300},
    "일반공업지역": {"건폐율": 70, "용적률": 350},
    "준공업지역": {"건폐율": 70, "용적률": 400},
    "보전녹지지역": {"건폐율": 20, "용적률": 80},
    "생산녹지지역": {"건폐율": 20, "용적률": 100},
    "자연녹지지역": {"건폐율": 20, "용적률": 100},
    "보전관리지역": {"건폐율": 20, "용적률": 80},
    "생산관리지역": {"건폐율": 20, "용적률": 80},
    "계획관리지역": {"건폐율": 40, "용적률": 100},
    "농림지역": {"건폐율": 20, "용적률": 80},
    "자연환경보전지역": {"건폐율": 20, "용적률": 80},
}


def create_directories():
    """zones/, laws/ 폴더 생성"""
    os.makedirs("zones", exist_ok=True)
    os.makedirs("laws", exist_ok=True)
    print("[폴더] zones/, laws/ 생성 완료")


def build_zones_db(collector, sample_pnu: str):
    """
    용도지역별 규제 데이터 수집

    Args:
        collector: EumLandCollector 인스턴스
        sample_pnu: 기준 PNU (시군구 코드 추출용)
    """
    print("\n" + "="*50)
    print("용도지역별 규제 데이터 수집 시작")
    print("="*50)

    all_laws = set()  # 발견된 모든 법령 (중복 제거용)

    for zone_name, ucode in ZONE_CODES.items():
        print(f"\n[{zone_name}] 수집 중... (ucode: {ucode})")

        try:
            # 토지이음에서 용도지역 규제 정보 가져오기
            raw_data = collector.get_zone_law_details(
                sample_pnu,
                ucode=ucode,
                include_full_text=False  # 조문 전문은 나중에 별도 수집
            )

            # 기준값 (법정 기준)
            standards = ZONE_STANDARDS.get(zone_name, {"건폐율": 0, "용적률": 0})

            # 정리된 데이터 구조
            clean_data = {
                "용도지역": zone_name,
                "용도지역코드": ucode,

                # 규제 기준값 (숫자)
                "기준값": {
                    "건폐율_max": standards["건폐율"],
                    "용적률_max": standards["용적률"],
                    "건폐율_토지이음": raw_data.get("건폐율_기준", ""),
                    "용적률_토지이음": raw_data.get("용적률_기준", ""),
                },

                # 건축 불가 용도
                "건축불가_용도": raw_data.get("건축불가건축물", []),

                # 관련 법령 (참조만, 조문 전문 X)
                "관련법령": [],

                # 법령 카테고리별
                "법령_카테고리별": raw_data.get("법령_카테고리별", {}),
            }

            # 관련 법령 목록 정리 (조문 전문 제외)
            for law in raw_data.get("관련법령_전체", []):
                law_ref = {
                    "법령명": law.get("법령명", ""),
                    "조항": law.get("조항", ""),
                }
                clean_data["관련법령"].append(law_ref)

                # 전체 법령 목록에 추가
                if law_ref["법령명"] and law_ref["조항"]:
                    all_laws.add((law_ref["법령명"], law_ref["조항"]))

            # 저장
            filepath = f"zones/{zone_name}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(clean_data, f, ensure_ascii=False, indent=2)

            print(f"  -> 저장 완료: {filepath}")
            print(f"     건폐율: {standards['건폐율']}%, 용적률: {standards['용적률']}%")
            print(f"     관련법령: {len(clean_data['관련법령'])}개")

            # 서버 부하 방지
            time.sleep(0.5)

        except Exception as e:
            print(f"  -> 오류 발생: {e}")
            continue

    print(f"\n[완료] 총 {len(all_laws)}개 고유 법령 조항 발견")
    return all_laws


def build_laws_db(collector, all_laws: set):
    """
    법령 조문 전문 수집

    Args:
        collector: EumLandCollector 인스턴스
        all_laws: {(법령명, 조항), ...} 세트
    """
    print("\n" + "="*50)
    print("법령 조문 수집 시작")
    print("="*50)

    # 법령별로 그룹화
    by_law_name = defaultdict(list)

    for 법령명, 조항 in all_laws:
        by_law_name[법령명].append(조항)

    print(f"총 {len(by_law_name)}개 법령, {len(all_laws)}개 조항")

    # 각 법령별로 조문 수집
    for 법령명, 조항들 in by_law_name.items():
        print(f"\n[{법령명}] {len(조항들)}개 조항 수집 중...")

        법령_데이터 = {
            "법령명": 법령명,
            "조항들": []
        }

        for 조항 in 조항들:
            print(f"  - {조항} 수집 중...", end=" ")

            try:
                조문_전문 = collector.get_law_article_text(법령명, 조항)

                조항_데이터 = {
                    "조항": 조항,
                    "조문_전문": 조문_전문,
                    "요약": None,  # 나중에 LLM으로 요약 추가 가능
                }
                법령_데이터["조항들"].append(조항_데이터)

                if 조문_전문:
                    print(f"성공 ({len(조문_전문)}자)")
                else:
                    print("조문 없음")

                # 서버 부하 방지
                time.sleep(0.3)

            except Exception as e:
                print(f"오류: {e}")
                continue

        # 파일명에서 공백 제거
        filename = 법령명.replace(" ", "").replace("·", "_")
        filepath = f"laws/{filename}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(법령_데이터, f, ensure_ascii=False, indent=2)

        print(f"  -> 저장 완료: {filepath}")


def build_summary_index(zones_dir="zones", laws_dir="laws"):
    """
    전체 인덱스 파일 생성 (조회용)
    """
    print("\n" + "="*50)
    print("인덱스 파일 생성")
    print("="*50)

    # 용도지역 인덱스
    zones_index = {}
    for filename in os.listdir(zones_dir):
        if filename.endswith(".json"):
            with open(f"{zones_dir}/{filename}", "r", encoding="utf-8") as f:
                data = json.load(f)
                zone_name = data.get("용도지역", filename.replace(".json", ""))
                zones_index[zone_name] = {
                    "파일": f"{zones_dir}/{filename}",
                    "용도지역코드": data.get("용도지역코드", ""),
                    "건폐율_max": data.get("기준값", {}).get("건폐율_max", 0),
                    "용적률_max": data.get("기준값", {}).get("용적률_max", 0),
                }

    # 법령 인덱스
    laws_index = {}
    for filename in os.listdir(laws_dir):
        if filename.endswith(".json"):
            with open(f"{laws_dir}/{filename}", "r", encoding="utf-8") as f:
                data = json.load(f)
                law_name = data.get("법령명", filename.replace(".json", ""))
                laws_index[law_name] = {
                    "파일": f"{laws_dir}/{filename}",
                    "조항_수": len(data.get("조항들", [])),
                    "조항_목록": [item.get("조항", "") for item in data.get("조항들", [])],
                }

    # 통합 인덱스 저장
    index = {
        "용도지역": zones_index,
        "법령": laws_index,
        "총_용도지역_수": len(zones_index),
        "총_법령_수": len(laws_index),
    }

    with open("regulation_index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: regulation_index.json")
    print(f"  - 용도지역: {len(zones_index)}개")
    print(f"  - 법령: {len(laws_index)}개")


def main():
    print("="*50)
    print("토지 규제 데이터베이스 구축")
    print("="*50)

    # 1. 폴더 생성
    create_directories()

    # 2. Collector 초기화
    collector = EumLandCollector()

    # 3. 기준 PNU (서울 강남구 역삼동)
    # - 실제 필지 데이터가 아니라 시군구 코드만 필요
    sample_pnu = "1168010100108250012"

    # 4. 용도지역 데이터 수집
    all_laws = build_zones_db(collector, sample_pnu)

    # 5. 법령 조문 수집
    if all_laws:
        build_laws_db(collector, all_laws)

    # 6. 인덱스 생성
    build_summary_index()

    print("\n" + "="*50)
    print("데이터베이스 구축 완료!")
    print("="*50)
    print("\n생성된 파일:")
    print("  zones/          - 용도지역별 규제 기준")
    print("  laws/           - 법령 조문 전문")
    print("  regulation_index.json - 전체 인덱스")


if __name__ == "__main__":
    main()
