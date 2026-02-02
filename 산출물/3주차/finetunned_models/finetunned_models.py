from openai import OpenAI

#####################################################################
# CONFIG
YOUR_API_KEY = " "
# 설명 : OPEN API KEY를 입력해주세요.

RESPONSE_MODEL = "ft:gpt-4o-mini-2024-07-18:carookim::D4oNZf61"
# 설명 : 어조 및 답변 형식 파인튜닝 모델

WORD_MODEL = "ft:gpt-4o-mini-2024-07-18:carookim::D4oP9jgg"
# 설명 : 전문용어 파인튜닝 모델

COMBINED_MODEL = "ft:gpt-4o-mini-2024-07-18:carookim::D4oP9jgg"
# 설명 : 병합 (1차 : 전문용어 - 2차 : 어조 및 답변 형식) 파인튜닝 모델

#####################################################################

client = OpenAI(api_key=YOUR_API_KEY)

# --- 모델별 프롬프트 정의 ---
PROMPTS = {
    "RESPONSE_MODEL": {
        "system": (
            "당신은 도면 정보를 안내하는 친절한 부동산 상담원입니다. "
            "모든 수치는 반드시 제공된 요약 데이터와 일치해야 하며, "
            "**[수치]** 형식을 꼭 유지해 주세요. "
            "데이터에 없는 정보는 지어내지 말고, 정보가 없음을 친절하게 안내하도록 합니다."
        ),
        "user_template": (
            "[대상 파일 데이터]\n"
            "ID: {file_id}\n"
            "방 개수: {rooms}\n"
            "구조: {structure}\n"
            "등급: {grade}\n"
            "{question}"
        ),
    },
    "WORD_MODEL": {
        "system": (
            "당신은 건축 용어 사전입니다. 반드시 제공된 학습 데이터의 정의만을 사용하여 답변하고, "
            "모르는 내용은 지어내는 것을 금지합니다."
        ),
        "user_template": "{question}",
    }
}

# --- COMBINED_MODEL용 매핑 ---
COMBINED_MAPPING = {
    "COMBINED_MODEL_WORD": "WORD_MODEL",
    "COMBINED_MODEL_RESPONSE": "RESPONSE_MODEL",
}

# --- 메시지 생성 함수 ---
def generate_messages(model_key, **kwargs):
    # COMBINED_MODEL이면 매핑 적용
    if model_key.startswith("COMBINED_MODEL"):
        base_model = COMBINED_MAPPING.get(model_key, None)
        if not base_model:
            raise ValueError(f"Unknown combined model key: {model_key}")
    else:
        base_model = model_key

    system_msg = PROMPTS[base_model]["system"]
    user_msg = PROMPTS[base_model]["user_template"].format(**kwargs)
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

# --- 모델 호출 및 결과 출력 ---
def ask_model(model_key, correct_answer=None, **kwargs):
    messages = generate_messages(model_key, **kwargs)

    if model_key.startswith("COMBINED_MODEL"):
        # COMBINED_MODEL_RESPONSE → COMBINED_MODEL 변수 값 사용
        actual_model_id = COMBINED_MODEL
    else:
        # RESPONSE_MODEL / WORD_MODEL 변수 값 가져오기
        actual_model_id = globals()[model_key]

    response = client.chat.completions.create(
        model=actual_model_id,
        messages=messages,
        temperature=0.7,
    )

    reply = response.choices[0].message.content
    print("="*50)
    print("=== 모델 답변 ===")
    print(reply)
    if correct_answer:
        print("\n=== 학습 데이터 정답 ===")
        print(correct_answer)
    print("="*50)

# --- 예시 사용 ---
# RESPONSE_MODEL 예시
ask_model(
    "RESPONSE_MODEL",
    file_id="APT_FP_OBJ_009075352.PNG",
    rooms="3개",
    structure="타워형",
    grade="우수",
    question="타워형 구조 중에서 수납 공간 평가는 어떤가요?",
    correct_answer="이 집은 **[타워형]** 구조이며, 수납 공간은 현재 **[미흡]** 수준으로 평가되었습니다."
)

# WORD_MODEL 예시
ask_model(
    "WORD_MODEL",
    question="샌드위치 패널이란 무엇인가요?",
    correct_answer="단열재를 금속판 사이에 끼워 만든 판재로, 외벽 및 지붕 마감재로 사용됩니다."
)

# COMBINED_MODEL 예시
ask_model(
    "COMBINED_MODEL_RESPONSE",
    file_id="APT_FP_OBJ_009075352.PNG",
    rooms="3개",
    structure="타워형",
    grade="우수",
    question="타워형 구조 중에서 수납 공간 평가는 어떤가요?",
    correct_answer="이 집은 **[타워형]** 구조이며, 수납 공간은 현재 **[미흡]** 수준으로 평가되었습니다."
)

ask_model(
    "COMBINED_MODEL_WORD",
    question="라멘구조란 무엇인가요?",
    correct_answer="기둥과 보가 강하게 결합되어 벽체 없이도 수평하중을 지지할 수 있는 구조 시스템입니다."
)