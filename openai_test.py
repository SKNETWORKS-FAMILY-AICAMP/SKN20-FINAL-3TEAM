from dotenv import load_dotenv
import os

load_dotenv()  # 이 줄이 없으면 .env는 무시됨

print(os.getenv("OPENAI_API_KEY"))  