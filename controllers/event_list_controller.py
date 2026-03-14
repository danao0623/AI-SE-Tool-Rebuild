from __future__ import annotations
from typing import List, Optional
from sqlalchemy import select

from controllers.base_controller import BaseController
from init_db import get_async_session_context
from models.event_list import EventList


class EventListController(BaseController):
    model = EventList

    # ------------------------------------------------------------
    # 新增事件列表（正常程序 / 例外程序）
    # ------------------------------------------------------------
    @classmethod
    async def add_event_list(cls, list_type: str, use_case_id: int):
        async with get_async_session_context() as session:
            obj = EventList(
                type=list_type,
                use_case_id=use_case_id,
            )
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    # ------------------------------------------------------------
    # 依 UseCase 取得底下所有 EventList
    # ------------------------------------------------------------
    @classmethod
    async def list_by_usecase(cls, usecase_id: Optional[int] = None, use_case_id: Optional[int] = None) -> List[EventList]:
        if use_case_id is None:
            use_case_id = usecase_id
        
        async with get_async_session_context() as session:
            stmt = select(EventList).where(EventList.use_case_id == use_case_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())
