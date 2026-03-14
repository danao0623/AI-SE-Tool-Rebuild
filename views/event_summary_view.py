from __future__ import annotations
from typing import Optional

from nicegui import ui, app

from flow_controllers.event_summary_flow import EventSummaryFlowController
from utils.export_event_summary import export_event_summary_md_pdf


# 全域元件引用
usecase_select = None
normal_event_table = None
exception_event_table = None

current_usecase_id: Optional[int] = None


# ============================================================
# 後端事件處理：UseCase / Event
# ============================================================
async def _load_usecases_and_first_events() -> None:
    """頁面載入時：讀取 UseCase 清單，預設載入第一筆的事件。"""
    global usecase_select, current_usecase_id

    try:
        usecases = await EventSummaryFlowController.list_usecases_for_current_project()
    except RuntimeError as e:
        ui.notify("尚未選擇專案，請先回到專案管理頁面。", type="warning", timeout=4000)
        print(f"[EventSummary] list_usecases_for_current_project error: {e}")
        return

    if usecase_select is None:
        return

    if not usecases:
        usecase_select.options = {}
        usecase_select.value = None
        usecase_select.update()

        if normal_event_table:
            normal_event_table.rows = []
            normal_event_table.update()
        if exception_event_table:
            exception_event_table.rows = []
            exception_event_table.update()
        return

    options = {
        str(uc["id"]): f'{uc["id"]} - {uc["name"]}'
        for uc in usecases
        if uc.get("id") is not None
    }

    usecase_select.options = options

    first = usecases[0]
    first_id_str = str(first["id"])
    current_usecase_id = int(first["id"])
    usecase_select.value = first_id_str
    usecase_select.update()

    await _load_events(current_usecase_id)


async def _load_events(usecase_id: int) -> None:
    """讀取指定 UseCase 的事件列表，更新兩張表格。"""
    global current_usecase_id, normal_event_table, exception_event_table
    current_usecase_id = usecase_id

    data = await EventSummaryFlowController.load_events_by_usecase(usecase_id)

    normal_rows = data.get("正常程序", [])
    exception_rows = data.get("例外程序", [])

    if normal_event_table is not None:
        normal_event_table.rows = normal_rows
        normal_event_table.update()

    if exception_event_table is not None:
        exception_event_table.rows = exception_rows
        exception_event_table.update()


async def _on_usecase_select_change(event) -> None:
    """切換 Use Case 下拉選單時觸發。"""
    value = event.value
    if not value:
        return

    try:
        usecase_id = int(value)
    except ValueError:
        return

    await _load_events(usecase_id)


async def _generate_for_all_usecases() -> None:
    """為目前專案所有 Use Case 批次產生事件列表。"""
    ui.notify("正在為全部 Use Case 產生三段式事件列表（AI）…", type="info", timeout=2000)

    result = await EventSummaryFlowController.generate_for_current_project()
    if not result.get("ok", False):
        ui.notify(f"產生失敗：{result.get('reason', '未知錯誤')}", type="negative", timeout=4000)
        return

    uc_count = result.get("usecase_count", 0)
    ev_count = result.get("event_count", 0)
    ui.notify(f"已為 {uc_count} 個 Use Case 產生共 {ev_count} 筆事件。", type="positive", timeout=5000)

    if current_usecase_id is not None:
        await _load_events(current_usecase_id)


# ============================================================
# 匯出：MD / PDF（module-level）
# ============================================================
async def _export_current_usecase(fmt: str = "md") -> None:
    """匯出目前選取 UseCase 的 MD/PDF；fmt: 'md' or 'pdf'"""
    global current_usecase_id, usecase_select

    if current_usecase_id is None:
        ui.notify("請先選擇一個 Use Case", type="warning", timeout=3000)
        return

    if usecase_select is None:
        ui.notify("Use Case 下拉選單尚未初始化", type="warning", timeout=3000)
        return

    label = (usecase_select.options or {}).get(str(current_usecase_id), "")
    usecase_name = label.split(" - ", 1)[-1] if " - " in label else f"usecase_{current_usecase_id}"

    ui.notify("正在匯出 MD / PDF…", type="info", timeout=2000)

    try:
        result = await export_event_summary_md_pdf(current_usecase_id, usecase_name)
    except Exception as e:
        ui.notify(f"匯出失敗：{e}", type="negative", timeout=5000)
        return

    ui.notify("匯出完成。", type="positive", timeout=3000)

    # download 一律使用「本機路徑」，不是 URL
    if fmt == "pdf":
        ui.download(result["pdf_path"])
    else:
        ui.download(result["md_path"])


# ✅ NiceGUI 正確用法：on_click 直接綁 async function（不要 asyncio.create_task）
async def _export_md() -> None:
    await _export_current_usecase("md")


async def _export_pdf() -> None:
    await _export_current_usecase("pdf")


