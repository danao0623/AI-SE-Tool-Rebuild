from nicegui import ui
from flow_controllers.project import ProjectFlowController

def project_page():
    """AI 專案管理頁面（三欄並排修正版）"""

    class State:
        loading = False
        selected_fields = []

    async def generate_project():
        name = project_name_input.value.strip()
        if not name:
            ui.notify("請輸入專案名稱", color="red")
            return
        State.loading = True
        ui.notify("AI 生成中...", color="blue")
        data = await ProjectFlowController.generate_project_data(name)
        State.loading = False

        if not data:
            ui.notify("AI 生成失敗", color="red")
            return

        for row in data:
            label, content = row["項目"], row["內容"]
            if label == "專案描述":
                project_description.value = content
            elif label == "系統架構":
                project_architecture.value = content
            elif label == "前端語言":
                frontend_lang.value = content
            elif label == "前端平台":
                frontend_platform.value = content
            elif label == "前端函式庫":
                frontend_lib.value = content
            elif label == "後端語言":
                backend_lang.value = content
            elif label == "後端平台":
                backend_platform.value = content
            elif label == "後端函式庫":
                backend_lib.value = content

        ui.notify("AI 生成完成", color="green")

    async def regenerate_selected():
        name = project_name_input.value.strip()
        if not name:
            ui.notify("請先輸入專案名稱", color="red")
            return
        if not State.selected_fields:
            ui.notify("請選擇要再生的欄位", color="red")
            return
        ui.notify(f"AI 重新生成：{', '.join(State.selected_fields)}...", color="blue")
        State.loading = True
        data = await ProjectFlowController.regenerate_selected_fields(name, State.selected_fields)
        State.loading = False

        for row in data:
            label, content = row["項目"], row["內容"]
            if label in State.selected_fields:
                if label == "專案描述":
                    project_description.value = content
                elif label == "系統架構":
                    project_architecture.value = content
                elif label == "前端語言":
                    frontend_lang.value = content
                elif label == "前端平台":
                    frontend_platform.value = content
                elif label == "前端函式庫":
                    frontend_lib.value = content
                elif label == "後端語言":
                    backend_lang.value = content
                elif label == "後端平台":
                    backend_platform.value = content
                elif label == "後端函式庫":
                    backend_lib.value = content

        ui.notify("AI 再生完成", color="green")

    def toggle_field(field_name):
        if field_name in State.selected_fields:
            State.selected_fields.remove(field_name)
        else:
            State.selected_fields.append(field_name)

    # === 畫面配置 ===
    with ui.element().classes('grid grid-cols-4 gap-6 w-full h-screen bg-gray-50 p-6 items-start'):

        # 🧭 左側流程
        with ui.card().classes('col-span-1 p-5 bg-white rounded-xl shadow-md h-full flex flex-col justify-between'):
            with ui.column():
                ui.label('🧭 專案流程').classes('text-lg font-bold mb-3 text-gray-800')
                with ui.stepper().props('vertical').classes('w-full'):
                    ui.step('專案管理').props('active')
                    ui.step('使用案例管理')
                    ui.step('使用案例明細')
                    ui.step('專案物件瀏覽')
                    ui.step('產生程式碼')
                ui.separator()
                ui.label('進入專案管理功能').classes('text-gray-500 text-sm text-center mb-2')
            ui.button('下一步', color='blue').classes('w-full')

        # 🧠 中間主體
        with ui.card().classes('col-span-2 p-6 bg-white rounded-xl shadow-md flex flex-col gap-3 overflow-y-auto'):
            ui.label('📘 專案管理系統').classes('text-2xl font-bold text-center text-indigo-700')
            ui.label('輸入專案名稱後，AI 將自動生成技術堆疊與描述。').classes('text-center text-gray-500 mb-2')

            with ui.row().classes('justify-center gap-3'):
                project_name_input = ui.input('專案名稱').classes('w-1/2')
                ui.button('生成專案資料', color='blue', on_click=generate_project).classes('text-white px-4')

            with ui.grid(columns=2).classes('w-full gap-3 mt-2'):
                frontend_lang = ui.input('前端語言')
                frontend_platform = ui.input('前端平台')
                frontend_lib = ui.input('前端函式庫')
                backend_lang = ui.input('後端語言')
                backend_platform = ui.input('後端平台')
                backend_lib = ui.input('後端函式庫')

            project_architecture = ui.textarea(label='系統架構').classes('w-full h-24')
            project_description = ui.textarea(label='專案描述').classes('w-full h-24')

        # 🤖 右側 AI 再生
        with ui.card().classes('col-span-1 p-5 bg-white rounded-xl shadow-md flex flex-col gap-3 h-full'):
            ui.label('🤖 AI 欄位再生').classes('text-lg font-bold text-indigo-700 mb-2 text-center')
            ui.label('選擇要重新生成的欄位：').classes('text-sm text-gray-600 mb-2')

            for label in ['專案描述', '系統架構', '前端語言', '前端平台', '前端函式庫',
                          '後端語言', '後端平台', '後端函式庫']:
                with ui.row().classes('justify-between items-center w-full'):
                    ui.label(label)
                    ui.checkbox(on_change=lambda e, f=label: toggle_field(f))

            ui.button('重新生成選取欄位', color='green', on_click=regenerate_selected).classes('w-full mt-3')
            spinner = ui.spinner(size='lg', color='blue')
            spinner.bind_visibility_from(State, 'loading')