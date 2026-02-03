
---

# OpenAI Fine-Tuned Models

이 문서는 OpenAI에서 파인튜닝된 모델(`RESPONSE_MODEL`, `WORD_MODEL`, `COMBINED_MODEL`)을 불러와 사용하는 방법과 예시를 정리한 가이드입니다.

---

## 1. 환경 설정

### 필수 라이브러리 설치

터미널(또는 CMD)에서 requirements.txt 파일이 있는 위치로 이동한 뒤 아래 명령어를 입력하세요.

```bash
pip install -r requirements.txt

```

### 기본 Python 구성

```python
from openai import OpenAI

# 1. API 키 및 모델 ID 설정
YOUR_API_KEY = " "  # OpenAI API Key를 입력하세요

RESPONSE_MODEL = "ft:gpt-4o-mini-2024-07-18:carookim::D4oNZf61"  # 어조 및 답변 형식 파인튜닝 모델
WORD_MODEL     = "ft:gpt-4o-mini-2024-07-18:carookim::D4oP9jgg"  # 전문용어 파인튜닝 모델
COMBINED_MODEL = "ft:gpt-4o-mini-2024-07-18:carookim::D4oP9jgg"  # 병합 모델 (1차: 전문용어, 2차: 어조 및 답변 형식)

client = OpenAI(api_key=YOUR_API_KEY)

```

---

## 2. 모델별 프롬프트 정의

### 🏢 RESPONSE_MODEL (도면 안내형)

* **역할:** 도면 정보 안내 친절 상담원
* **특징:** 데이터에 없는 정보는 지어내지 않으며, 수치는 `[수치]` 형식으로 출력합니다.
* **System Prompt:** `당신은 도면 정보를 안내하는 친절한 부동산 상담원입니다. ...`
* **User Template:** `"[대상 파일 데이터]\nID: {file_id}\n방 개수: {rooms}\n구조: {structure}\n등급: {grade}\n{question}"`

### 📖 WORD_MODEL (용어 사전형)

* **역할:** 건축 용어 사전
* **특징:** 학습 데이터에 정의된 내용만 사용하며, 모르는 내용은 답변하지 않습니다.
* **System Prompt:** `당신은 건축 용어 사전입니다. ...`
* **User Template:** `{question}`

### 🔗 COMBINED_MODEL (통합형)

* **특징:** `RESPONSE_MODEL`과 `WORD_MODEL`의 기능을 하나로 통합한 모델입니다. 호출 시 키에 따라 프롬프트를 선택적으로 사용합니다.
* `COMBINED_MODEL_RESPONSE`: 도면 안내용 프롬프트 사용
* `COMBINED_MODEL_WORD`: 용어 사전용 프롬프트 사용



---

## 3. 핵심 함수 구현

### 메시지 생성 함수

```python
def generate_messages(model_key, **kwargs):
    # Combined 모델 여부에 따른 매핑 처리
    if model_key.startswith("COMBINED_MODEL"):
        base_model = COMBINED_MAPPING.get(model_key)
    else:
        base_model = model_key

    system_msg = PROMPTS[base_model]["system"]
    user_msg = PROMPTS[base_model]["user_template"].format(**kwargs)
    
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

```

### 모델 호출 및 결과 출력 함수

```python
def ask_model(model_key, correct_answer=None, **kwargs):
    messages = generate_messages(model_key, **kwargs)

    # 실제 호출할 모델 ID 결정
    if model_key.startswith("COMBINED_MODEL"):
        actual_model_id = COMBINED_MODEL
    else:
        actual_model_id = globals()[model_key]

    response = client.chat.completions.create(
        model=actual_model_id,
        messages=messages,
        temperature=0.7,
    )

    reply = response.choices[0].message.content
    
    print("=" * 50)
    print("=== 모델 답변 ===")
    print(reply)
    if correct_answer:
        print("\n=== 학습 데이터 정답 ===")
        print(correct_answer)
    print("=" * 50)

```

---

## 4. 사용 예시

### 4.1 RESPONSE_MODEL 호출

```python
ask_model(
    "RESPONSE_MODEL",
    file_id="APT_FP_OBJ_009075352.PNG",
    rooms="3개",
    structure="타워형",
    grade="우수",
    question="타워형 구조 중에서 수납 공간 평가는 어떤가요?",
    correct_answer="이 집은 **[타워형]** 구조이며, 수납 공간은 현재 **[미흡]** 수준으로 평가되었습니다."
)

```

### 4.2 WORD_MODEL 호출

```python
ask_model(
    "WORD_MODEL",
    question="샌드위치 패널이란 무엇인가요?",
    correct_answer="단열재를 금속판 사이에 끼워 만든 판재로, 외벽 및 지붕 마감재로 사용됩니다."
)

```

### 4.3 COMBINED_MODEL 호출

```python
# 도면 안내 기능 사용 시
ask_model(
    "COMBINED_MODEL_RESPONSE",
    file_id="APT_FP_OBJ_009075352.PNG",
    rooms="3개",
    structure="타워형",
    grade="우수",
    question="타워형 구조 중에서 수납 공간 평가는 어떤가요?"
)

# 용어 사전 기능 사용 시
ask_model(
    "COMBINED_MODEL_WORD",
    question="라멘구조란 무엇인가요?",
    correct_answer="기둥과 보가 강하게 결합되어 벽체 없이도 수평하중을 지지할 수 있는 구조 시스템입니다."
)

```

---

## 5. ⚠️ 주의사항

1. **키 사용 준수:** `COMBINED_MODEL` 사용 시, 목적에 맞는 접미사(`_RESPONSE` 또는 `_WORD`)를 반드시 확인하여 사용하십시오.
2. **검증:** 결과 확인 시 `correct_answer`를 함께 출력하여 실제 학습 데이터의 의도와 일치하는지 상시 모니터링하는 것이 좋습니다.

---