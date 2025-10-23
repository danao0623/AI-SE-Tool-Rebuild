import os
from dotenv import load_dotenv

# ✅ 明確指定要載入的 .env 檔案路徑
dotenv_path = os.path.join(os.path.dirname(__file__), "api_key.env")
load_dotenv(dotenv_path)

API_KEY = os.getenv("gemini_key")
if not API_KEY:
    raise ValueError("❌ 沒有讀到 gemini_key，請確認 .env 檔案")

MODEL_NAME = "models/gemini-2.5-flash"   # 或 "models/gemini-2.5-pro"

API_URL = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={API_KEY}"
HEADERS = {"Content-Type": "application/json"}

print("✅ 已成功載入 gemini_key 並設定 API_URL 和 HEADERS")
print(f"model_name: {MODEL_NAME}")