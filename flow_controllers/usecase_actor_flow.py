from __future__ import annotations
from typing import List, Dict, Any

from nicegui import app

# from agents.usecase_actor_agent import UseCaseActorAgent
from agents.usecase_actor_agent_openai import UseCaseActorAgent
from controllers.actor_controller import ActorController
from controllers.usecase_controller import UsecaseController
from controllers.usecase_actor_controller import UsecaseActorController


class UsecaseActorFlowController:
    """
    Flow 層：
    - 從 app.storage.user 取得目前專案
    - 串接 DB Controller / AI Agent
    - 轉成畫面用的中文欄位資料
    """

    # ------------------------------------------------------------
    # 共用小工具
    # ------------------------------------------------------------
    @staticmethod
    def _get_current_project() -> Dict[str, Any]:
        """從 user storage 取得目前專案，失敗時丟 RuntimeError 給上層吃。"""
        project = app.storage.user.get("current_project")
        if not project:
            raise RuntimeError("no_project")

        pid = project.get("id")
        if not pid:
            raise RuntimeError("no_project_id")

        return project

    @staticmethod
    def _guess_primary_actor(name: str) -> str:
        """
        從 Use Case 名稱粗略猜測主要 Actor（給舊資料或查無關聯時用）
        目前內容偏向舊的選股系統，只是為了兼容舊資料，不會影響新專案。
        """
        if not name:
            return ""

        # 系統管理員相關
        if any(k in name for k in ["帳戶", "備份", "恢復", "系統性能", "日誌", "權限"]):
            return "系統管理員"

        # 個人投資者相關
        if any(k in name for k in ["選股推薦", "市場分析報告", "投資組合建議", "預測模型報告", "AI選股"]):
            return "個人投資者"

        # 財務顧問相關
        if any(k in name for k in ["客製化投資方案", "客戶", "投資組合績效", "理財規劃"]):
            return "財務顧問"

        # AI 模型訓練師相關
        if any(k in name for k in ["訓練", "AI選股模型", "模型性能", "數據源", "特徵工程", "調參"]):
            return "AI模型訓練師"

        # 市場研究員相關
        if any(k in name for k in ["進階市場研究", "趨勢分析", "市場數據", "數據查詢", "研究報告"]):
            return "市場研究員"

        # 如果都沒有命中，就暫時不指定主要角色
        return ""

    # ------------------------------------------------------------
    # 0. 專案級清除（給「刪專案」或「專案核心變更」呼叫）
    # ------------------------------------------------------------
    @classmethod
    async def purge_all_for_project(cls, project_id: int) -> None:
        """清除某專案底下所有與 Use Case / Actor 有關的內容。"""
        # 先刪 UseCase（會透過 relationship cascade 刪掉事件列表、圖等）
        old_usecases = await UsecaseController.list(project_id=project_id)
        for u in old_usecases:
            await UsecaseController.delete(u.id)

        # 再刪 Actor
        old_actors = await ActorController.list(project_id=project_id)
        for a in old_actors:
            await ActorController.delete(a.id)

    # ------------------------------------------------------------
    # 1. 從 DB 載入目前專案的 Actors / UseCases
    # ------------------------------------------------------------
    @classmethod
    async def load_from_db_for_current_project(cls) -> Dict[str, Any]:
        try:
            project = cls._get_current_project()
        except RuntimeError as e:
            # 回傳給 View，讓 View 根據 reason 顯示提示
            return {"ok": False, "reason": str(e)}

        pid = project["id"]

        # Actor：只抓「目前專案」的角色
        actors = await ActorController.list(project_id=pid)

        # UseCase：綁定目前專案
        usecases = await UsecaseController.list(project_id=pid)

        # 上面 Actor Grid 用的資料
        actors_rows = [
            {
                "名稱": getattr(a, "name", "") or "",
                "說明": getattr(a, "description", "") or "",
            }
            for a in actors
        ]

        # 下面 Use Case Grid 用的資料
        usecases_rows: List[Dict[str, Any]] = []
        for u in usecases:
            name = getattr(u, "name", "") or ""
            summary = (
                getattr(u, "summary", None)
                or getattr(u, "description", "")  # 舊欄位相容
                or ""
            )

            # 先嘗試從關聯的 UsecaseActor 取得第一個 Actor 當主要角色
            primary_actor = ""
            try:
                links = getattr(u, "usecase_actor", None)
                if links:
                    first_actor = getattr(links[0], "actor", None)
                    if first_actor and getattr(first_actor, "name", None):
                        primary_actor = first_actor.name
            except Exception:
                primary_actor = ""

            # 如果關聯表拿不到，就用名稱猜（舊資料兼容）
            if not primary_actor:
                primary_actor = cls._guess_primary_actor(name)

            usecases_rows.append(
                {
                    "使用案例名稱": name,
                    "概述": summary,
                    "主要角色": primary_actor,
                }
            )

        return {
            "ok": True,
            "actors_rows": actors_rows,
            "usecases_rows": usecases_rows,
        }

    # ------------------------------------------------------------
    # 2. AI 一次產生 Actor + UseCase（只在記憶體，不直接寫 DB）
    # ------------------------------------------------------------
    @classmethod
    async def generate_actors_and_usecases_for_current_project(
        cls,
    ) -> Dict[str, Any]:
        try:
            project = cls._get_current_project()
        except RuntimeError as e:
            return {"ok": False, "reason": str(e)}

        result = await UseCaseActorAgent.generate_actors_and_usecases(project)
        if not result:
            return {"ok": False, "reason": "empty_response"}

        actors = result.get("actors") or []
        usecases = result.get("use_cases") or []

        actors_rows = [
            {
                "名稱": (a.get("name") or "").strip(),
                "說明": (a.get("description") or "").strip(),
            }
            for a in actors
        ]
        usecases_rows = [
            {
                "使用案例名稱": (u.get("name") or "").strip(),
                "概述": (u.get("summary") or "").strip(),
                "主要角色": (u.get("primary_actor") or "").strip(),
            }
            for u in usecases
        ]

        return {
            "ok": True,
            "actors_rows": actors_rows,
            "usecases_rows": usecases_rows,
        }

    # 舊名稱相容：View 目前呼叫的是 generate_for_current_project
    @classmethod
    async def generate_for_current_project(cls) -> Dict[str, Any]:
        return await cls.generate_actors_and_usecases_for_current_project()

    # ------------------------------------------------------------
    # 3. 重新生成單一 UseCase（不碰 DB，只回傳一列 row）
    # ------------------------------------------------------------
    @classmethod
    async def regenerate_usecase_for_current_project(
        cls,
        actor_name: str,
        old_usecase: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            project = cls._get_current_project()
        except RuntimeError as e:
            return {"ok": False, "reason": str(e)}

        payload = {
            "name": old_usecase.get("name") or old_usecase.get("使用案例名稱", ""),
            "summary": old_usecase.get("summary") or old_usecase.get("概述", ""),
            "primary_actor": actor_name,
        }

        new_uc = await UseCaseActorAgent.regenerate_single_usecase(
            project, actor_name, payload
        )
        if not new_uc:
            return {"ok": False, "reason": "empty_response"}

        row = {
            "使用案例名稱": (new_uc.get("name") or "").strip(),
            "概述": (new_uc.get("summary") or "").strip(),
            "主要角色": (new_uc.get("primary_actor") or actor_name).strip(),
        }
        return {"ok": True, "row": row}

    # ------------------------------------------------------------
    # 3.5 重生 Actor + 該 Actor 的 UseCases（不碰 DB，只改畫面 State）
    # ------------------------------------------------------------
    @classmethod
    async def regenerate_actor_and_usecases_for_current_project(
        cls,
        old_actor_row: Dict[str, Any],
        old_usecases_for_actor: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        old_actor_row: 例如 {"名稱": "...", "說明": "..."}
        old_usecases_for_actor: 只放這個 Actor 對應的 UseCase
            [{"使用案例名稱": "...", "概述": "...", "主要角色": "..."}]
        """
        try:
            project = cls._get_current_project()
        except RuntimeError as e:
            return {"ok": False, "reason": str(e)}

        # 組成 Agent 需要的輸入格式
        old_actor_payload = {
            "name": old_actor_row.get("名稱", ""),
            "description": old_actor_row.get("說明", ""),
        }
        old_uc_payloads = [
            {
                "name": u.get("使用案例名稱", ""),
                "summary": u.get("概述", ""),
            }
            for u in old_usecases_for_actor
        ]

        result = await UseCaseActorAgent.regenerate_actor_with_usecases(
            project_info=project,
            old_actor=old_actor_payload,
            old_usecases_for_actor=old_uc_payloads,
        )
        if not result:
            return {"ok": False, "reason": "empty_response"}

        new_actor = result.get("actor") or {}
        new_usecases = result.get("use_cases") or []

        # 轉成 View 需要的 row 格式
        new_actor_row = {
            "名稱": (new_actor.get("name") or "").strip(),
            "說明": (new_actor.get("description") or "").strip(),
        }
        new_usecase_rows = [
            {
                "使用案例名稱": (u.get("name") or "").strip(),
                "概述": (u.get("summary") or "").strip(),
                "主要角色": (u.get("primary_actor") or new_actor_row["名稱"]).strip(),
            }
            for u in new_usecases
        ]

        return {
            "ok": True,
            "actor_row": new_actor_row,
            "usecases_rows": new_usecase_rows,
        }

    # ------------------------------------------------------------
    # 4. 將目前表格內容寫回 DB（會清掉「目前專案」舊資料再重寫）
    #    ✅ 同時寫入 usecase_actors 關聯表，讓之後可以依 Actor 分類 UseCase
    # ------------------------------------------------------------
    @classmethod
    async def save_current_to_db(
        cls,
        actors_rows: List[Dict[str, Any]],
        usecases_rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        try:
            project = cls._get_current_project()
        except RuntimeError as e:
            return {"ok": False, "reason": str(e)}

        pid = project["id"]

        # 1) 清除目前專案所有舊資料（UseCase + Actor + 其關聯/圖），避免舊資料殘留
        await cls.purge_all_for_project(pid)

        # 2) 寫入新資料
        actor_count = 0
        usecase_count = 0
        link_count = 0

        # 2-1) 新增 Actors，並用「名稱」建立對照表
        actor_by_name: Dict[str, Any] = {}
        for row in actors_rows:
            actor = await ActorController.add(
                name=row.get("名稱", "") or "",
                description=row.get("說明", "") or "",
                project_id=pid,
            )
            if actor is not None and getattr(actor, "name", None):
                actor_by_name[actor.name] = actor
                actor_count += 1

        # 2-2) 新增 UseCases，並用名稱建立對照表
        usecase_by_name: Dict[str, Any] = {}
        for row in usecases_rows:
            uc = await UsecaseController.add(
                name=row.get("使用案例名稱", "") or "",
                description=row.get("概述", "") or "",
                project_id=pid,
            )
            if uc is not None and getattr(uc, "name", None):
                usecase_by_name[uc.name] = uc
                usecase_count += 1

        # 2-3) 建立 usecase_actors 關聯
        for row in usecases_rows:
            uc_name = (row.get("使用案例名稱") or "").strip()
            actor_name = (row.get("主要角色") or "").strip()

            if not uc_name or not actor_name:
                continue

            uc = usecase_by_name.get(uc_name)
            actor = actor_by_name.get(actor_name)
            if not uc or not actor:
                continue

            await UsecaseActorController.add(
                use_case_id=getattr(uc, "id"),
                actor_id=getattr(actor, "id"),
            )
            link_count += 1

        return {
            "ok": True,
            "actor_count": actor_count,
            "usecase_count": usecase_count,
            "link_count": link_count,
        }