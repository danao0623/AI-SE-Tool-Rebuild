# init_db.py
import contextlib
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeMeta, declarative_base
from typing import AsyncGenerator

# -------------------------------------------------------
# 建立 Base
# -------------------------------------------------------
Base: DeclarativeMeta = declarative_base()

# -------------------------------------------------------
# ★★★ 這裡要 import 所有 models（非常重要）★★★
# -------------------------------------------------------
# 只要 import models 套件，就會一次 import 全部 model 檔案
import models  # <--- 必須存在，否則 SQLAlchemy 找不到 SequenceObject 等類別


# -------------------------------------------------------
# 資料庫設定
# -------------------------------------------------------
DATABASE_URL = "sqlite+aiosqlite:///SQL/base.db"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


# -------------------------------------------------------
# 建立資料庫表格
# -------------------------------------------------------
async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# -------------------------------------------------------
# 取得 Async Session（FastAPI / Flow Controller 使用）
# -------------------------------------------------------
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


get_async_session_context = contextlib.asynccontextmanager(get_async_session)