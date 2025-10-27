from nicegui import app
from controllers.user_account_controller import UserAccountController

class LoginFlowController:

    @staticmethod
    async def handle_login(account: str, password: str):
        """登入流程（負責驗證與寫入 session）"""
        if not account or not password:
            return {'status': 'warning', 'message': '請輸入帳號與密碼'}

        user = await UserAccountController.get_single(account=account)
        if user is None:
            return {'status': 'error', 'message': '查無此帳號'}
        elif user.password != password:
            return {'status': 'error', 'message': '密碼錯誤'}
        else:
            # ✅ 將登入資訊寫入 NiceGUI session
            app.storage.user['current_user_account'] = account
            print(f"✅ 使用者登入成功：{account}")
            print(f"📦 目前 session 狀態：{app.storage.user}")

            return {'status': 'success', 'message': f'歡迎回來，{account}'}

    @staticmethod
    async def handle_register(account: str, password: str):
        """註冊流程"""
        if not account or not password:
            return {'status': 'warning', 'message': '帳號或密碼不得為空'}

        success = await UserAccountController.add_user(account, password)
        if success:
            return {'status': 'success', 'message': '註冊成功！即將返回登入頁...'}
        else:
            return {'status': 'warning', 'message': '帳號已存在，請重新輸入'}