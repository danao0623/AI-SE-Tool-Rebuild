from models.user_account import UserAccount
from controllers.base import BaseController
from sqlalchemy.exc import IntegrityError

class UserAccountController(BaseController):
    model = UserAccount  # 指定使用的 model

    @staticmethod
    async def add_user(account: str, password: str):
        """新增使用者（有檢查帳號重複）"""
        # 先查是否存在
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
