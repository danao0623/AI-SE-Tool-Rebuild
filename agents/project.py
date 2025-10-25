# agents/project_agent.py
import requests
import json
from api.api_sys import API_URL, HEADERS
from utils.json_cleaner import clean_json_text

class ProjectAgent:
    """AI 專案生成 Agent - 專職 AI 溝通"""

    @staticmethod
    async def generate_project_json(project_name: str) -> dict:
        """初次生成整份專案資料"""
        prompt = f"""
        你是一名資深系統設計師，請根據使用者輸入的專案名稱「{project_name}」，
        生成以下格式的 JSON（繁體中文）：
        {{
            "project_name": "{project_name}",
            "description": "請簡述此系統的用途與特色",
            "architecture": "請描述系統架構與主要模組",
            "frontend": {{
                "language": "前端語言",
                "platform": "前端平台",
                "library": "主要前端函式庫"
            }},
            "backend": {{
                "language": "後端語言",
                "platform": "後端平台",
                "library": "主要後端框架或函式庫"
            }}
        }}
        僅輸出 JSON，不要多餘說明。
        """
        return await ProjectAgent._send_request(prompt)

    @staticmethod
    async def regenerate_fields(project_name: str, fields: list[str]) -> dict:
        """針對指定欄位重新生成"""
        field_list = "、".join(fields)
        prompt = f"""
        使用者的專案名稱為「{project_name}」。
        請僅針對以下欄位重新生成合理內容（繁體中文）：
        {field_list}
        只輸出 JSON，例如：
        {{
            "description": "...",
            "architecture": "...",
            "frontend_language": "...",
            ...
        }}
        """
        return await ProjectAgent._send_request(prompt)

    @staticmethod
    async def _send_request(prompt: str) -> dict:
        """統一呼叫 Gemini API 並解析回傳結果"""
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.9,
                "maxOutputTokens": 1024,
                "topP": 0.8,
                "topK": 10,
            },
        }

        response = requests.post(API_URL, headers=HEADERS, json=data)
        if response.status_code != 200:
            print(f"❌ API 請求失敗: {response.status_code}")
            return {}

        text = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        try:
            cleaned = clean_json_text(text) if "clean_json_text" in globals() else text
            return json.loads(cleaned)
        except json.JSONDecodeError:
            print("⚠️ 無法解析 AI 回覆內容")
            return {}
