# 📁 agents/project_agent.py
import aiohttp
import asyncio
import json
from api.api_sys import API_URL, HEADERS
from utils.json_cleaner import clean_json_text


class ProjectAgent:
    """AI 專案生成 Agent - 專職 AI 溝通"""

    # === 🧠 初次生成專案資料 ===
    @staticmethod
    async def generate_project_json(project_name: str) -> dict:
        """根據專案名稱生成完整專案 JSON"""
        prompt = f"""
你是一名資深系統設計師。
請根據使用者輸入的專案名稱「{project_name}」，產生一份標準 JSON 結構的系統設計初稿。
請使用繁體中文，且只輸出 JSON，不要任何多餘文字。

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

    # === 🔁 再生指定欄位 ===
    @staticmethod
    async def regenerate_fields(project_name: str, fields: list[str]) -> dict:
        """針對指定欄位重新生成合理內容"""
        field_mapping = {
            "專案描述": "description",
            "系統架構": "architecture",
            "前端語言": "frontend.language",
            "前端平台": "frontend.platform",
            "前端函式庫": "frontend.library",
            "後端語言": "backend.language",
            "後端平台": "backend.platform",
            "後端函式庫": "backend.library",
        }

        translated_fields = [field_mapping.get(f, f) for f in fields]

        prompt = f"""
你的角色：系統分析與架構設計專家。  
請根據專案名稱「{project_name}」，僅重新生成以下欄位：
{', '.join(translated_fields)}

請直接輸出 JSON，不要其他文字。
若屬於 frontend 或 backend，請放入對應子物件中。
JSON 範例：
{{
  "description": "新的描述內容",
  "architecture": "新的架構內容",
  "frontend": {{
    "language": "React",
    "platform": "Web",
    "library": "TailwindCSS"
  }},
  "backend": {{
    "language": "Python",
    "platform": "FastAPI",
    "library": "SQLAlchemy"
  }}
}}
⚠️ 開頭與結尾必須為 {{ 與 }}。
"""
        return await ProjectAgent._send_request(prompt)

    # === 🚀 呼叫 Gemini 並解析結果（強化容錯版） ===
    @staticmethod
    async def _send_request(prompt: str) -> dict:
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048,
                "topP": 0.9,
                "topK": 40,
            },
        }

        for attempt in range(3):  # 最多嘗試 3 次
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

                        print("\n🧠 原始 AI 回覆文字：")
                        print(text)

                        # 🔹 偵測並提取 ```json 區塊
                        if "```json" in text:
                            start = text.find("```json") + len("```json")
                            end = text.rfind("```")
                            text = text[start:end].strip()

                        # 🔹 自動補齊缺失的結尾
                        if text.count("{") > text.count("}"):
                            text += "}" * (text.count("{") - text.count("}"))

                        # 🔹 嘗試擷取最外層 JSON
                        if "{" in text and "}" in text:
                            text = text[text.find("{"): text.rfind("}") + 1]

                        # 🔹 清理亂字
                        cleaned = clean_json_text(text) if "clean_json_text" in globals() else text
                        print("\n🧹 清理後 JSON 文字：")
                        print(cleaned)

                        # 🔹 嘗試解析
                        try:
                            json_data = json.loads(cleaned)
                        except json.JSONDecodeError:
                            print("⚠️ JSON 格式仍有問題，嘗試自動修復。")
                            fixed_text = cleaned.replace("```", "").replace("json", "")
                            fixed_text = fixed_text.replace("\\n", "\n").strip()
                            json_data = json.loads(fixed_text)

                        print("\n📦 解析後 JSON 物件：")
                        print(json.dumps(json_data, indent=4, ensure_ascii=False))

                        if not json_data:
                            print("⚠️ 回傳為空物件，嘗試重試…")
                            await asyncio.sleep(2)
                            continue

                        return json_data

            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                print(f"⚠️ API 連線異常: {e}")
            except json.JSONDecodeError:
                print("⚠️ JSON 解析失敗，再次嘗試…")

            await asyncio.sleep(1.5)

        # === 若三次都失敗，執行 fallback prompt ===
        print("🚫 三次嘗試均失敗，執行補救 prompt。")
        fallback = {
            "contents": [{"parts": [{"text": prompt + "\n請務必完整輸出 JSON，不要留空或錯誤。"}]}]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(API_URL, headers=HEADERS, json=fallback, timeout=60) as resp:
                    text = (await resp.text()).strip()
                    if "{" in text and "}" in text:
                        text = text[text.find("{"): text.rfind("}") + 1]
                        return json.loads(text)
        except Exception as e:
            print(f"⚠️ Fallback 仍失敗：{e}")

        print("⚠️ 全部嘗試失敗，返回空字典。")
        return {}