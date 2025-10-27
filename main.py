import asyncio
from nicegui import ui,app
from views.login_view import login_page
from flow_controllers.login_flow import LoginFlowController
from views.project_view import project_page

@ui.page('/')
def main():
    login_page(
        on_login=lambda acc, pwd: asyncio.create_task(LoginFlowController.handle_login(acc, pwd)),
        on_register=lambda acc, pwd: asyncio.create_task(LoginFlowController.handle_register(acc, pwd)),
        redirect_url='/project'
    )
def main_page():
    print("🔐 登入狀態內容:", app.storage.user)  # 🧠 在伺服器端印出目前的 user 狀態
    ui.label('這是主頁面')


@ui.page('/project')
def project_page_route():
    project_page()

ui.run(
    storage_secret='private key to secure the browser session cookie',
    reload=False,
    port=8080,
    host='0.0.0.0',
    reconnect_timeout=60
)
