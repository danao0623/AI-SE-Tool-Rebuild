from __future__ import annotations

from typing import Any, Dict, List

from nicegui import app

from controllers.usecase_controller import UsecaseController
from controllers.event_list_controller import EventListController
from controllers.event_controller import EventController
from agents.event_summary_agent_openai import EventSummaryAgent


class EventSummaryFlowController:
    """三段式事件列表的 Flow 層

    功能：
    - 讀取目前專案底下的 UseCase 清單（給下拉選單）
    - 讀取指定 UseCase 的事件（正常 / 例外）
    - 呼叫 AI 產生 / 重生事件列表（單一或全部）
    """

    # ============================================================
    # 共用：取得目前專案 ID
    # ============================================================
    @staticmethod
    def _get_current_project() -> Dict[str, Any]:
        project = app.storage.user.get("current_project")
        if not project:
            raise RuntimeError("no_project")
        if "id" not in project:
            raise RuntimeError("no_project_id")
        return project

    @staticmethod
    def _get_current_project_id() -> int:
        project = EventSummaryFlowController._get_current_project()
        return int(project["id"])

    # ============================================================
    # 1. UseCase 清單
    # ============================================================
    @classmethod
    async def list_usecases_for_current_project(cls) -> List[Dict[str, Any]]:
        """回傳目前專案底下的 UseCase 清單，給下拉選單使用。"""
        pid = cls._get_current_project_id()
        usecases = await UsecaseController.list(project_id=pid)

        rows: List[Dict[str, Any]] = []
        for uc in usecases:
            rows.append(
                {
                    "id": getattr(uc, "id", None),
                    "name": getattr(uc, "name", "") or "",
                    "description": getattr(uc, "description", "") or "",
                }
            )
        return rows

    # 舊名稱相容
    @classmethod
    async def list_usecases(cls) -> List[Dict[str, Any]]:
        return await cls.list_usecases_for_current_project()

    # ============================================================
    # 2. 讀取某 UseCase 的事件（正常 / 例外）
    # ============================================================
    @classmethod
    async def load_events_by_usecase(cls, usecase_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """回傳指定 UseCase 的三段式事件列表。

        回傳格式：
        {
            "正常程序": [ { id, sequence_no, type, description }, ... ],
            "例外程序": [ { ... }, ... ]
        }
        """
        event_lists = await EventListController.list_by_usecase(usecase_id=usecase_id)

        result: Dict[str, List[Dict[str, Any]]] = {
            "正常程序": [],
            "例外程序": [],
        }

        for el in event_lists:
            events = await EventController.list_by_event_list(event_list_id=el.id)

            rows: List[Dict[str, Any]] = []
            for ev in events:
                rows.append(
                    {
                        "id": getattr(ev, "id", None),
                        "sequence_no": getattr(ev, "sequence_no", 0),
                        "type": getattr(ev, "type", "") or "",  # Request / Process / Response
                        "description": getattr(ev, "description", "") or "",
                    }
                )

            list_type = getattr(el, "type", "") or ""  # 欄位名稱是 type
            if list_type == "正常程序":
                result["正常程序"].extend(rows)
            elif list_type == "例外程序":
                result["例外程序"].extend(rows)

        # 排序（照 sequence_no）
        result["正常程序"].sort(key=lambda x: x.get("sequence_no", 0))
        result["例外程序"].sort(key=lambda x: x.get("sequence_no", 0))

        return result

    # 舊名稱相容
    @classmethod
    async def load_events(cls, usecase_id: int) -> Dict[str, List[Dict[str, Any]]]:
        return await cls.load_events_by_usecase(usecase_id)

    # ============================================================
    # 4. 一鍵產生目前專案全部 UseCase 的事件列表（View 需要這個名稱）
    # ============================================================
    @classmethod
    async def generate_for_current_project(cls) -> Dict[str, Any]:
        """
        給 View 呼叫用：一鍵產生目前專案全部 UseCase 的三段式事件列表。

        注意：你原本的入口叫 for_current_project()，
        但 view 端呼叫 generate_for_current_project()，因此這裡補齊並統一走同一條邏輯。
        """
        try:
            pid = cls._get_current_project_id()
        except RuntimeError as e:
            return {"ok": False, "reason": str(e)}

        # Agent 端負責：讀取 usecases → 產生 event_lists/events → 寫入 DB（或透過 controllers）
        result = await EventSummaryAgent.generate_for_current_project()

        if not result or not isinstance(result, dict) or not result.get("ok", False):
            if isinstance(result, dict) and "reason" in result:
                return {"ok": False, "reason": result.get("reason")}
            return {"ok": False, "reason": "ai_failed"}

        # 預期 Agent 會回傳包含統計資訊的字典
        return {
            "ok": True,
            "project_id": result.get("project_id", pid),
            "usecase_count": result.get("usecase_count", 0),
            "event_list_count": result.get("event_list_count", 0),
            "event_count": result.get("event_count", 0),
        }

    # ============================================================
    # 舊入口：保留，但改成呼叫新的 generate_for_current_project()
    # ============================================================
    @classmethod
    async def for_current_project(cls) -> Dict[str, Any]:
        """舊入口相容（請改用 generate_for_current_project）。"""
        return await cls.generate_for_current_project()

    # 舊名稱相容：generate_all / generate_all_for_current_project
    @classmethod
    async def generate_all(cls) -> Dict[str, Any]:
        return await cls.generate_for_current_project()

    @classmethod
    async def generate_all_for_current_project(cls) -> Dict[str, Any]:
        return await cls.generate_for_current_project()