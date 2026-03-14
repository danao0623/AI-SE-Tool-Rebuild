# views/object_view.py
from __future__ import annotations

from typing import Any, Dict, Optional
import re
from nicegui import ui, app
from flow_controllers.object_flow import ObjectFlowController


def _extract_row(e: Any) -> Optional[Dict[str, Any]]:
    args = getattr(e, "args", None)
    if isinstance(args, dict):
        if isinstance(args.get("row"), dict):
            return args["row"]
        if "id" in args:
            return args
    if isinstance(args, list):
        for item in args:
            if isinstance(item, dict):
                if isinstance(item.get("row"), dict):
                    return item["row"]
                if "id" in item:
                    return item
    return None


def _parse_usecase_id(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return None
    m = re.match(r"^\s*(\d+)\s*(?:[-–—].*)?$", s)
    if m:
        return int(m.group(1))
    m2 = re.search(r"(\d+)", s)
    return int(m2.group(1)) if m2 else None


async def _show_object_detail(object_id: int) -> None:
    detail = await ObjectFlowController.get_object_detail(int(object_id))
    obj = detail.get("object") or {}
    attrs = detail.get("attributes") or []
    meths = detail.get("methods") or []

    with ui.dialog() as dialog, ui.card().classes("w-[950px] max-w-[95vw]"):
        ui.label(f"物件詳細：{obj.get('name','')}").classes("text-lg font-bold")
        ui.label(f"類型：{obj.get('type','')}").classes("text-sm text-gray-600")
        if obj.get("usecase_name"):
            ui.label(f"所屬 Use Case：{obj.get('usecase_name','')}").classes("text-sm text-gray-600")
        if obj.get("description"):
            ui.label(f"說明：{obj.get('description','')}").classes("text-sm text-gray-700")

        ui.separator().classes("my-3")

        ui.label("屬性（Attributes）").classes("font-semibold")
        ui.table(
            columns=[
                {"name": "name", "label": "名稱", "field": "name"},
                {"name": "type", "label": "型別", "field": "type"},
                {"name": "visibility", "label": "可見性", "field": "visibility"},
                {"name": "default", "label": "預設值", "field": "default"},
            ],
            rows=attrs,
        ).props("flat bordered dense row-key=id").classes("w-full max-h-[28vh] overflow-y-auto")

        ui.separator().classes("my-3")

        ui.label("方法（Methods）").classes("font-semibold")
        ui.table(
            columns=[
                {"name": "name", "label": "名稱", "field": "name"},
                {"name": "parameters", "label": "參數", "field": "parameters"},
                {"name": "return_type", "label": "回傳", "field": "return_type"},
                {"name": "visibility", "label": "可見性", "field": "visibility"},
            ],
            rows=meths,
        ).props("flat bordered dense row-key=id").classes("w-full max-h-[28vh] overflow-y-auto")

        with ui.row().classes("justify-end w-full mt-3"):
            ui.button("關閉", on_click=dialog.close).props("outline")

    dialog.open()


def svo_page() -> None:
    current_project: Dict[str, Any] = app.storage.user.get("current_project") or {}
    if not current_project:
        with ui.column().classes("w-full h-screen items-center justify-center bg-gray-50 p-8 gap-4"):
            ui.label("專案物件瀏覽（Object Browser）").classes("text-2xl font-bold text-red-600")
            ui.label("尚未選擇專案，請先回到「專案管理」頁面選擇一個專案。")
            ui.button("回到專案管理", color="primary", on_click=lambda: ui.navigate.to("/project"))
        return

    state: Dict[str, Any] = {"usecase_id": None, "usecase_options": {}}
    usecase_select = None
    boundary_table = None
    control_table = None
    entity_table = None

    columns = [
        {"name": "usecase_name", "label": "Use Case", "field": "usecase_name"},
        {"name": "name", "label": "名稱", "field": "name"},
        {"name": "description", "label": "說明", "field": "description"},
        {"name": "attributes", "label": "屬性", "field": "attributes"},
        {"name": "methods", "label": "方法", "field": "methods"},
    ]

    async def load_objects() -> None:
        uc_id = state.get("usecase_id")
        if uc_id is None:
            if boundary_table:
                boundary_table.rows = []
                boundary_table.update()
            if control_table:
                control_table.rows = []
                control_table.update()
            if entity_table:
                entity_table.rows = []
                entity_table.update()
            return

        data = await ObjectFlowController.list_objects_grouped_by_type(usecase_id=int(uc_id))

        if boundary_table:
            boundary_table.rows = data.get("Boundary", []) or []
            boundary_table.update()
        if control_table:
            control_table.rows = data.get("Control", []) or []
            control_table.update()
        if entity_table:
            entity_table.rows = data.get("Entity", []) or []
            entity_table.update()

    async def on_row_click(e: Any) -> None:
        row = _extract_row(e)
        if not row:
            ui.notify("無法取得點擊列資料", type="warning")
            return
        object_id = row.get("id")
        if not object_id:
            ui.notify("找不到物件 id", type="warning")
            return
        await _show_object_detail(int(object_id))

    async def on_usecase_change(e: Any) -> None:
        uc_id = _parse_usecase_id(getattr(e, "value", None))
        state["usecase_id"] = uc_id
        await load_objects()

    async def load_usecases_and_first() -> None:
        nonlocal usecase_select
        usecases = await ObjectFlowController.list_usecases_for_current_project()
        if usecase_select is None:
            return

        if not usecases:
            usecase_select.options = {}
            usecase_select.value = None
            usecase_select.update()
            state["usecase_id"] = None
            await load_objects()
            return

        options = {str(uc["id"]): f'{uc["id"]} - {uc.get("name", "")}' for uc in usecases if uc.get("id") is not None}
        state["usecase_options"] = options
        usecase_select.options = options

        first_id = int(usecases[0]["id"])
        state["usecase_id"] = first_id
        usecase_select.value = str(first_id)
        usecase_select.update()

        await load_objects()

    async def generate_objects_for_selected_usecase() -> None:
        uc_id = state.get("usecase_id")
        if uc_id is None:
            ui.notify("請先選擇一個 Use Case", type="warning", timeout=3000)
            return

        ui.notify("正在產生 / 重生（當前 Use Case）…", type="info", timeout=2000)
        result = await ObjectFlowController.generate_objects_for_current_project(usecase_id=int(uc_id))

        if not result.get("ok"):
            ui.notify(f"生成失敗：{result.get('reason', '未知錯誤')}", type="negative", timeout=6000)
            return

        ui.notify(f"完成：建立 {result.get('created', 0)} 筆，刪除 {result.get('deleted', 0)} 筆", type="positive", timeout=4500)
        await load_objects()

    async def generate_objects_for_all_usecases() -> None:
        ui.notify("正在一次生成全部 Use Case 物件…", type="info", timeout=2500)
        # ✅ 不傳 usecase_id/usecase_ids，Flow 會自動抓全部 usecase ids
        result = await ObjectFlowController.generate_objects_for_current_project()

        if not result.get("ok"):
            ui.notify(f"生成失敗：{result.get('reason', '未知錯誤')}", type="negative", timeout=8000)
            return

        ui.notify(f"完成（全部 Use Case）：建立 {result.get('created', 0)} 筆，刪除 {result.get('deleted', 0)} 筆", type="positive", timeout=6000)
        # 生成完成後，刷新當前選到的 usecase 畫面
        await load_objects()

    with ui.element().classes("grid grid-cols-4 gap-6 w-full h-screen bg-gray-50 p-6 items-start"):
        with ui.card().classes("col-span-1 p-5 bg-white rounded-xl shadow-md h-full flex flex-col justify-between"):
            ui.label("🧭 專案流程").classes("text-lg font-bold mb-3 text-gray-800")
            with ui.stepper(value=5).props("vertical").classes("w-full"):
                ui.step("專案管理").props("name=1 done")
                ui.step("專案案例管理").props("name=2 done")
                ui.step("使用案例明細").props("name=3 done")
                ui.step("三段式事件列表").props("name=4 done")
                ui.step("專案物件瀏覽").props("name=5")
                ui.step("UML 圖生成").props("name=6")
                ui.step('介面藍圖').props('name=7')
                ui.step('產生程式碼').props('name=8')

            with ui.row().classes("w-full justify-between mt-4"):
                ui.button("上一頁（三段式事件列表）", on_click=lambda: ui.navigate.to("/event_summary")).props("outline")
                ui.button("下一步（圖像 / 程式碼產生）", color="primary", on_click=lambda: ui.navigate.to("/mermaid"))

        with ui.card().classes("col-span-2 p-6 bg-white rounded-xl shadow-md flex flex-col gap-4 h-full"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("專案物件瀏覽（Object Browser）").classes("text-2xl font-bold text-gray-800")
                ui.label(f"目前專案：{current_project.get('name', '')}").classes("text-sm text-gray-600")

            ui.separator().classes("my-2")

            with ui.row().classes("items-center w-full gap-2"):
                ui.label("選擇 Use Case：").classes("font-semibold")
                usecase_select = ui.select(label=None, options={}, on_change=on_usecase_change).classes("w-72").props("outlined dense")

            ui.separator().classes("my-2")

            ui.label("邊界物件（Boundary）").classes("font-semibold text-gray-800")
            boundary_table = ui.table(columns=columns, rows=[]).props("flat bordered dense row-key=id").classes("w-full max-h-[22vh] overflow-y-auto")
            boundary_table.on("rowClick", on_row_click)

            ui.separator().classes("my-2")
            ui.label("控制物件（Control）").classes("font-semibold text-gray-800")
            control_table = ui.table(columns=columns, rows=[]).props("flat bordered dense row-key=id").classes("w-full max-h-[22vh] overflow-y-auto")
            control_table.on("rowClick", on_row_click)

            ui.separator().classes("my-2")
            ui.label("實體物件（Entity）").classes("font-semibold text-gray-800")
            entity_table = ui.table(columns=columns, rows=[]).props("flat bordered dense row-key=id").classes("w-full max-h-[22vh] overflow-y-auto")
            entity_table.on("rowClick", on_row_click)

        with ui.card().classes("col-span-1 p-5 bg-white rounded-xl shadow-md flex flex-col gap-4"):
            ui.label("🤖 AI 產生專案物件").classes("text-lg font-bold text-gray-800")
            ui.label(
                "- 你可以只生成目前選取的 Use Case\n"
                "- 也可以一次生成全部 Use Case（建議第一次用這個）\n"
                "- 生成後可用下拉切換檢視各 Use Case 的物件"
            ).classes("text-sm text-gray-600 whitespace-pre-line")

            ui.button("🧠 產生 / 重生（當前 Use Case）", color="primary", on_click=generate_objects_for_selected_usecase)
            ui.button("🚀 一次生成（全部 Use Case）", color="secondary", on_click=generate_objects_for_all_usecases).props("outline")

    ui.timer(0.1, load_usecases_and_first, once=True)
