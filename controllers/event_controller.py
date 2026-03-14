from __future__ import annotations
from typing import List
from sqlalchemy import select

from controllers.base_controller import BaseController
from init_db import get_async_session_context
from models.event import Event


class EventController(BaseController):
    model = Event

    # ------------------------------------------------------------
    # 新增一個事件（sequence_no + type + description + event_list_id）
    # ------------------------------------------------------------
    @classmethod
    async def add_event(cls, sequence_no: int, type: str, description: str, event_list_id: int):
        async with get_async_session_context() as session:
            obj = Event(
                sequence_no=sequence_no,
                type=type,
                description=description,
                event_list_id=event_list_id,
            )
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    # ------------------------------------------------------------
    # 取得某 EventList 底下的所有事件
    # ------------------------------------------------------------
    @classmethod
    async def list_by_event_list(cls, event_list_id: int) -> List[Event]:
        async with get_async_session_context() as session:
            stmt = select(Event).where(Event.event_list_id == event_list_id).order_by(Event.sequence_no)
            result = await session.execute(stmt)
            return list(result.scalars().all())
