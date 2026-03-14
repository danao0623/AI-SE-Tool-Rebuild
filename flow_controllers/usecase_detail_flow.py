from __future__ import annotations
from typing import Any, Dict, List, Optional

from nicegui import app

from controllers.usecase_controller import UsecaseController
from agents.usecase_detail_agent_openai import UseCaseDetailAgent


class UsecaseDetailFlowController:
    """
    Use Case Detail 的 Flow 層

    負責：
    - 讀取目前專案底下的 UseCase 清單
    - 讀取 / 儲存單一 UseCase 的 Detail 欄位
    - 呼叫 UseCaseDetailAgent，為全部或單一 UseCase 產生 Detail
    """

    # ============================================================
    # 共用小工具
    # ============================================================
    @staticmethod
    def _get_current_project_id() -> int:
        project = app.storage.user.get("current_project")
        if not project:
            raise RuntimeError("no_project")

        pid = project.get("id")
        if not pid:
            raise RuntimeError("no_project_id")

        return int(pid)

    @staticmethod
    def _extract_primary_actor_from_usecase(uc: Any) -> str:
        """
        嘗試從關聯的 UsecaseActor 中抓第一個 Actor 當主要角色。
        若失敗則回傳空字串。
        """
        try:
            links = getattr(uc, "usecase_actor", None)
            if links:
                first_link = links[0]
                actor_obj = getattr(first_link, "actor", None)
                if actor_obj and getattr(actor_obj, "name", None):
                    return actor_obj.name
        except Exception:
            pass
        return ""

    # ============================================================
    # 1. 給畫面用的 UseCase 清單
    # ============================================================
    @classmethod
    async def list_usecases_for_current_project(cls) -> List[Dict[str, Any]]:
        """
        回傳目前專案底下所有 UseCase 的基本資訊。

        回傳格式：
        [
            {
                "id": 1,
                "name": "瀏覽課程列表",
                "description": "...",
                "has_normal": True/False,
                "has_exception": True/False,
                "has_trigger": True/False,
                "has_pre": True/False,
                "has_post": True/False,
            },
            ...
        ]
        """
        pid = cls._get_current_project_id()
        usecases: List[Any] = await UsecaseController.list(project_id=pid)

        rows: List[Dict[str, Any]] = []
        for uc in usecases:
            rows.append(
                {
                    "id": getattr(uc, "id", None),
                    "name": getattr(uc, "name", "") or "",
                    "description": getattr(uc, "description", "") or "",
                    "has_normal": bool(getattr(uc, "normal_process", None)),
                    "has_exception": bool(getattr(uc, "exception_process", None)),
                    "has_trigger": bool(getattr(uc, "trigger_condition", None)),
                    "has_pre": bool(getattr(uc, "pre_condition", None)),
                    "has_post": bool(getattr(uc, "post_condition", None)),
                }
            )
        return rows

    # ============================================================
    # 2. 讀取單一 UseCase Detail
    # ============================================================
    @classmethod
    async def load_detail(cls, usecase_id: int) -> Optional[Dict[str, str]]:
        """
        從資料庫讀取指定 UseCase 的 Detail 欄位。
        """
        uc = await UsecaseController.get_single(id=usecase_id)
        if not uc:
            return None

        return {
            "id": uc.id,
            "name": uc.name or "",
            "description": uc.description or "",
            "normal_process": uc.normal_process or "",
            "exception_process": uc.exception_process or "",
            "trigger_condition": uc.trigger_condition or "",
            "pre_condition": uc.pre_condition or "",
            "post_condition": uc.post_condition or "",
        }

    # ============================================================
    # 3. 儲存單一 UseCase Detail（使用者編輯後）
    # ============================================================
    @classmethod
    async def save_detail(
        cls,
        usecase_id: int,
        *,
        normal_process: str,
        exception_process: str,
        trigger_condition: str,
        pre_condition: str,
        post_condition: str,
    ) -> None:
        """
        把畫面上編輯後的 Detail 寫回資料庫。
        """
        await UsecaseController.update(
            obj_id=usecase_id,
            normal_process=normal_process,
            exception_process=exception_process,
            trigger_condition=trigger_condition,
            pre_condition=pre_condition,
            post_condition=post_condition,
        )

    # ============================================================
    # 4. 一鍵為「目前專案」全部 UseCase 產生 Detail（AI）
    # ============================================================
    @classmethod
    async def generate_for_current_project(cls) -> Dict[str, Any]:
        """
        針對目前專案底下所有 UseCase：
        - 撈出 UseCase 清單
        - 組成給 UseCaseDetailAgent 的輸入
        - 呼叫 AI 產生 Detail
        - 寫回資料庫
        """
        try:
            pid = cls._get_current_project_id()
        except RuntimeError as e:
            return {"ok": False, "reason": str(e)}

        usecase_objs: List[Any] = await UsecaseController.list(project_id=pid)
        if not usecase_objs:
            return {
                "ok": True,
                "usecase_count": 0,
                "updated_count": 0,
            }

        payloads: List[Dict[str, Any]] = []
        for uc in usecase_objs:
            uid = getattr(uc, "id", None)
            if uid is None:
                continue

            payloads.append(
                {
                    "id": uid,
                    "name": getattr(uc, "name", "") or "",
                    "description": getattr(uc, "description", "") or "",
                    "actor": cls._extract_primary_actor_from_usecase(uc),
                }
            )

        if not payloads:
            return {
                "ok": True,
                "usecase_count": len(usecase_objs),
                "updated_count": 0,
            }

        # 呼叫 Agent
        ai_results = await UseCaseDetailAgent.generate_details_for_usecases(payloads)

        updated_count = 0
        for item in ai_results or []:
            source = item.get("source") or {}
            detail = item.get("details") or {}
            uc_id = source.get("id")
            if not uc_id:
                continue

            await UsecaseController.update(
                obj_id=uc_id,
                normal_process=detail.get("正常程序", "") or "",
                exception_process=detail.get("例外程序", "") or "",
                trigger_condition=detail.get("觸發條件", "") or "",
                pre_condition=detail.get("前置條件", "") or "",
                post_condition=detail.get("後置條件", "") or "",
            )
            updated_count += 1

        return {
            "ok": True,
            "usecase_count": len(usecase_objs),
            "updated_count": updated_count,
        }

    # ============================================================
    # 5. 針對單一 UseCase 重新產生 Detail（預留）
    # ============================================================
    @classmethod
    async def generate_for_single_usecase(cls, usecase_id: int) -> Dict[str, Any]:
        """
        針對單一 UseCase 重新產生 Detail（AI）。
        目前 view 尚未用到，但預留給之後的「單筆重生」按鈕。
        """
        uc = await UsecaseController.get_single(id=usecase_id)
        if not uc:
            return {"ok": False, "reason": "usecase_not_found"}

        payload = {
            "id": uc.id,
            "name": uc.name or "",
            "description": uc.description or "",
            "actor": cls._extract_primary_actor_from_usecase(uc),
        }

        results = await UseCaseDetailAgent.generate_details_for_usecases([payload])
        if not results:
            return {"ok": False, "reason": "ai_failed"}

        detail = (results[0] or {}).get("details") or {}

        await UsecaseController.update(
            obj_id=uc.id,
            normal_process=detail.get("正常程序", "") or "",
            exception_process=detail.get("例外程序", "") or "",
            trigger_condition=detail.get("觸發條件", "") or "",
            pre_condition=detail.get("前置條件", "") or "",
            post_condition=detail.get("後置條件", "") or "",
        )

        return {"ok": True, "updated_usecase_id": uc.id}