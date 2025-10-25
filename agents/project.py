import aiohttp
import asyncio
import json
from api.api_sys import API_URL, HEADERS
from utils.json_cleaner import clean_json_text


class ProjectAgent:
    """AI 專案生成 Agent - 專職 AI 溝通"""

    # === 🧠 初次生成整份專案資料 ===
    @staticmethod
    async def generate_project_json(project_name: str) -> dict:
        """根據專案名稱生成完整專案 JSON"""
        prompt = f"""
你是一名資深系統設計師。
請根據使用者輸入的專案名稱「{project_name}」，
產生一份標準 JSON 結構的系統設計初稿（請使用繁體中文，且只輸出 JSON，不要多餘文字）。

你的角色：系統分析與架構設計專家  
你的任務：根據輸入的專案名稱，產生結構化 JSON 結果。  
規則：
1. 只輸出 JSON，不要任何文字解釋。
2. JSON 格式必須正確可被 Python json.loads() 解析。
3. 所有中文字請使用繁體中文。
4. JSON 開頭與結尾必須是 {{ 與 }}。

JSON 結構如下：
{{
    "project_name": "{project_name}",
    "description": "系統用途與特色簡述",
    "architecture": "整體系統架構與主要模組說明",
    "frontend": {{
        "language": "前端語言（例如：JavaScript、TypeScript、Vue、React）",
        "platform": "前端平台或框架（例如：Web、App）",
        "library": "主要前端函式庫或框架（例如：React、Vue.js）"
    }},
    "backend": {{
        "language": "後端語言（例如：Python、Java、Node.js）",
        "platform": "後端平台（例如：FastAPI、Spring Boot）",
        "library": "主要後端框架或 ORM（例如：SQLAlchemy、Express.js）"
    }}
}}
⚠️ 請務必只輸出有效 JSON，開頭與結尾必須為 {{ 與 }}。
"""
        return await ProjectAgent._send_request(prompt)

    # === 🔁 針對指定欄位重新生成 ===
    @staticmethod
    async def regenerate_fields(project_name: str, fields: list[str]) -> dict:
        """僅針對指定欄位重新生成合理內容"""
        prompt = f"""
你的角色：系統分析與架構設計專家  
你的任務：根據輸入的專案名稱，重新生成指定欄位的內容。  

使用者的專案名稱為「{project_name}」。
請僅針對以下欄位重新生成合理內容（使用繁體中文，且只輸出 JSON，不要多餘說明）：
{", ".join(fields)}

輸出格式範例如下（只保留需要的欄位）：
{{
    "description": "新的專案描述",
    "architecture": "新的系統架構說明",
    "frontend": {{
        "language": "新前端語言",
        "platform": "新前端平台",
        "library": "新前端函式庫"
    }},
    "backend": {{
        "language": "新後端語言",
        "platform": "新後端平台",
        "library": "新後端框架或函式庫"
    }}
}}
⚠️ 請勿輸出任何非 JSON 的文字。
"""
        return await ProjectAgent._send_request(prompt)

    # === 🚀 統一呼叫 Gemini API ===
    @staticmethod
    async def _send_request(prompt: str) -> dict:
        """統一呼叫 Gemini API 並解析回傳結果（含重試與錯誤防護）"""
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,          # 降溫提升穩定性
                "maxOutputTokens": 1024,
                "topP": 0.9,
                "topK": 40,
            },
        }

        for attempt in range(3):  # 最多重試 3 次
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(API_URL, headers=HEADERS, json=data, timeout=60) as response:
                        if response.status != 200:
                            print(f"❌ API 請求失敗: {response.status}")
                            await asyncio.sleep(2)
                            continue

                        result = await response.json()
                        text = (
                            result.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "{}")
                        )

                        print("\n🧠 原始 AI 回覆文字：")
                        print(text)

                        # 嘗試從文字中擷取最外層 JSON（移除多餘解釋）
                        if "{" in text and "}" in text:
                            text = text[text.find("{"): text.rfind("}") + 1]

                        # 清理 JSON
                        cleaned = clean_json_text(text) if "clean_json_text" in globals() else text
                        print("\n🧹 清理後 JSON 文字：")
                        print(cleaned)

                        # 嘗試解析 JSON
                        json_data = json.loads(cleaned)
                        print("\n📦 解析後 JSON 物件：")
                        print(json.dumps(json_data, indent=4, ensure_ascii=False))
                        return json_data

            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                print(f"⚠️ 連線錯誤或超時：{e}")
            except json.JSONDecodeError:
                print("⚠️ JSON 解析失敗，嘗試重試…")

            await asyncio.sleep(2)  # 每次重試延遲 2 秒

        print("🚫 三次嘗試均失敗，返回空結果。")
        return {}
