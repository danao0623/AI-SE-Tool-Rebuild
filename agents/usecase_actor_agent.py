# agents/usecase_actor_agent.py

import json
import aiohttp

from api.api_sys import API_URL, HEADERS
from utils.json_cleaner import clean_json_text


class UsecaseActorAgent:
    """
    使用案例 / 角色 Agent（純線上 Gemini 版）

    兩階段流程：
    1. 先呼叫 LLM 產生 5 個 Actor（名稱 + 描述）
    2. 再呼叫 LLM 根據這 5 個 Actor 產生每個 Actor 對應的 3 個 Use Case（共 15 個）

    → 最後組成統一 JSON 給 FlowController 與 View。
    """

    # ================================================================
    #                       對外主要入口
    # ================================================================
    @staticmethod
    async def generate_actor_usecase_json(project_info: dict) -> dict:
        project_name = project_info.get("name", "未命名專案")

        # STEP 1：產生 5 Actors
        actors = await UsecaseActorAgent._generate_actors(project_name)
        if not actors:
            print("❌ 無 Actors，AI 生成失敗")
            return {}

        # STEP 2：產生每個 Actor 3 個 UseCases（共 15 筆）
        usecase_list = await UsecaseActorAgent._generate_usecase_list(project_name, actors)
        if not usecase_list:
            print("❌ 無 UseCase List，AI 生成失敗")
            return {}

        # STEP 3：重組成系統統一格式
        use_cases: list[dict] = []
        for uc in usecase_list:
            use_cases.append(
                {
                    "name": uc.get("use_case_name", ""),
                    "summary": uc.get("description", ""),
                    "primary_actor": uc.get("actor", ""),
                    "other_actors": [],
                }
            )

        final = {
            "project_name": project_name,
            "actors": actors,
            "use_cases": use_cases,
        }

        print("\n📦【UsecaseActorAgent 最終完整 JSON】")
        print(json.dumps(final, ensure_ascii=False, indent=4))
        print("=" * 80)

        return final

    # ================================================================
    #                      第一階段：產生 5 個 Actor
    # ================================================================
    @staticmethod
    async def _generate_actors(project_name: str) -> list[dict]:

        prompt = f"""
你是一名資深系統分析師，請根據「{project_name}」系統需求，
產生 5 位系統使用者（Actor），包含以下內容：

- id：從 1 開始編號
- name：角色名稱
- description：角色的職責描述

請務必以**純 JSON**格式回答，不要加入文字說明，也不要加上 ```json。

格式如下：
{{
  "project_name": "{project_name}",
  "use_case_actor": [
    {{
      "id": 1,
      "name": "角色名稱",
      "description": "角色描述"
    }}
  ]
}}
"""

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 1.0,
                "maxOutputTokens": 2048,
                "topP": 0.8,
                "topK": 10,
            },
        }

        # ---- 呼叫 Gemini ----
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_URL, headers=HEADERS, json=payload, timeout=60
            ) as resp:

                if resp.status != 200:
                    print("❌ _generate_actors API 錯誤:", resp.status)
                    print(await resp.text())
                    return []

                data = await resp.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "{}")
                )

        cleaned = clean_json_text(text)

        try:
            json_obj = json.loads(cleaned)
        except Exception:  # noqa: BLE001
            print("❌ Actors JSON 解析失敗")
            print(cleaned)
            return []

        actors_raw = json_obj.get("use_case_actor", []) or []

        # 整理格式：我們只需要 name + description
        actors = [
            {
                "name": a.get("name", ""),
                "description": a.get("description", ""),
            }
            for a in actors_raw
        ]

        print("\n🎭【_generate_actors 產生的 Actors】")
        print(json.dumps(actors, ensure_ascii=False, indent=4))
        print("=" * 80)

        return actors

    # ================================================================
    #         第二階段：產生每個 Actor 的 3 個 UseCases（共 15）
    # ================================================================
    @staticmethod
    async def _generate_usecase_list(
        project_name: str, actors: list[dict]
    ) -> list[dict]:

        prompt = f"""
你是一名系統分析師。以下是此系統的 5 位使用者角色（Actors）：

{json.dumps(actors, ensure_ascii=False, indent=4)}

請為每一位 Actor 設計 **3 個使用案例（Use Case）**，
每個 UseCase 必須包含：
- actor：角色名稱
- use_case_name：使用案例名稱
- description：使用案例描述（簡要）

總共應該產生 15 個 Use Case。

⚠️ 請嚴格輸出純 JSON，不要任何說明文字、不要 Markdown。

格式：
{{
  "project_name": "{project_name}",
  "use_case_list": [
    {{
      "actor": "角色名稱",
      "use_case_name": "名稱",
      "description": "描述"
    }}
  ]
}}
"""

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 1.0,
                "maxOutputTokens": 4096,
                "topP": 0.8,
                "topK": 10,
            },
        }

        # ---- 呼叫 Gemini ----
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_URL, headers=HEADERS, json=payload, timeout=60
            ) as resp:

                if resp.status != 200:
                    print("❌ _generate_usecase_list API 錯誤:", resp.status)
                    print(await resp.text())
                    return []

                data = await resp.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "{}")
                )

        cleaned = clean_json_text(text)

        try:
            parsed = json.loads(cleaned)
        except Exception:  # noqa: BLE001
            print("❌ UseCaseList JSON 解析失敗")
            print(cleaned)
            return []

        use_case_list = parsed.get("use_case_list", []) or []

        print("\n📘【_generate_usecase_list 產生的 UseCase List】")
        print(json.dumps(use_case_list, ensure_ascii=False, indent=4))
        print("=" * 80)

        return use_case_list