import aiohttp
import asyncio
import json

# ✅ 改成從 OpenAI 的設定檔匯入
from api.api_sys_openai import API_URL, HEADERS, MODEL_NAME

from utils.json_cleaner import clean_json_text


class ProjectAgent:
    """AI 專案生成 Agent - 專職 AI 溝通（OpenAI 版本）"""

    # === 🧠 初次或完整再生皆可用 ===
    @staticmethod
    async def generate_project_json(project_name: str) -> dict:
        """根據專案名稱生成完整專案 JSON（與原本結構相同）"""
        # 👉 這段 prompt 完全沿用你原本的（只是現在給 OpenAI 用）
        prompt = f"""
你是一名資深系統設計師。
請根據使用者輸入的專案名稱「{project_name}」，產生一份標準 JSON 結構的系統設計初稿。
請使用繁體中文，且只輸出 JSON，不要任何多餘文字。
（本輸出將作為完整再生依據）

JSON 結構如下：
{{
    "project_name": "{project_name}",
    "description": "系統用途與特色簡述",
    "architecture": "整體系統架構與主要模組說明",
    "frontend": {{
        "language": "前端語言（例如：JavaScript、Vue）",
        "platform": "前端平台（例如：Web、App）",
        "library": "主要前端框架（例如：React、Vue.js）"
    }},
    "backend": {{
        "language": "後端語言（例如：Python、Node.js）",
        "platform": "後端平台（例如：FastAPI、Spring Boot）",
        "library": "主要後端框架（例如：SQLAlchemy、Express.js）"
    }}
}}
⚠️ 請務必只輸出 JSON，開頭與結尾必須為 {{ 與 }}。
"""
        return await ProjectAgent._send_request(prompt)

    # === 🚀 呼叫 OpenAI 並解析結果（含詳細終端輸出） ===
    @staticmethod
    async def _send_request(prompt: str) -> dict:
        """
        改成呼叫 OpenAI chat/completions。
        維持三階段輸出：原始 → 清理後 → 解析後。
        """

        # 🟣 OpenAI 需要的是 model + messages，不再是 contents / generationConfig
        data = {
            "model": MODEL_NAME,   # 在 api_sys_openai.py 裡目前是 gpt-4.1-mini
            "messages": [
                {
                    "role": "system",
                    "content": "你是一名資深系統設計師，負責產生嚴格符合需求的 JSON 結構。"
                },
                {
                    "role": "user",
                    "content": prompt
                },
            ],
            # 要求 OpenAI 嚴格輸出 JSON
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
        }

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    headers = dict(HEADERS)
                    headers["Accept-Encoding"] = "gzip, deflate, identity"
                    async with session.post(API_URL, headers=HEADERS, json=data, timeout=60) as response:
                        if response.status != 200:
                            print(f"❌ API 回應錯誤: {response.status}")
                            raw = await response.read()
                            print("🔎 錯誤內容(raw前200bytes):", raw[:200])
                            await asyncio.sleep(1.5)
                            # 印出錯誤內容，方便除錯
                            try:
                                error_text = await response.text()
                                print("🔎 錯誤內容:", error_text)
                            except Exception:
                                pass
                            await asyncio.sleep(1.5)
                            continue

                        result = await response.json()

                        # 🔁 OpenAI 回傳結構：choices[0].message.content
                        text = (
                            result.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "{}")
                        )

                        # === 🧠 第1段：原始 AI 回傳文字 ===
                        print("\n🧠【原始 AI 回覆文字】")
                        print("-" * 80)
                        print(text)
                        print("-" * 80)

                        # 一般來說，response_format = json_object 會直接是純 JSON
                        # 但保險起見，還是沿用你原本的清理流程
                        if "```json" in text:
                            start = text.find("```json") + len("```json")
                            end = text.rfind("```")
                            text = text[start:end].strip()
                        if "{" in text and "}" in text:
                            text = text[text.find("{"): text.rfind("}") + 1]

                        # === 🧹 第2段：清理後文字 ===
                        cleaned = clean_json_text(text) if "clean_json_text" in globals() else text
                        print("\n🧹【清理後 JSON 文字】")
                        print("-" * 80)
                        print(cleaned)
                        print("-" * 80)

                        # 嘗試解析成 JSON
                        json_data = {}
                        try:
                            json_data = json.loads(cleaned)
                        except json.JSONDecodeError:
                            print("⚠️ JSONDecodeError，嘗試修復格式…")
                            fixed = cleaned.replace("\\n", "\n").replace("```", "").strip()
                            json_data = json.loads(fixed)

                        # === 📦 第3段：解析後 JSON 結構 ===
                        print("\n📦【解析後 JSON 物件】")
                        print(json.dumps(json_data, indent=4, ensure_ascii=False))
                        print("=" * 80)

                        if not json_data:
                            print("⚠️ 回傳為空物件，重試中…")
                            await asyncio.sleep(1.5)
                            continue

                        return json_data

            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                print(f"⚠️ API 連線異常: {e}")
            except json.JSONDecodeError:
                print("⚠️ JSON 解析失敗，再次嘗試…")

            await asyncio.sleep(1.5)

        print("🚫 三次嘗試均失敗，返回空字典。")
        return {}
