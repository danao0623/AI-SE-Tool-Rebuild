# 📁 views/project_view.py
import asyncio
from nicegui import ui
from flow_controllers.project_flow import ProjectFlowController


def project_page():
    """AI 專案管理頁面（完整版：生成、儲存、開啟、刪除、再生）"""

    class State:
        loading = False
        selected_fields = []
        generated_data = {}
        selected_project = None

    # === 🧠 生成專案資料 ===
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
            State.generated_data[label] = content
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

        ui.notify("AI 生成完成，可修改後按『💾 儲存專案』", color="green")

    # === 💾 儲存專案 ===
    async def save_project():
        name = project_name_input.value.strip()
        if not name:
            ui.notify("請輸入專案名稱", color="red")
            return

        ui.notify("資料儲存中...", color="blue")

        project_data = {
            "name": name,
            "description": project_description.value,
            "architecture": project_architecture.value,
            "frontend_language": frontend_lang.value,
            "frontend_platform": frontend_platform.value,
            "frontend_library": frontend_lib.value,
            "backend_language": backend_lang.value,
            "backend_platform": backend_platform.value,
            "backend_library": backend_lib.value,
        }

        success = await ProjectFlowController.save_project(project_data)
        if success:
            ui.notify("專案資料已儲存 ✅", color="green")
            await refresh_project_table()
        else:
            ui.notify("資料儲存失敗，請確認登入狀態", color="red")

    # === 📂 開啟專案（方法一：從資料庫重新查）===
    async def on_open_project(e=None):
        selected = State.selected_project
        if not selected:
            ui.notify("請選擇要開啟的專案", color="red")
            return

        project_detail = await ProjectFlowController.get_project_detail(selected["id"])
        if not project_detail:
            ui.notify("找不到專案資料", color="red")
            return

        project_name_input.value = project_detail["name"]
        project_description.value = project_detail["description"]
        project_architecture.value = project_detail["architecture"]
        frontend_lang.value = project_detail["frontend_language"]
        frontend_platform.value = project_detail["frontend_platform"]
        frontend_lib.value = project_detail["frontend_library"]
        backend_lang.value = project_detail["backend_language"]
        backend_platform.value = project_detail["backend_platform"]
        backend_lib.value = project_detail["backend_library"]

        ui.notify(f"已開啟專案：{project_detail['name']}", color="green")

    # === 🗑️ 刪除專案 ===
    async def on_delete_project(e=None):
        selected = State.selected_project
        if not selected:
            ui.notify("請選擇要刪除的專案", color="red")
            return
        await ProjectFlowController.delete_project(selected["id"])
        ui.notify(f"已刪除專案：{selected['專案名稱']}", color="orange")
        await refresh_project_table()

    # === 📊 更新表格 ===
    async def refresh_project_table():
        projects = await ProjectFlowController.list_user_projects()
        project_table.options["rowData"] = projects
        project_table.update()

    # === 🔄 再生選取欄位 ===
    async def regenerate_selected():
        name = project_name_input.value.strip()
        if not name:
            ui.notify("請輸入專案名稱", color="red")
            return
        if not State.selected_fields:
            ui.notify("請選擇要重新生成的欄位", color="red")
            return

        ui.notify(f"AI 正在重新生成：{', '.join(State.selected_fields)}...", color="blue")
        State.loading = True
        data = await ProjectFlowController.regenerate_selected_fields(name, State.selected_fields)
        State.loading = False

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

        ui.notify("AI 再生完成 ✅", color="green")

    # === ✅ 勾選再生欄位 ===
    def toggle_field(field_name: str):
        if field_name in State.selected_fields:
            State.selected_fields.remove(field_name)
        else:
            State.selected_fields.append(field_name)

    # === 🧱 UI 介面 ===
    with ui.element().classes('grid grid-cols-4 gap-6 w-full h-screen bg-gray-50 p-6 items-start'):

        # 🧭 左側導覽
        with ui.card().classes('col-span-1 p-5 bg-white rounded-xl shadow-md h-full flex flex-col justify-between'):
            with ui.column():
                ui.label('🧭 專案流程').classes('text-lg font-bold mb-3 text-gray-800')
                with ui.stepper().props('vertical').classes('w-full'):
                    ui.step('專案管理').props('active')
                    ui.step('使用案例管理')
                    ui.step('使用案例明細')
                    ui.step('專案物件瀏覽')
                    ui.step('產生程式碼')
            ui.button('下一步', color='blue').classes('w-full')

        # 🧠 中間主內容
        with ui.card().classes('col-span-2 p-6 bg-white rounded-xl shadow-md flex flex-col gap-4 overflow-y-auto'):
            ui.label('📘 專案管理系統').classes('text-2xl font-bold text-center text-indigo-700')

            with ui.row().classes('justify-center gap-3'):
                project_name_input = ui.input('專案名稱').classes('w-1/2')
                ui.button('生成專案資料', color='blue', on_click=generate_project)

            with ui.grid(columns=2).classes('w-full gap-3 mt-2'):
                frontend_lang = ui.input('前端語言')
                frontend_platform = ui.input('前端平台')
                frontend_lib = ui.input('前端函式庫')
                backend_lang = ui.input('後端語言')
                backend_platform = ui.input('後端平台')
                backend_lib = ui.input('後端函式庫')

            project_architecture = ui.textarea('系統架構').classes('w-full h-36 text-sm')
            project_description = ui.textarea('專案描述').classes('w-full h-36 text-sm')

            ui.button('💾 儲存專案', color='green', on_click=save_project).classes('w-1/3 mx-auto')

            ui.separator()
            ui.label('📂 專案清單').classes('text-lg font-bold text-gray-700')

            with ui.aggrid({
                'columnDefs': [
                    {'headerName': '專案名稱', 'field': '專案名稱', 'sortable': True, 'filter': True},
                    {'headerName': '專案描述', 'field': '專案描述', 'flex': 2},
                    {'headerName': '系統架構', 'field': '系統架構', 'flex': 2},
                ],
                'rowSelection': 'single',
                'defaultColDef': {'resizable': True, 'sortable': True, 'filter': True},
            }).classes('w-full h-64 mt-3') as project_table:
                project_table.on('cellClicked', lambda e: setattr(State, 'selected_project', e.args.get('data')))

            with ui.row().classes('justify-center gap-4 mt-3'):
                ui.button('🗑️ 刪除專案', color='red', on_click=on_delete_project)
                ui.button('📂 開啟專案', color='blue', on_click=on_open_project)

            ui.timer(1.5, lambda: asyncio.create_task(refresh_project_table()), once=True)

        # 🤖 右側 AI 再生
        with ui.card().classes('col-span-1 p-5 bg-white rounded-xl shadow-md flex flex-col gap-3 h-full'):
            ui.label('🤖 AI 欄位再生').classes('text-lg font-bold text-indigo-700 mb-2 text-center')

            for label in ['專案描述', '系統架構', '前端語言', '前端平台', '前端函式庫',
                          '後端語言', '後端平台', '後端函式庫']:
                with ui.row().classes('justify-between items-center w-full'):
                    ui.label(label)
                    ui.checkbox(on_change=lambda e, f=label: toggle_field(f))

            ui.button('重新生成選取欄位', color='green', on_click=regenerate_selected).classes('w-full mt-3')
            spinner = ui.spinner(size='lg', color='blue')
            spinner.bind_visibility_from(State, 'loading')