import asyncio
from nicegui import ui, app

from views.login_view import login_page
from flow_controllers.login_flow import LoginFlowController
from views.project_view import project_page
from views.usecase_and_actor_view import usecase_actor_page
from views.usecase_detail_view import usecase_detail_page
from views.event_summary_view import event_summary_page
from views.object_view import svo_page
from views.mermaid_view import mermaid_page
from views.blueprint_view import blueprint_page
from views.code_view import code_page
from flow_controllers.blueprint_api_flow import router as blueprint_router


@ui.page('/')
def main():
    login_page(
        on_login=lambda acc, pwd: asyncio.create_task(
            LoginFlowController.handle_login(acc, pwd)
        ),
        on_register=lambda acc, pwd: asyncio.create_task(
            LoginFlowController.handle_register(acc, pwd)
        ),
        redirect_url='/project',
    )


def main_page():
    # 這個目前沒掛路由，只是你自己除錯用的
    print("🔐 登入狀態內容:", app.storage.user)
    ui.label('這是主頁面')


@ui.page('/project')
def project_page_route():
    project_page()


# 🔧 這裡是重點：路徑改成 /usecase_actor，並呼叫真正的 view
@ui.page('/usecase_actor')
def usecase_actor_page_route():
    usecase_actor_page()

@ui.page('/usecase_detail')
def usecase_detail_page_route():
    usecase_detail_page()

@ui.page('/event_summary')
def event_summary_page_route():
    event_summary_page()


@ui.page("/svo")
def svo_page_route():
    svo_page()

@ui.page("/mermaid")
def mermaid_page_route():
    mermaid_page()

@ui.page("/blueprint")
def blueprint_page_route():
    blueprint_page()

@ui.page("/code")
def code_page_route():
    code_page()

# ... 其他 import

app.add_static_files('/files', 'files')

app.include_router(blueprint_router)

ui.run(
    storage_secret='private key to secure the browser session cookie',
    reload=False,
    port=8080,
    host='0.0.0.0',
    reconnect_timeout=60,
)