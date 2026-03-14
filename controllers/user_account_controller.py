from models.user_account import UserAccount
from controllers.base_controller import BaseController
from sqlalchemy.exc import IntegrityError


class UserAccountController(BaseController):
    model = UserAccount  # 指定使用的 model

    # ----------------------------
    # 🔹 新增使用者
    # ----------------------------
    @staticmethod
    async def add_user(account: str, password: str):
        """新增使用者（有檢查帳號重複）"""
        existing = await UserAccountController.get_single(account=account)
        if existing:
            print("⚠️ 帳號已存在，跳過新增")
            return False

        try:
            await UserAccountController.add(account=account, password=password)
            return True
        except IntegrityError:
            print("⚠️ UNIQUE constraint failed, 新增失敗")
            return False

    # ----------------------------
    # 🔹 ✅ 補上 Flow 需要的方法
    # ----------------------------
    @staticmethod
    async def get_by_account(account: str):
        """依 account 取得使用者（給 Flow 用）"""
        if not account:
            return None
        return await UserAccountController.get_single(account=account)

    # 🔹 保險：有些地方可能叫 username
    @staticmethod
    async def get_by_username(username: str):
        return await UserAccountController.get_by_account(username)