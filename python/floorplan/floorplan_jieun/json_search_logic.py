import json

def analyze_floorplan_data(data):
    results = []

    for item in data:
        doc_text = item.get("document", "")
        plan_id = item.get("id")

        # ======================
        # 1. 수납공간
        # ======================
        storage_spaces = []
        if "드레스룸" in doc_text:
            storage_spaces.append("드레스룸")
        if "알파룸" in doc_text:
            storage_spaces.append("알파룸")
        if any(kw in doc_text for kw in ["팬트리", "펜트리"]):
            storage_spaces.append("팬트리룸")
        if "발코니" in doc_text:
            storage_spaces.append("발코니")

        # ======================
        # 2. 환기창
        # ======================
        vent_spaces = []

        if "주방" in doc_text:
            segment = doc_text.split("주방", 1)[1].split(".", 1)[0]
            if any(kw in segment for kw in ["환기창이 있어", "창이 있어"]):
                vent_spaces.append("주방")

        for kw in ["부부욕실", "욕실", "화장실"]:
            if kw in doc_text:
                segment = doc_text.split(kw, 1)[1].split(".", 1)[0]
                if any(w in segment for w in ["환기창이 있어", "창이 있어"]):
                    vent_spaces.append(kw)
                    break

        # ======================
        # 3. 채광창
        # ======================
        light_spaces = []

        if "거실" in doc_text:
            segment = doc_text.split("거실", 1)[1].split(".", 1)[0]
            if any(kw in segment for kw in ["채광", "창문이 있어", "창이 있어"]):
                light_spaces.append("거실")

        if "침실" in doc_text:
            segment = doc_text.split("침실", 1)[1].split(".", 1)[0]
            if any(kw in segment for kw in ["채광", "창문이 있어", "외기창이 있어"]):
                light_spaces.append("침실")

        results.append({
            "id": plan_id,
            "환기창이_있는_공간": vent_spaces,
            "수납공간": storage_spaces,
            "채광창이_있는_공간": light_spaces
        })

    return results

# 예시 실행 (사용자가 업로드한 파일 내용의 일부를 변수로 가정)
import json

file_path = r"D:\2026\coding_2026\playdata\skn20_lastproject\SLLM_User_Input_Processing_Model\floorplan.json"

with open(file_path, "r", encoding="utf-8") as f:
    json_content = json.load(f)
analysis = analyze_floorplan_data(json_content)
print(json.dumps(analysis, indent=2, ensure_ascii=False))
