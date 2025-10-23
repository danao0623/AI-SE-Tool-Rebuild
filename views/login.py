from nicegui import ui

def login_page(on_login=None, on_register=None):
    """登入畫面 View
    on_login: 登入按鈕事件（callback）
    on_register: 註冊按鈕事件（callback）
    """
    ui.colors(primary='#2563EB')  # 主色（深藍）
    ui.page_title('AI輔助軟體工程工具 - 登入')

    # --- 背景與置中容器 ---
    with ui.column().classes('w-full h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-gray-100'):
        with ui.card().classes('w-96 shadow-2xl p-8 rounded-2xl bg-white'):
            
            # 標題
            ui.label('AI 輔助軟體工程工具').classes(
                'text-2xl font-bold text-center text-blue-600 mb-6 tracking-wide'
            )

            # 帳號輸入
            account = ui.input(
                label='帳號',
                placeholder='請輸入帳號'
            ).classes('w-full mb-4')

            # 密碼輸入
            password = ui.input(
                label='密碼',
                password=True,
                placeholder='請輸入密碼'
            ).classes('w-full mb-6')

            # 登入/註冊按鈕區
            with ui.row().classes('justify-between w-full'):
                ui.button(
                    '登入',
                    color='primary',
                    on_click=lambda: on_login and on_login(account.value, password.value)
                ).classes('w-1/2 mr-2 h-12 text-base font-semibold')

                ui.button(
                    '註冊',
                    color='green',
                    on_click=lambda: on_register and on_register(account.value, password.value)
                ).classes('w-1/2 ml-2 h-12 text-base font-semibold')

            # 分隔線
            ui.separator().classes('my-6')

            # 頁腳
            ui.label('© 2025 澎湖科技大學 資管系 AI-SE 專題').classes(
                'text-xs text-gray-500 text-center mt-4'
            )