# ============================================================
# Page View 本體
# ============================================================
def event_summary_page() -> None:
    """
    三段式事件列表頁面：
    - 左側：專案流程 Stepper
    - 中間：Use Case 選擇 + 正常/例外事件表格
    - 右側：AI 產生（僅保留「一鍵產生全部 Use Case」）
    """
    current_project = app.storage.user.get("current_project")
    if not current_project:
        with ui.column().classes("w-full h-screen items-center justify-center bg-gray-50 p-8 gap-4"):
            ui.label("三段式事件列表").classes("text-2xl font-bold text-red-600")
            ui.label("尚未選擇專案，請先回到「專案管理」頁面選擇一個專案。")
            ui.button("回到專案管理", color="primary", on_click=lambda: ui.navigate.to("/project"))
        return

    global usecase_select, normal_event_table, exception_event_table

    # 頁面載入後，自動載入 UseCase / Event
    ui.timer(0.1, _load_usecases_and_first_events, once=True)

    with ui.element().classes("grid grid-cols-4 gap-6 w-full h-screen bg-gray-50 p-6 items-start"):
        # --------------------------------------------------------
        # 左側：流程 Stepper
        # --------------------------------------------------------
        with ui.card().classes("col-span-1 p-5 bg-white rounded-xl shadow-md h-full flex flex-col justify-between"):
            ui.label("🧭 專案流程").classes("text-lg font-bold mb-3 text-gray-800")

            with ui.stepper(value=4).props("vertical").classes("w-full"):
                ui.step("專案管理").props("name=1 done")
                ui.step("專案案例管理").props("name=2 done")
                ui.step("使用案例明細").props("name=3 done")
                ui.step("三段式事件列表").props("name=4")
                ui.step("專案物件瀏覽").props("name=5")
                ui.step("UML 圖生成").props("name=6")
                ui.step('介面藍圖').props('name=7')
                ui.step('產生程式碼').props('name=8')

            with ui.row().classes("w-full justify-between mt-4"):
                ui.button(
                    "上一頁（Use Case Detail）",
                    color="grey",
                    on_click=lambda: ui.navigate.to("/usecase_detail"),
                ).props("outline")

                ui.button(
                    "下一步（專案物件瀏覽）",
                    color="primary",
                    on_click=lambda: ui.navigate.to("/svo"),
                )

        # --------------------------------------------------------
        # 中間：Use Case + 事件列表
        # --------------------------------------------------------
        with ui.card().classes("col-span-2 p-6 bg-white rounded-xl shadow-md flex flex-col gap-4 h-full"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("三段式事件列表（Event List）").classes("text-2xl font-bold text-gray-800")
                ui.label(f"目前專案：{current_project.get('name', '')}").classes("text-sm text-gray-600")

            ui.label(
                "說明：此頁顯示由 Use Case Detail 拆解出的「正常程序 / 例外程序」事件。"
                "事件列表將作為後續 UML 圖與程式碼產生的基礎。"
            ).classes("text-sm text-gray-600")

            ui.separator().classes("my-2")

            # Use Case 下拉 + 匯出按鈕（放在旁邊）
            with ui.row().classes("items-center w-full gap-2"):
                ui.label("選擇 Use Case：").classes("font-semibold")

                usecase_select = (
                    ui.select(
                        label=None,
                        options={},
                        on_change=_on_usecase_select_change,
                    )
                    .classes("w-72")
                    .props("outlined dense")
                )

                ui.button("匯出 MD", icon="description", on_click=_export_md).props("outline dense")
                ui.button("匯出 PDF", icon="picture_as_pdf", on_click=_export_pdf).props("outline dense")


            ui.separator().classes("my-2")

            # --- 正常程序事件列表 ---
            ui.label("正常程序事件列表").classes("font-semibold text-gray-800")
            normal_event_table = ui.table(
                columns=[
                    {"name": "sequence_no", "label": "順序", "field": "sequence_no", "align": "left"},
                    {"name": "type", "label": "類型 (Request/Process/Response)", "field": "type", "align": "left"},
                    {"name": "description", "label": "說明", "field": "description", "align": "left"},
                ],
                rows=[],
            ).props("flat bordered dense row-key=id").classes("w-full max-h-[32vh] overflow-y-auto")

            ui.separator().classes("my-2")

            # --- 例外程序事件列表 ---
            ui.label("例外程序事件列表").classes("font-semibold text-gray-800")
            exception_event_table = ui.table(
                columns=[
                    {"name": "sequence_no", "label": "順序", "field": "sequence_no", "align": "left"},
                    {"name": "type", "label": "類型 (Request/Process/Response)", "field": "type", "align": "left"},
                    {"name": "description", "label": "說明", "field": "description", "align": "left"},
                ],
                rows=[],
            ).props("flat bordered dense row-key=id").classes("w-full max-h-[32vh] overflow-y-auto")

        # --------------------------------------------------------
        # 右側：AI 產生（只留一鍵全部生成）
        # --------------------------------------------------------
        with ui.card().classes("col-span-1 p-5 bg-white rounded-xl shadow-md flex flex-col gap-4"):
            ui.label("🤖 AI 產生三段式事件列表").classes("text-lg font-bold text-gray-800")

            ui.label(
                "- 會依據專案內所有 Use Case Detail 自動拆解事件\n"
                "- 建議先在上一頁確認 Detail 已整理好，再來這裡生成\n"
                "- 本頁僅保留『一鍵產生全部 Use Case』，生成後可用下拉選單檢視與匯出"
            ).classes("text-sm text-gray-600 whitespace-pre-line")

            ui.button(
                "⚙️ 一鍵為全部 Use Case 產生事件列表（AI）",
                color="secondary",
                on_click=_generate_for_all_usecases,
            ).classes("mt-2")