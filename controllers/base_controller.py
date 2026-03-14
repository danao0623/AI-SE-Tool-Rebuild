from init_db import get_async_session_context
from sqlalchemy.orm import class_mapper
                           #class_mapper = 取得某個 model 的 mapper（映射器）
from sqlalchemy.future import select

# ✅ BaseController 是所有 Controller 的「共用模板」
class BaseController:
    model = None  # 子類別要指定這裡是哪一個 model（例如 Stock, Project）

    @classmethod
    async def add(cls, **kwargs):
        async with get_async_session_context() as session:
            obj = cls.model(**kwargs)
            
            # 🟢 若 model 有 relationship 欄位，檢查是否有傳入關聯物件
            mapper = class_mapper(cls.model)
            for rel in mapper.relationships:
                if rel.key in kwargs and kwargs[rel.key] is not None:
                    related_obj = kwargs[rel.key]
                    setattr(obj, rel.key, related_obj)

            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            print(f"Added: {obj}")
            return obj
    
    # 🗑 刪除資料
    @classmethod
    async def delete(cls, obj_id: int):
        async with get_async_session_context() as session:
            obj = await session.get(cls.model, obj_id)
            if not obj:
                print("❌ 沒有這筆資料")
                return False
            await session.delete(obj)
            await session.commit()
            print(f"🗑成功刪除: {obj}這筆資料")
            return True
        
    
    # ✏️ 更新資料
    @classmethod
    async def update(cls, obj_id: int, **kwargs):
        async with get_async_session_context() as session:
            obj = await session.get(cls.model, obj_id)
            if not obj:
                print("❌ 找不到這筆資料")
                return None

            for key, value in kwargs.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)

            await session.commit()
            await session.refresh(obj)
            print(f"✏️ 已更新: {obj}")
            return obj
        
    # 📋 列出資料
    @classmethod
    async def list(cls, **filters):
        """
        若沒傳入參數 → 列出所有資料
        若傳入條件（如 name='AI Tool'） → 根據條件過濾
        """
        async with get_async_session_context() as session:
            query = select(cls.model)
            if filters:
                for key, value in filters.items():
                    column = getattr(cls.model, key)
                    query = query.where(column == value)

            result = await session.execute(query)
            records = result.scalars().all()

            print(f"📋 查詢結果 ({len(records)} 筆): {records}")
            return records
        
    # 📍 依 primary key 取得單筆資料（最常用）
    @classmethod
    async def get(cls, obj_id: int):
        async with get_async_session_context() as session:
            obj = await session.get(cls.model, obj_id)
            print(f"🔍 依 ID 查詢結果: {obj}")
            return obj
        
    # 📍 查詢單筆資料（例如根據帳號、ID）
    @classmethod
    async def get_single(cls, **filters):
        """
        根據傳入條件（如 account='willy'）回傳第一筆匹配的資料。
        若無結果則回傳 None。
        """
        async with get_async_session_context() as session:
            query = select(cls.model)
            for key, value in filters.items():
                column = getattr(cls.model, key)
                query = query.where(column == value)

            result = await session.execute(query)
            obj = result.scalars().first()
            print(f"🔍 單筆查詢結果: {obj}")
            return obj
    