# controllers/code_controller.py
from __future__ import annotations

from typing import Optional, List

from sqlalchemy import update, desc
from sqlalchemy.future import select

from controllers.base_controller import BaseController  # 依你的實際路徑調整
from init_db import get_async_session_context

from models.code import CodeSnapshot  # 依你的實際路徑調整


class CodeController(BaseController):
    """
    CodeSnapshot 的資料儲存 Controller
    - create_snapshot(): 新增一筆程式碼快照，並維護 is_latest 唯一性
    - get_latest_by_project(): 取某專案最新快照
    - list_by_project(): 列出某專案所有快照（新到舊）
    - set_latest(): 指定某筆快照為最新（其餘設為非最新）
    - delete_by_project(): 刪除某專案所有快照
    """
    model = CodeSnapshot

    @classmethod
    async def create_snapshot(
        cls,
        project_id: int,
        files_json: str,
        package_name: str = "generated_app",
        mode: str = "cover",
    ) -> CodeSnapshot:
        """
        建立新的 code snapshot 並設為最新。
        會先把同 project 的 is_latest 全部清成 False，避免多筆 latest。
        """
        async with get_async_session_context() as session:
            # 1) 清掉舊的 latest
            await session.execute(
                update(cls.model)
                .where(cls.model.project_id == project_id)
                .where(cls.model.is_latest == True)  # noqa: E712
                .values(is_latest=False)
            )

            # 2) 新增最新 snapshot
            obj = cls.model(
                project_id=project_id,
                package_name=package_name,
                mode=mode,
                is_latest=True,
                files_json=files_json,
            )
            session.add(obj)
            await session.commit()
            await session.refresh(obj)

            print(f"[CODE] ✅ Created snapshot (latest): id={obj.id}, project_id={project_id}")
            return obj

    @classmethod
    async def get_latest_by_project(cls, project_id: int) -> Optional[CodeSnapshot]:
        """
        取得某專案最新快照（優先 is_latest=True；若資料髒掉，fallback 取 created_at 最新）
        """
        async with get_async_session_context() as session:
            # 1) 正常情況：直接抓 is_latest=True
            q1 = (
                select(cls.model)
                .where(cls.model.project_id == project_id)
                .where(cls.model.is_latest == True)  # noqa: E712
                .limit(1)
            )
            r1 = await session.execute(q1)
            obj = r1.scalars().first()
            if obj:
                return obj

            # 2) fallback：沒有 latest 標記就抓 created_at 最新
            q2 = (
                select(cls.model)
                .where(cls.model.project_id == project_id)
                .order_by(desc(cls.model.created_at))
                .limit(1)
            )
            r2 = await session.execute(q2)
            return r2.scalars().first()

    @classmethod
    async def list_by_project(cls, project_id: int) -> List[CodeSnapshot]:
        """列出某專案所有快照（新到舊）"""
        async with get_async_session_context() as session:
            q = (
                select(cls.model)
                .where(cls.model.project_id == project_id)
                .order_by(desc(cls.model.created_at))
            )
            r = await session.execute(q)
            return r.scalars().all()

    @classmethod
    async def set_latest(cls, snapshot_id: int) -> Optional[CodeSnapshot]:
        """
        指定某筆 snapshot 為最新：
        - 先找 snapshot 拿 project_id
        - 將同 project 其他 latest 清掉
        - 將該筆設為 latest
        """
        async with get_async_session_context() as session:
            obj = await session.get(cls.model, snapshot_id)
            if not obj:
                print("[CODE] ❌ set_latest failed: snapshot not found")
                return None

            pid = obj.project_id

            # 清掉舊 latest
            await session.execute(
                update(cls.model)
                .where(cls.model.project_id == pid)
                .where(cls.model.is_latest == True)  # noqa: E712
                .values(is_latest=False)
            )

            # 設定新 latest
            obj.is_latest = True
            await session.commit()
            await session.refresh(obj)
            print(f"[CODE] ✅ set_latest: snapshot_id={snapshot_id} as latest (project_id={pid})")
            return obj

    @classmethod
    async def delete_by_project(cls, project_id: int) -> int:
        """
        刪除某專案全部快照
        回傳刪除筆數
        """
        async with get_async_session_context() as session:
            q = select(cls.model).where(cls.model.project_id == project_id)
            r = await session.execute(q)
            items = r.scalars().all()

            count = 0
            for obj in items:
                await session.delete(obj)
                count += 1

            await session.commit()
            print(f"[CODE] 🗑 deleted snapshots: project_id={project_id}, count={count}")
            return count
