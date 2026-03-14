from __future__ import annotations
from typing import Dict, Any, List

import json
import asyncio
import aiohttp

from nicegui import app

# ✅ 跟其它 OpenAI Agent 一樣的設定來源
from api.api_sys_openai import API_URL, HEADERS, MODEL_NAME  # type: ignore

# ✅ 用你現在專案在用的 json_cleaner
from utils.json_cleaner import clean_json_text  # type: ignore

# ✅ 新專案的 Usecase / Event 控制器
from controllers.usecase_controller import UsecaseController  # type: ignore
from controllers.event_list_controller import EventListController  # type: ignore
from controllers.event_controller import EventController  # type: ignore


class EventSummaryAgent:
    """
    事件三段式 Summary Agent（OpenAI 版）

    功能：
    - 讀取「目前專案」底下所有 UseCase（含正常/例外程序）
    - 呼叫 OpenAI，把流程文字拆成事件導向三段式：
        - 類型：Request / Process / Response
        - 說明：事件描述
    - 寫回 DB 的 EventList / Event
    """

    # ============================================================
    # 小工具：取得目前專案
    # ============================================================
    @staticmethod
    def _get_current_project() -> Dict[str, Any]:
        project = app.storage.user.get("current_project")
        if not project:
            raise RuntimeError("no_project")

        pid = project.get("id")
        if not pid:
            raise RuntimeError("no_project_id")

        return project

    # ============================================================
    # 對單一流程（正常/例外）呼叫 OpenAI，取得事件列表
    # ============================================================
    @staticmethod
    async def _call_openai_for_events(
        use_case_name: str,
        flow_type: str,
        flow_text: str,
    ) -> Dict[str, Any]:
        """
        flow_type: "正常程序" 或 "例外程序"
        flow_text: 對應欄位的完整文字（1. ...\\n2. ...）
        回傳格式預期：
        {
            "事件列表": [
                {"類型": "Request", "說明": "..."},
                ...
            ]
        }
        """

        if not flow_text.strip():
            # 該流程沒有內容，直接回空
            return {"事件列表": []}

        prompt = f"""
你是一位經驗豐富的系統分析師，正在分析資訊系統的使用案例。

使用案例名稱：{use_case_name}
流程種類：{flow_type}

以下是原始的「{flow_type}」內容（每行代表一個步驟）：
{flow_text}

請你從「Actor 與系統互動」的角度，將上述流程拆解為「事件導向」的三段式結構。
每一個事件必須標示為下列三種類型之一：
- Request：使用者或外部角色對系統發出的請求或操作
- Process：系統內部進行的處理、檢核、運算、查詢等
- Response：系統對使用者的回應，例如畫面更新、訊息提示、結果呈現

請嚴格遵守以下規則：
1. 每一事件只允許一個類型（Request / Process / Response）。
2. 說明需為 1 句完整的繁體中文句子，客觀、簡潔、避免過度補充。
3. 可以依常理將過於籠統的步驟拆成多個事件。
4. 僅輸出 JSON，不要任何解釋文字，也不要使用 Markdown（例如 ```）。

輸出 JSON 格式範例：
{{
  "事件列表": [
    {{"類型": "Request", "說明": "..." }},
    {{"類型": "Process", "說明": "..." }},
    {{"類型": "Response", "說明": "..." }}
  ]
}}

請依照上述格式輸出結果。
"""

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一名資深系統分析師，負責產生嚴格符合格式的事件導向 JSON 結構。",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
            "max_tokens": 2048,
        }

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        API_URL, headers=HEADERS, json=payload, timeout=90
                    ) as resp:
                        if resp.status != 200:
                            print(f"❌ EventSummaryAgent API 錯誤: {resp.status}")
                            try:
                                print(await resp.text())
                            except Exception:
                                pass
                            await asyncio.sleep(1.5)
                            continue

                        data = await resp.json()

                # OpenAI 回傳文字內容
                text = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "{}")
                )

                print(f"\n🧾 EventSummaryAgent 原始回應（{use_case_name} - {flow_type}）")
                print("-" * 80)
                print(text)
                print("-" * 80)

                # 一般來說 response_format=json_object 已是 JSON，但保險起見清理一次
                if "```json" in text:
                    start = text.find("```json") + len("```json")
                    end = text.rfind("```")
                    text = text[start:end].strip()
                if "{" in text and "}" in text:
                    text = text[text.find("{") : text.rfind("}") + 1]

                cleaned = clean_json_text(text)
                print("\n🧹 EventSummaryAgent 清理後 JSON 文字")
                print("-" * 80)
                print(cleaned)
                print("-" * 80)

                try:
                    json_data = json.loads(cleaned)
                except json.JSONDecodeError:
                    print("⚠️ JSONDecodeError，嘗試簡單修復…")
                    fixed = cleaned.replace("\\n", "\n").replace("```", "").strip()
                    json_data = json.loads(fixed)

                print("\n📦 EventSummaryAgent 解析後 JSON 物件")
                print(json.dumps(json_data, ensure_ascii=False, indent=2))
                print("=" * 80)

                # 保證有「事件列表」鍵
                if "事件列表" not in json_data or not isinstance(
                    json_data["事件列表"], list
                ):
                    json_data["事件列表"] = []

                return json_data

            except Exception as e:
                print(f"⚠️ EventSummaryAgent 呼叫失敗（第 {attempt+1} 次）：{e}")
                await asyncio.sleep(1.5)

        # 三次都失敗
        return {"事件列表": []}

    # ============================================================
    # 對單一 UseCase 產生「正常/例外」兩種 EventList 並寫入 DB
    # ============================================================
    @classmethod
    async def generate_for_single_usecase(cls, uc: Any) -> Dict[str, Any]:
        """
        uc: UsecaseController.list(...) 回傳的單筆 ORM 物件
        回傳資訊只做簡單統計，給 Flow / View 用
        """
        usecase_id = uc.id
        usecase_name = uc.name or ""

        normal_text = (uc.normal_process or "").strip()
        exception_text = (uc.exception_process or "").strip()

        created_lists: List[Dict[str, Any]] = []

        # --- 正常程序 ---
        normal_result = await cls._call_openai_for_events(
            use_case_name=usecase_name,
            flow_type="正常程序",
            flow_text=normal_text,
        )
        normal_events = normal_result.get("事件列表", []) or []
        if normal_events:
            event_list = await EventListController.add_event_list(
                list_type="正常程序",
                use_case_id=usecase_id,
            )
            for idx, ev in enumerate(normal_events, start=1):
                await EventController.add_event(
                    event_list_id=event_list.id,
                    sequence_no=idx,
                    type=ev.get("類型", "").strip(),
                    description=ev.get("說明", "").strip(),
                )
            created_lists.append(
                {"type": "正常程序", "count": len(normal_events), "list_id": event_list.id}
            )

        # --- 例外程序 ---
        exception_result = await cls._call_openai_for_events(
            use_case_name=usecase_name,
            flow_type="例外程序",
            flow_text=exception_text,
        )
        exception_events = exception_result.get("事件列表", []) or []
        if exception_events:
            event_list = await EventListController.add_event_list(
                list_type="例外程序",
                use_case_id=usecase_id,
            )
            for idx, ev in enumerate(exception_events, start=1):
                await EventController.add_event(
                    event_list_id=event_list.id,
                    sequence_no=idx,
                    type=ev.get("類型", "").strip(),
                    description=ev.get("說明", "").strip(),
                )
            created_lists.append(
                {"type": "例外程序", "count": len(exception_events), "list_id": event_list.id}
            )

        return {
            "usecase_id": usecase_id,
            "usecase_name": usecase_name,
            "lists": created_lists,
        }

    # ============================================================
    # 對「目前專案」全部 UseCase 產生事件列表
    # ============================================================
    @classmethod
    async def generate_for_current_project(cls) -> Dict[str, Any]:
        """
        Flow 可以直接呼叫這個：
        result = await EventSummaryAgent.generate_for_current_project()
        """

        try:
            project = cls._get_current_project()
        except RuntimeError as e:
            return {"ok": False, "reason": str(e)}

        pid = project["id"]

        # 讀取目前專案所有 UseCase（沿用 UsecaseDetailFlow 的寫法）
        usecases = await UsecaseController.list(project_id=pid)
        if not usecases:
            return {"ok": False, "reason": "no_usecase"}

        per_usecase_results: List[Dict[str, Any]] = []
        for uc in usecases:
            print(f"🔧 正在產生事件列表：UseCase <{uc.name}> (ID={uc.id})")
            one = await cls.generate_for_single_usecase(uc)
            per_usecase_results.append(one)

        total_lists = sum(len(r["lists"]) for r in per_usecase_results)
        total_events = sum(
            sum(l["count"] for l in r["lists"]) for r in per_usecase_results
        )

        return {
            "ok": True,
            "project_id": pid,
            "usecase_count": len(usecases),
            "event_list_count": total_lists,
            "event_count": total_events,
            "details": per_usecase_results,
        }