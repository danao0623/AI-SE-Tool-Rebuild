import asyncio
from nicegui import ui
from views.login import login_page
from flow_controllers.login import LoginFlowController

@ui.page('/')
def main():
    login_page(
        on_login=lambda acc, pwd: asyncio.create_task(LoginFlowController.handle_login(acc, pwd)),
        on_register=lambda acc, pwd: asyncio.create_task(LoginFlowController.handle_register(acc, pwd)),
    )

ui.run(
    storage_secret='private key to secure the browser session cookie',
    reload=False,
    port=8080,
    host='0.0.0.0',
    reconnect_timeout=60
)
