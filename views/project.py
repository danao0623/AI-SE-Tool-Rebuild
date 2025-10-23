import asyncio
from nicegui import ui

def project_page():
    # ✅ 定義狀態變數
    class State:
        loading = False

    with ui.row().classes('w-full h-full justify-between p-4 gap-4'):
        # 左側 Stepper 導覽
        with ui.card().classes('w-1/5 p-4 shadow-md'):
            ui.label('🧭 專案流程').classes('text-lg font-bold mb-2')
            with ui.stepper().props('vertical').classes('w-full'):
                ui.step('專案管理')
                ui.step('使用案例管理').props('active')
                ui.step('使用案例明細')
                ui.step('專案物件瀏覽')
                ui.step('產生程式碼')

        # 中間主要內容
        with ui.card().classes('w-3/5 p-6 shadow-md'):
            ui.label('使用案例管理').classes('text-xl font-bold mb-4 text-center')
            ui.label('AI 生成初步使用案例與角色 (Actors & Use Cases)').classes('text-gray-500 text-sm mb-4')

            with ui.row().classes('gap-2 mb-4'):
                project_name = ui.input('專案名稱').classes('w-1/2')
                ui.button('生成使用案例', color='primary')
                ui.button('清除資料', color='red')

            with ui.card().classes('mt-4 shadow-sm'):
                ui.label('使用案例清單').classes('text-md font-semibold mb-2')
                ui.aggrid({
                    'columnDefs': [
                        {'headerName': '角色名稱', 'field': 'actor'},
                        {'headerName': '使用案例', 'field': 'usecase'},
                        {'headerName': '描述', 'field': 'description'},
                    ],
                    'rowData': [],
                    'rowSelection': 'multiple'
                }).classes('w-full h-80')

            with ui.row().classes('w-full justify-center mt-4'):
                ui.button('進入下一步', color='primary')

        # 右側 AI 模型狀態區
        with ui.card().classes('w-1/5 p-4 text-center shadow-md'):
            ui.label('🤖 AI 模型狀態').classes('text-lg font-bold mb-2')

            spinner = ui.spinner(size='lg', color='blue')
            spinner.bind_visibility_from(State, 'loading')

            async def regenerate():
                State.loading = True
                ui.notify('AI 模型生成中...', color='primary')
                await asyncio.sleep(2)
                State.loading = False
                ui.notify('AI 生成完成！', color='positive')

            ui.button('重新生成', color='primary', on_click=regenerate).classes('mt-4')
            ui.button('導入資料', color='secondary').classes('mt-2')
