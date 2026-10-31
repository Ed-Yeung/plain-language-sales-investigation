import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek

load_dotenv()

MODEL = "deepseek-chat"          # 或 "deepseek-v4-flash"，建議先用 deepseek-chat
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not DEEPSEEK_API_KEY:
    raise RuntimeError("請在 .env 設定 DEEPSEEK_API_KEY")

def get_llm(temperature: float = 0):
    return ChatDeepSeek(
        model=MODEL,
        api_key=DEEPSEEK_API_KEY,
        temperature=temperature,
        # 若遇到 structured output 問題，可取消註解關閉 thinking
        # extra_body={"thinking": {"type": "disabled"}}
    )

MAX_CODE_ATTEMPTS = 3
CSV_PATH = "Data/Sample - Superstore.csv"