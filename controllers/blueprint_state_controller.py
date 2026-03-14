# controllers/blueprint_state_controller.py
from __future__ import annotations

from typing import Optional, List

from controllers.base_controller import BaseController
from models import BlueprintState


class BlueprintStateController(BaseController):
    """
    ✅ 單表模式（推薦）
    - 一個 (project_id, boundary_id) 只保留最新一筆
    - payload_json: TEXT/CLOB（整包 JSON）
    - canvas_jpg: BLOB（JPG bytes，給 code_agent 畫面參照）
    """
    model = BlueprintState

    # ----------------------------
    # ✅ New API (single-row per screen)
    # ----------------------------
    @classmethod
    async def get_current(cls, project_id: int, boundary_id: int) -> Optional[BlueprintState]:
        """
        取得當前最新狀態（單筆）
        """
        return await cls.get_single(project_id=int(project_id), boundary_id=int(boundary_id))

    @classmethod
    async def upsert_current(
        cls,
        project_id: int,
        boundary_id: int,
        *,
        screen_name: str = "",
        payload_json: str = "{}",
        canvas_jpg: bytes | None = None,
    ) -> BlueprintState:
        """
        ✅ Upsert：同一畫面只保留最新一筆
        - 存在：update 該筆
        - 不存在：add 新筆
        """
        project_id = int(project_id)
        boundary_id = int(boundary_id)

        row = await cls.get_current(project_id, boundary_id)
        data = {
            "screen_name": screen_name or "",
            "payload_json": payload_json if payload_json is not None else "{}",
        }
        # canvas_jpg 允許「不傳就不更新」
        if canvas_jpg is not None:
            data["canvas_jpg"] = canvas_jpg

        if row:
            # ✅ 用 BaseController.update
            updated = await cls.update(row.id, **data)
            if updated is None:
                # 理論上不會發生，但保底
                raise RuntimeError("BlueprintState upsert update 失敗：找不到欲更新的資料。")
            return updated

        # ✅ 用 BaseController.add
        return await cls.add(
            project_id=project_id,
            boundary_id=boundary_id,
            **data,
        )

    # ----------------------------
    # ✅ List API (for agents / admin pages)
    # ----------------------------
    @classmethod
    async def list(
        cls,
        project_id: int | None = None,
        boundary_id: int | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> List[BlueprintState]:
        """
        ✅ 列出 BlueprintState（給 code_agent 收集上下文用）

        - 單筆 upsert 模式下：
          同一個 (project_id, boundary_id) 理論上最多就一筆
        - 但 agent 需要能列出「某專案下所有畫面」的 blueprint_state，
          所以提供 list() 讓它可以一次抓到全部畫面狀態。

        參數：
        - project_id: 只列該專案
        - boundary_id: 只列該畫面
        - limit/offset: 分頁（如果 BaseController 支援）
        """
        filters = {}
        if project_id is not None:
            filters["project_id"] = int(project_id)
        if boundary_id is not None:
            filters["boundary_id"] = int(boundary_id)

        # ✅ 盡量沿用 BaseController 的 list（你其他 controller 通常也靠它）
        base_list = getattr(super(BlueprintStateController, cls), "list", None)
        if callable(base_list):
            # BaseController.list 若不支援 limit/offset，傳了也不會用；保守做法：有值才帶
            if limit is not None:
                filters["limit"] = int(limit)
            if offset is not None:
                filters["offset"] = int(offset)
            rows = await base_list(**filters)
            return list(rows or [])

        # 若你的 BaseController 沒有 list（理論上不太可能），就明確報錯，避免 agent 默默拿到空資料。
        raise AttributeError("BaseController 缺少 list()，BlueprintStateController.list 無法運作。")

    # ----------------------------
    # 🔁 Backward compatibility (old calls)
    # ----------------------------
    @classmethod
    async def get_latest(cls, project_id: int, boundary_id: int) -> Optional[BlueprintState]:
        """
        舊版相容：等同 get_current
        """
        return await cls.get_current(project_id, boundary_id)

    @classmethod
    async def add_new_version(cls, *args, **kwargs):
        """
        舊版版本制停用：避免你以為有存，其實又長版本
        """
        raise RuntimeError(
            "BlueprintState 已改為『單筆 upsert（不使用 version/history）』，"
            "請改呼叫 BlueprintStateController.upsert_current()."
        )

    @classmethod
    async def list_history(cls, *args, **kwargs):
        raise RuntimeError("BlueprintState 已改為單筆 upsert（不提供 history）。")

    @classmethod
    async def get_by_version(cls, *args, **kwargs):
        raise RuntimeError("BlueprintState 已改為單筆 upsert（不使用 version）。")

    @classmethod
    async def get_latest_version(cls, *args, **kwargs) -> int:
        # 舊版相容：單筆模式下永遠可視為 1
        return 1