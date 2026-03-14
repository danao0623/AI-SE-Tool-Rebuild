import asyncio
from init_db import engine, Base, create_db_and_tables

from models.user_account import UserAccount
from models.project import Project
from models.usecase import Usecase
from models.usecase_actor import UsecaseActor
from models.actor import Actor
from models.event_list import EventList
from models.event import Event
from models.sequence_diagram import SequenceDiagram
from models.sequence_object import SequenceObject
from models.entity_relationship_diagram import EntityRelationshipDiagram
from models.entity_relationship_object import EntityRelationshipObject
from models.class_diagram import ClassDiagram
from models.class_object import ClassObject
from models.method import Method
from models.attribute import Attribute
from models.project_file import ProjectFile
from models.blueprint_state import BlueprintState
from models.code import CodeSnapshot

async def main():
    print("🧹 清空資料庫中所有表...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)   # ❌ 刪除所有表
        await conn.run_sync(Base.metadata.create_all) # ✅ 重新建立所有表
    print("✅ SQLite 資料庫重建完成！")

asyncio.run(main())