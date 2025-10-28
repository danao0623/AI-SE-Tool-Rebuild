# 📁 views/project_view.py
import asyncio
from nicegui import ui
from flow_controllers.project_flow import ProjectFlowController


def project_page():
    """AI 專案管理頁面（支援 開啟/刪除；更新時清掉後續產物；可再生欄位）"""

    class State:
        loading = False
        selected_fields = []
        generated_data = {}      # 以「顯示標籤」為 key 的暫存（方便直接綁 UI）
        selected_project = None  # aggrid 選到的 row 資料

    # --- 共用：把 dict 值回填到表單 ---
    def update_fields(data: dict):
        mapping = {
            "專案描述": project_description,
            "系統架構": project_architecture,
            "前端語言": frontend_lang,
            "前端平台": frontend_platform,
            "前端函式庫": frontend_lib,
            "後端語言": backend_lang,
            "後端平台": backend_platform,
            "後端函式庫": backend_lib,
        }
        for label, value in data.items():
            if label in mapping:
                mapping[label].value = value
                State.generated_data[label] = value

    # --- 初次生成（固定 baseline）---
    async def generate_project():
        name = project_name_input.value.strip()
        if not name:
            return ui.notify("請輸入專案名稱", color="red")

        ui.notify("AI 生成中...", color="blue")
        State.loading = True
        rows = await ProjectFlowController.generate_project_data(name)
        State.loading = False

        if not rows:
            return ui.notify("AI 生成失敗", color="red")

        # 轉 row -> label dict，並回填 UI
        State.generated_data = {r["項目"]: r["內容"] for r in rows}
        update_fields(State.generated_data)
        ui.notify("AI 初次生成完成 ✅", color="green")

    # --- 再生（完整重生，但只覆蓋勾選欄位）---
    async def regenerate_selected():
        name = project_name_input.value.strip()
        if not name:
            return ui.notify("請輸入專案名稱", color="red")
        if not State.selected_fields:
            return ui.notify("請選擇要再生的欄位", color="red")

        ui.notify(f"AI 正在重新生成：{', '.join(State.selected_fields)}...", color="blue")
        State.loading = True
        new_rows = await ProjectFlowController.regenerate_selected_fields(
            name, State.selected_fields, State.generated_data
        )
        State.loading = False

        new_data = {r["項目"]: r["內容"] for r in new_rows if r["內容"]}
        update_fields(new_data)
        ui.notify("AI 再生完成 ✅", color="green")

    # --- 儲存（若「核心欄位有變」→ 自動清掉 2/3 階段產物）---
    async def save_project():
        name = project_name_input.value.strip()
        if not name:
            return ui.notify("請輸入專案名稱", color="red")

        data = {
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
        ui.notify("資料儲存中...", color="blue")
        result = await ProjectFlowController.save_project(data)

        if not result.get("ok"):
            return ui.notify("儲存失敗，請確認登入狀態", color="red")

        await refresh_project_table()
        action = result.get("action")
        if action == "created":
            ui.notify("專案已新增 ✅", color="green")
        elif action == "updated":
            ui.notify("專案已更新（內容無重大變更）✅", color="green")
        elif action == "updated_purged":
            ui.notify("專案已更新 ✅ — 由於核心設定變更，已清空後續(UseCase/Detail/物件/圖/檔案)產物", color="orange")

    # --- 開啟專案（把 DB 內容塞回上方表單）---
    async def on_open_project():
        row = State.selected_project
        if not row:
            return ui.notify("請先在下方選擇一個專案", color="red")

        detail = await ProjectFlowController.get_project_detail(row["id"])
        if not detail:
            return ui.notify("找不到專案內容", color="red")

        # 回填
        project_name_input.value = detail["name"]
        update_fields({
            "專案描述": detail["description"],
            "系統架構": detail["architecture"],
            "前端語言": detail["frontend_language"],
            "前端平台": detail["frontend_platform"],
            "前端函式庫": detail["frontend_library"],
            "後端語言": detail["backend_language"],
            "後端平台": detail["backend_platform"],
            "後端函式庫": detail["backend_library"],
        })
        ui.notify(f"已開啟專案：{detail['name']}", color="green")

    # --- 刪除專案（含級聯清掉後續產物）---
    async def on_delete_project():
        row = State.selected_project
        if not row:
            return ui.notify("請先在下方選擇一個專案", color="red")
        await ProjectFlowController.delete_project(row["id"])
        ui.notify(f"已刪除專案：{row['專案名稱']}（含後續產物）", color="orange")
        await refresh_project_table()

    # --- 專案清單（列表）---
    async def refresh_project_table():
        rows = await ProjectFlowController.list_user_projects()
        project_table.options["rowData"] = rows
        project_table.update()

    # --- 勾選再生欄位 ---
    def toggle_field(field: str):
        if field in State.selected_fields:
            State.selected_fields.remove(field)
        else:
            State.selected_fields.append(field)

    # ================== UI 佈局 ==================
    with ui.element().classes('grid grid-cols-4 gap-6 w-full h-screen bg-gray-50 p-6 items-start'):

        # 左：流程
        with ui.card().classes('col-span-1 p-5 bg-white rounded-xl shadow-md h-full flex flex-col justify-between'):
            ui.label('🧭 專案流程').classes('text-lg font-bold mb-3 text-gray-800')
            with ui.stepper().props('vertical').classes('w-full'):
                ui.step('專案管理').props('active')
                ui.step('使用案例管理')
                ui.step('使用案例明細')
                ui.step('專案物件瀏覽')
                ui.step('程式碼生成')
            ui.button('下一步', color='blue').classes('w-full')

        # 中：主內容
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

            with ui.row().classes('justify-center gap-4'):
                ui.button('💾 儲存專案', color='green', on_click=save_project)
                ui.button('📂 開啟專案', color='blue', on_click=on_open_project)
                ui.button('🗑️ 刪除專案', color='red', on_click=on_delete_project)

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

            ui.timer(1.0, lambda: asyncio.create_task(refresh_project_table()), once=True)

        # 右：AI 再生欄位
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
