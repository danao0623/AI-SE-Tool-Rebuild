from nicegui import ui
from flow_controllers.login import LoginFlowController
import asyncio

def login_page(on_login=None, on_register=None):
    """登入頁面 View（負責顯示畫面與 UI 互動）"""
    ui.colors(primary='#2563EB')
    ui.page_title('AI輔助軟體工程工具 - 登入')

    with ui.column().classes('w-full h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-gray-100'):
        with ui.card().classes('w-96 shadow-2xl p-8 rounded-2xl bg-white'):

            ui.label('AI 輔助軟體工程工具').classes('text-2xl font-bold text-center text-blue-600 mb-6 tracking-wide')

            account = ui.input(label='帳號', placeholder='請輸入帳號').classes('w-full mb-4')
            password = ui.input(label='密碼', password=True, placeholder='請輸入密碼').classes('w-full mb-6')

            async def on_login_click():
                if on_login:
                    result = await on_login(account.value, password.value)
                    ui.notify(result['message'], color=_map_color(result['status']))
                    if result['status'] == 'success':
                        await asyncio.sleep(0.8)
                        ui.navigate.to('/project')

            async def on_register_click():     # 註冊按鈕事件
                if on_register:
                    result = await on_register(account.value, password.value)
                    ui.notify(result['message'], color=_map_color(result['status']))
                    if result['status'] == 'success':
                        await asyncio.sleep(1.2)
                        ui.navigate.to('/')

            with ui.row().classes('justify-between w-full'):
                ui.button('登入', color='primary', on_click=on_login_click).classes('w-1/2 mr-2 h-12 text-base font-semibold')
                ui.button('註冊', color='green', on_click=on_register_click).classes('w-1/2 ml-2 h-12 text-base font-semibold')

            ui.separator().classes('my-6')
            ui.label('© 2025 澎湖科技大學 資管系 AI-SE 專題').classes('text-xs text-gray-500 text-center mt-4')

def _map_color(status: str):
    return {
        'success': 'positive',
        'warning': 'warning',
        'error': 'negative',
    }.get(status, 'primary')