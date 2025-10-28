import aiohttp
import asyncio
import json
from api.api_sys import API_URL, HEADERS
from utils.json_cleaner import clean_json_text


class ProjectAgent:
    """AI 專案生成 Agent - 專職 AI 溝通"""

    # === 🧠 初次或完整再生皆可用 ===
    @staticmethod
    async def generate_project_json(project_name: str) -> dict:
        """根據專案名稱生成完整專案 JSON"""
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

    # === 🚀 呼叫 Gemini 並解析結果（含詳細終端輸出） ===
    @staticmethod
    async def _send_request(prompt: str) -> dict:
        """呼叫 Gemini 並印出三階段輸出：原始 → 清理後 → 解析後"""
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048,
                "topP": 0.9,
                "topK": 40,
            },
        }

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(API_URL, headers=HEADERS, json=data, timeout=60) as response:
                        if response.status != 200:
                            print(f"❌ API 回應錯誤: {response.status}")
                            await asyncio.sleep(1.5)
                            continue

                        result = await response.json()
                        text = (
                            result.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "{}")
                        )

                        # === 🧠 第1段：原始 AI 回傳文字 ===
                        print("\n🧠【原始 AI 回覆文字】")
                        print("-" * 80)
                        print(text)
                        print("-" * 80)

                        # 清理出 JSON 區塊
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