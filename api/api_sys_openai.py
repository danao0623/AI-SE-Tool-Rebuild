import os
from dotenv import load_dotenv

# 指定要載入的 OpenAI API key 檔案
dotenv_path = os.path.join(os.path.dirname(__file__), "openai_key.env")
load_dotenv(dotenv_path)

API_KEY = os.getenv("openai_key")
if not API_KEY:
    raise ValueError("❌ 沒有讀到 openai_key，請確認 openai_key.env 檔案是否存在且格式正確")

# --- OpenAI 專用設定 ---
MODEL_NAME = "gpt-4.1-mini"   # 你可以改成 gpt-4.1 / gpt-4o / gpt-4.1-turbo 等

API_URL = "https://api.openai.com/v1/chat/completions"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

print("🟣 已成功載入 OpenAI API Key")
print(f"model_name: {MODEL_NAME}")
