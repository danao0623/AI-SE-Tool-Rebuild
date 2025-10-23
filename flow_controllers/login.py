# flow_controller/login.py
from nicegui import ui
from controllers.user_account import UserAccountController

class LoginFlowController:

    @staticmethod
    async def handle_login(account: str, password: str):
        """登入流程：比對帳號與密碼"""
        if not account or not password:
            ui.notify('請輸入帳號與密碼', color='warning')
            return

        user = await UserAccountController.get_user(account)

        if user is None:
            ui.notify('查無此帳號', color='negative')
        elif user.password != password:
            ui.notify('密碼錯誤', color='negative')
        else:
            ui.notify(f'歡迎回來，{account}', color='positive')
            ui.open('/project')  # 登入成功導向專案頁

    @staticmethod
    async def handle_register(account: str, password: str):
        """註冊流程：新增新使用者"""
        if not account or not password:
            ui.notify('帳號或密碼不得為空', color='warning')
            return

        success = await UserAccountController.add_user(account, password)
        if success:
            ui.notify('註冊成功！', color='positive')
        else:
            ui.notify('帳號已存在，請重新輸入', color='warning')
