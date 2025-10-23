import asyncio
from init_db import create_db_and_tables, get_async_session_context
from controllers.user_account import UserAccountController
from controllers.project import ProjectController

async def main():
    # ✅ 確保資料表存在
    await create_db_and_tables()

    # 1️⃣ 新增一個使用者
    user = await UserAccountController.add(account="willy", password="123456")

    # 2️⃣ 新增一個專案，屬於上面那個使用者
    project = await ProjectController.add(
        name="AI Tool",
        description="AI 輔助軟體工程工具",
        frontend_language="Python",
        backend_language="Python",
        user_id=user.id
    )

    print(f"\n🧑‍💻 新增的使用者：{user}")
    print(f"📁 新增的專案：{project}")
    print(f"✅ 專案的 user_id：{project.user_id}\n")

    await UserAccountController.list()
    # 3️⃣ 顯示目前資料庫中所有專案
    await ProjectController.list()

if __name__ == "__main__":
    asyncio.run(main())
