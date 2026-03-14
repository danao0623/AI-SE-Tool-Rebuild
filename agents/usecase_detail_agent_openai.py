from __future__ import annotations
from typing import List, Dict, Any
import aiohttp
import asyncio
import json

from api.api_sys_openai import API_URL, HEADERS, MODEL_NAME
from utils.json_cleaner import clean_json_text


class UseCaseDetailAgent:
    """
    使用案例明細 (Use Case Detail) 的 AI Agent（OpenAI 版本）

    職責：
    - 接收一批 UseCase 資料 (actor, name, description ...)
    - 逐一呼叫 OpenAI，生成：
        - 正常程序
        - 例外程序
        - 觸發條件
        - 前置條件
        - 後置條件
    - 回傳結構化的 details dict，讓 Flow / Controller 自行寫入資料庫
    """

    # ============================================================
    #  對外主要方法：一次處理多個 UseCase
    # ============================================================
    @staticmethod
    async def generate_details_for_usecases(
        usecases: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        給定多個 UseCase，逐一呼叫 AI 產生 Detail。

        入參 usecases 每一筆至少要能取到：
        - actor 名稱（例如 key: "actor" 或 "主要角色"）
        - usecase 名稱（例如 key: "use_case_name" / "name" / "使用案例名稱"）
        - description / summary / 概述

        回傳格式（List[Dict]）每一筆包含：
        {
            "source": 原始 usecase dict,
            "details": {
                "正常程序": "...",
                "例外程序": "...",
                "觸發條件": "...",
                "前置條件": "...",
                "後置條件": "..."
            }
        }
        """
        results: List[Dict[str, Any]] = []

        for uc in usecases:
            detail = await UseCaseDetailAgent._generate_single_detail(uc)
            if not detail:
                # 若該筆失敗，就先跳過（你可以依需求改成回傳空 dict）
                continue

            results.append(
                {
                    "source": uc,      # 保留原始 usecase，方便 Flow / Controller 對應 ID
                    "details": detail, # AI 產出的明細
                }
            )

        return results

    # ============================================================
    #  單一 UseCase：呼叫 OpenAI 產生 Detail
    # ============================================================
    @staticmethod
    async def _generate_single_detail(
        usecase: Dict[str, Any],
    ) -> Dict[str, str] | None:
        """
        為單一 UseCase 產生 Detail。

        usecase 來源可以是：
        - DB 回傳的 row（例如 {"id": 1, "使用案例名稱": "...", "概述": "...", "主要角色": "..."}）
        - 或 Flow 自行組成的 dict

        回傳：
        {
            "正常程序": "...",
            "例外程序": "...",
            "觸發條件": "...",
            "前置條件": "...",
            "後置條件": "..."
        }
        或失敗時回傳 None
        """

        # ---- 嘗試從多種欄位名稱取值，避免你之後欄位命名稍微不同就壞掉 ----
        actor = (
            usecase.get("actor")
            or usecase.get("主要角色")
            or usecase.get("primary_actor")
            or ""
        )
        name = (
            usecase.get("use_case_name")
            or usecase.get("name")
            or usecase.get("使用案例名稱")
            or ""
        )
        desc = (
            usecase.get("description")
            or usecase.get("summary")
            or usecase.get("概述")
            or ""
        )

        if not name:
            print("⚠️ _generate_single_detail：該 UseCase 缺少名稱，略過。")
            return None

        prompt = f"""
你是一名專業系統分析師，請根據以下資訊為使用案例分別產生下列內容：
1. 正常程序
2. 例外程序
3. 觸發條件
4. 前置條件
5. 後置條件

請使用繁體中文，並嚴格以 JSON 格式產出，格式如下（key 名稱不可修改）：

{{
  "正常程序": "1. ...\\n2. ...\\n3. ...",
  "例外程序": "1. ...\\n2. ...\\n3. ...",
  "觸發條件": "......",
  "前置條件": "......",
  "後置條件": "......"
}}

⚠️ 請務必符合以下要求：
- 僅輸出上述 JSON 結構，不要有多餘文字說明。
- 程序請以「條列式步驟」呈現，每一步以「編號. 內容」方式書寫。
- 若無明確內容，也請給出合理的描述，不要留空字串。

使用者角色：{actor}
使用案例名稱：{name}
使用案例描述：{desc}
"""

        # ---- 呼叫 OpenAI （和你 ProjectAgent 的模式一致）----
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一名資深系統分析師，負責產生嚴格符合需求的 JSON 結構。",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
        }

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        API_URL, headers=HEADERS, json=payload, timeout=90
                    ) as resp:
                        if resp.status != 200:
                            print(
                                f"❌ UseCaseDetailAgent API 錯誤 (status={resp.status})"
                            )
                            try:
                                print("🔎 錯誤內容:", await resp.text())
                            except Exception:
                                pass
                            await asyncio.sleep(1.5)
                            continue

                        data = await resp.json()

                # OpenAI 回傳內容：choices[0].message.content
                text = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "{}")
                )

                # === 🧠 原始文字輸出（除錯用） ===
                print("\n🧾 UseCaseDetailAgent 原始回應：")
                print("-" * 80)
                print(text)
                print("-" * 80)

                # 一般情況下，response_format=json_object 會直接是純 JSON 字串
                # 保險起見仍做一點清理
                if "```json" in text:
                    start = text.find("```json") + len("```json")
                    end = text.rfind("```")
                    text = text[start:end].strip()
                elif "```" in text:
                    # 處理一般 ``` 包起來的情況
                    start = text.find("```") + len("```")
                    end = text.rfind("```")
                    text = text[start:end].strip()

                if "{" in text and "}" in text:
                    text = text[text.find("{"): text.rfind("}") + 1]

                cleaned = clean_json_text(text)
                print("\n🧹 UseCaseDetailAgent 清理後 JSON 文字：")
                print("-" * 80)
                print(cleaned)
                print("-" * 80)

                detail_obj: Dict[str, Any] = json.loads(cleaned)

                # 簡單檢查一下關鍵欄位，有缺就補空字串
                for key in ["正常程序", "例外程序", "觸發條件", "前置條件", "後置條件"]:
                    detail_obj.setdefault(key, "")

                print("\n📦 UseCaseDetailAgent 解析後 JSON：")
                print(json.dumps(detail_obj, ensure_ascii=False, indent=2))
                print("=" * 80)

                return {
                    "正常程序": str(detail_obj.get("正常程序", "")).strip(),
                    "例外程序": str(detail_obj.get("例外程序", "")).strip(),
                    "觸發條件": str(detail_obj.get("觸發條件", "")).strip(),
                    "前置條件": str(detail_obj.get("前置條件", "")).strip(),
                    "後置條件": str(detail_obj.get("後置條件", "")).strip(),
                }

            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                print(f"⚠️ UseCaseDetailAgent API 連線異常: {e}")
            except json.JSONDecodeError as e:
                print(f"⚠️ UseCaseDetailAgent JSON 解析失敗: {e}")

            print(f"🔄 UseCaseDetailAgent 第 {attempt + 1} 次嘗試失敗，準備重試…")
            await asyncio.sleep(1.5)

        print("🚫 UseCaseDetailAgent 三次嘗試均失敗，回傳 None。")
        return None
