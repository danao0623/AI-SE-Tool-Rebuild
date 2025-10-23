# views/login_view.py
from nicegui import ui
from controllers.user_account import UserAccountController 

def login_page():
    ui.colors(primary='#3B82F6')  # 主色系（藍色）
    ui.page_title('AI輔助軟體工程工具 - 登入')

    with ui.column().classes('w-full h-screen items-center justify-center bg-gray-100'):
        with ui.card().classes('w-96 shadow-2xl p-8 rounded-2xl bg-white'):
            ui.label('AI 輔助軟體工程工具').classes('text-2xl font-bold text-center text-blue-600 mb-6')

            account = ui.input(label='帳號', placeholder='請輸入帳號').classes('w-full mb-4')
            password = ui.input(label='密碼', password=True, placeholder='請輸入密碼').classes('w-full mb-6')

            with ui.row().classes('justify-between w-full'):
                ui.button('登入', color='blue', on_click=lambda: UserAccountController.login(account.value, password.value)).classes('w-1/2 mr-2')
                ui.button('註冊', color='green', on_click=lambda: UserAccountController.register(account.value, password.value)).classes('w-1/2 ml-2')

            ui.separator().classes('my-6')
            ui.label('© 2025 澎湖科技大學 資管系 AI-SE 專題').classes('text-xs text-gray-500 text-center')
