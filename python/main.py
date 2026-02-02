import psycopg2
from openai import OpenAI
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pgvector.psycopg2 import register_vector

app = FastAPI()
client = OpenAI(api_key="YOUR_OPENAI_API_KEY")














# DB 연결 및 pgvector 등록
def get_db_conn():
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        database="arae",
        user="postgres",
        password="1234"
    )
    register_vector(conn) # 이거 안 하면 벡터 검색 시 에러 날 수 있음
    return conn

# 자바에서 보낼 데이터 구조 정의
class ChatRequest(BaseModel):
    email: str
    question: str

# 2. 메인 RAG 로직
@app.post("/chatllm") # 자바 서비스의 URL과 맞춤
def ask_rag(request: ChatRequest):
    try:
        # 1. 질문 임베딩
        emb_res = client.embeddings.create(
            input=request.question,
            model="text-embedding-3-small"
        )
        q_embedding = emb_res.data[0].embedding

        # 2. 벡터 유사도 검색 (Legal + Internal 합쳐서 검색 예시)
        conn = get_db_conn()
        with conn.cursor() as cur:
            search_query = """
                SELECT content, region FROM legal_documents 
                ORDER BY embedding <=> %s::vector LIMIT 3
            """
            cur.execute(search_query, (q_embedding,))
            results = cur.fetchall()

        # 3. 컨텍스트 구성
        context = "\n".join([f"[{r[1]}] {r[0]}" for r in results])

        # 4. LLM 답변 및 요약 제목 생성
        llm_res = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"당신은 법률 전문가입니다. 다음 내용을 참고해서 답변하세요: {context}"},
                {"role": "user", "content": f"질문: {request.question}\n\n답변은 친절하게 해주고, 답변의 내용을 한 줄로 요약한 'summaryTitle'도 함께 만들어줘."}
            ]
        )
        
        full_text = llm_res.choices[0].message.content
        # 임시로 제목과 본문 분리 (실제로는 LLM에게 JSON 포맷으로 달라고 하면 더 정확함)
        return {
            "summaryTitle": request.question[:15] + "...", # 임시 요약
            "answer": full_text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))