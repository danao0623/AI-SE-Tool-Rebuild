from __future__ import annotations
from typing import Dict, Optional

from nicegui import ui, app

from flow_controllers.usecase_detail_flow import UsecaseDetailFlowController


# 全域元件參照（方便在事件處理裡更新）
usecase_select = None

normal_process_area = None
exception_process_area = None
trigger_condition_area = None
pre_condition_area = None
post_condition_area = None

# 目前選擇的 UseCase id
current_usecase_id: Optional[int] = None


# ============================================================
# 後端事件處理
# ============================================================
async def _load_usecases_and_first_detail() -> None:
    """頁面載入時：載入 UseCase 清單，並預設選第一筆載入 Detail"""
    global usecase_select, current_usecase_id

    try:
        rows = await UsecaseDetailFlowController.list_usecases_for_current_project()
    except RuntimeError as e:
        ui.notify("尚未選擇專案，請先回到專案管理頁面。", type='warning', timeout=4000)
        print(f"[UsecaseDetail] list_usecases_for_current_project error: {e}")
        return

    if usecase_select is None:
        # 頁面尚未完成初始化（理論上不會發生），保險檢查
        return

    if not rows:
        usecase_select.options = {}
        usecase_select.value = None
        usecase_select.update()
        # 清空右側欄位
        _set_detail_fields(
            normal="",
            exception="",
            trigger="",
            pre="",
            post="",
        )
        return

    # 建立 select options：值用 id（字串），顯示文字用「id - name」
    options: Dict[str, str] = {
        str(r["id"]): f'{r["id"]} - {r["name"]}' for r in rows if r.get("id") is not None
    }

    usecase_select.options = options

    # 預設選第一筆
    first = rows[0]
    first_id_str = str(first["id"])
    current_usecase_id = int(first["id"])
    usecase_select.value = first_id_str

    usecase_select.update()

    # 同步載入第一筆 Detail
    await _load_detail(current_usecase_id)


async def _load_detail(usecase_id: int) -> None:
    """載入指定 UseCase 的 Detail 值到右側欄位"""
    global current_usecase_id
    current_usecase_id = usecase_id

    detail = await UsecaseDetailFlowController.load_detail(usecase_id)
    if not detail:
        _set_detail_fields(
            normal="",
            exception="",
            trigger="",
            pre="",
            post="",
        )
        return

    _set_detail_fields(
        normal=detail.get("normal_process", "") or "",
        exception=detail.get("exception_process", "") or "",
        trigger=detail.get("trigger_condition", "") or "",
        pre=detail.get("pre_condition", "") or "",
        post=detail.get("post_condition", "") or "",
    )


def _set_detail_fields(
    *,
    normal: str,
    exception: str,
    trigger: str,
    pre: str,
    post: str,
) -> None:
    """統一設定五個欄位的值並更新 UI"""
    if normal_process_area is not None:
        normal_process_area.value = normal
        normal_process_area.update()

    if exception_process_area is not None:
        exception_process_area.value = exception
        exception_process_area.update()

    if trigger_condition_area is not None:
        trigger_condition_area.value = trigger
        trigger_condition_area.update()

    if pre_condition_area is not None:
        pre_condition_area.value = pre
        pre_condition_area.update()

    if post_condition_area is not None:
        post_condition_area.value = post
        post_condition_area.update()


async def _on_usecase_select_change(event) -> None:
    """切換 UseCase 下拉選單時觸發"""
    value = event.value
    if not value:
        return

    try:
        usecase_id = int(value)
    except ValueError:
        return

    await _load_detail(usecase_id)


async def _save_current_detail() -> None:
    """將目前畫面上的 Detail 內容寫回資料庫"""
    if current_usecase_id is None:
        ui.notify("請先選擇一個 Use Case", type='warning')
        return

    await UsecaseDetailFlowController.save_detail(
        usecase_id=current_usecase_id,
        normal_process=normal_process_area.value or "",
        exception_process=exception_process_area.value or "",
        trigger_condition=trigger_condition_area.value or "",
        pre_condition=pre_condition_area.value or "",
        post_condition=post_condition_area.value or "",
    )
    ui.notify("Use Case 明細已儲存", type='positive', timeout=2500)


async def _generate_all_details_by_ai() -> None:
    """
    呼叫 Flow，一鍵產生目前專案底下所有 UseCase 的 Detail。
    產生完成後，會重新載入目前選取的那一筆。
    """
    ui.notify("正在產生 Use Case Detail（AI）…", type='info', timeout=2000)

    result = await UsecaseDetailFlowController.generate_for_current_project()
    if not result.get("ok", False):
        reason = result.get("reason", "未知錯誤")
        if reason == "no_project":
            msg = "尚未選擇專案，請先回到「專案管理」頁面。"
        elif reason == "no_project_id":
            msg = "目前專案沒有 ID，無法產生 Use Case Detail。"
        else:
            msg = f"產生失敗：{reason}"
        ui.notify(msg, type='negative', timeout=4000)
        return

    updated = result.get("updated_count", 0)
    total = result.get("usecase_count", 0)
    ui.notify(
        f"AI 已為 {updated}/{total} 個 Use Case 產生 / 更新 Detail",
        type='positive',
        timeout=3000,
    )

    if current_usecase_id is not None:
        await _load_detail(current_usecase_id)


def _clear_fields_only() -> None:
    """只清空畫面上的資料，不寫回資料庫"""
    _set_detail_fields(
        normal="",
        exception="",
        trigger="",
        pre="",
        post="",
    )


# ============================================================
# Page View 本體（保持與第二步畫面風格一致）
# ============================================================
def usecase_detail_page() -> None:
    """
    使用案例明細頁面：
    - 左側：流程 Stepper + 上一頁 / 下一步按鈕
    - 中間：Use Case 下拉 + Detail 編輯欄位
    - 右側：AI 一鍵產生說明與操作區
    """

    current_project = app.storage.user.get("current_project")
    if not current_project:
        # 與 usecase_and_actor_page 相同的「尚未選專案」風格
        with ui.column().classes(
            "w-full h-screen items-center justify-center bg-gray-50 p-8 gap-4"
        ):
            ui.label("使用案例明細").classes("text-2xl font-bold text-red-600")
            ui.label("尚未選擇專案，請先回到「專案管理」頁面選擇一個專案。")
            ui.button(
                "回到專案管理",
                color="primary",
                on_click=lambda: ui.navigate.to("/project"),
            )
        return

    global usecase_select, normal_process_area, exception_process_area, trigger_condition_area, pre_condition_area, post_condition_area

    # 頁面載入後，用 timer 非同步載入 UseCase 清單與第一筆 Detail
    ui.timer(0.1, _load_usecases_and_first_detail, once=True)

    with ui.element().classes(
        "grid grid-cols-4 gap-6 w-full h-screen bg-gray-50 p-6 items-start"
    ):
        # --------------------------------------------------------
        # 左側流程 Stepper（維持與 Actor/UseCase 頁面一致風格）
        # --------------------------------------------------------
        with ui.card().classes(
            "col-span-1 p-5 bg-white rounded-xl shadow-md h-full flex flex-col justify-between"
        ):
            ui.label("🧭 專案流程").classes("text-lg font-bold mb-3 text-gray-800")

            with ui.stepper(value=3).props('vertical').classes('w-full'):
                ui.step('專案管理').props('name=1 done')
                ui.step('專案案例管理').props('name=2 done')
                ui.step('使用案例明細').props('name=3 ')
                ui.step('三段式事件列表').props('name=4')
                ui.step('專案物件瀏覽').props('name=5')
                ui.step('UML 圖生成').props('name=6')
                ui.step('介面藍圖').props('name=7')
                ui.step('產生程式碼').props('name=8')
            
            with ui.row().classes("w-full justify-between mt-4"):
                ui.button(
                    "上一頁（Actor / UseCase）",
                    color="grey",
                    on_click=lambda: ui.navigate.to("/usecase_actor"),
                ).props("outline")

                ui.button(
                    "下一步（三段式事件列表）",
                    color="primary",
                    on_click=lambda: ui.navigate.to("/event_summary"),
                )

        # --------------------------------------------------------
        # 中間：Use Case 下拉 + Detail 編輯
        # --------------------------------------------------------
        with ui.card().classes(
            "col-span-2 p-6 bg-white rounded-xl shadow-md flex flex-col gap-4 h-full"
        ):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("使用案例明細（Use Case Detail）").classes(
                    "text-2xl font-bold text-gray-800"
                )
                ui.label(
                    f"目前專案：{current_project.get('name', '')}"
                ).classes("text-sm text-gray-600")

            ui.label(
                "說明：AI 會根據 Actor 與 Use Case 的描述自動產生一版 Detail，"
                "但你仍可以在下方五個欄位手動增刪步驟與內容，按下「儲存」寫回資料庫。"
            ).classes("text-sm text-gray-600")

            ui.separator().classes("my-2")

            # --- Use Case 下拉 ---
            with ui.row().classes("items-center w-full"):
                ui.label("選擇 Use Case：").classes("font-semibold")
                usecase_select = (
                    ui.select(
                        label=None,
                        options={},  # 實際內容由 _load_usecases_and_first_detail 動態填入
                        on_change=_on_usecase_select_change,
                    )
                    .classes("w-80")
                    .props("outlined dense")
                )

            ui.separator().classes("my-2")

           # ---------------- 五大欄位 ----------------
            with ui.card().classes('w-full grow max-h-[65vh] overflow-y-auto mt-2 p-3'):
                with ui.row().classes('w-full gap-4 flex-wrap'):
                    # 左側：正常 / 例外
                    with ui.column().classes('w-full lg:w-1/2 gap-2'):
                        global normal_process_area, exception_process_area

                        normal_process_area = ui.textarea(
                            '正常程序（Normal Flow）',
                            placeholder='1. 使用者...\n2. 系統...',
                        ).props('rows=4 autogrow').classes('w-full')

                        exception_process_area = ui.textarea(
                            '例外程序（Exception / Alternate Flow）',
                            placeholder='1. 若登入失敗...\n2. 若資料庫錯誤...',
                        ).props('rows=4 autogrow').classes('w-full')

                    # 右側：觸發 / 前置 / 後置
                    with ui.column().classes('w-full lg:w-1/2 gap-2'):
                        global trigger_condition_area, pre_condition_area, post_condition_area

                        trigger_condition_area = ui.textarea(
                            '觸發條件（Trigger）',
                            placeholder='例如：學生希望查詢課程列表...',
                        ).props('rows=3 autogrow').classes('w-full')

                        pre_condition_area = ui.textarea(
                            '前置條件（Pre-condition）',
                            placeholder='例如：學生已成功登入系統...',
                        ).props('rows=3 autogrow').classes('w-full')

                        post_condition_area = ui.textarea(
                            '後置條件（Post-condition）',
                            placeholder='例如：學生的選課結果已更新...',
                        ).props('rows=3 autogrow').classes('w-full')
            ui.separator().classes("my-2")

            with ui.row().classes("justify-end w-full gap-3"):
                ui.button(
                    "清空畫面（不寫回 DB）",
                    color="grey",
                    on_click=_clear_fields_only,
                ).props("outline")

                ui.button(
                    "💾 儲存目前 Use Case Detail",
                    color="primary",
                    on_click=_save_current_detail,
                )

        # --------------------------------------------------------
        # 右側：AI 操作區
        # --------------------------------------------------------
        with ui.card().classes(
            "col-span-1 p-5 bg-white rounded-xl shadow-md flex flex-col gap-4"
        ):
            ui.label("🤖 AI 輔助產生 Use Case Detail").classes(
                "text-lg font-bold text-gray-800"
            )

            ui.label(
                "- 會針對目前專案底下所有 Use Case 產生 / 覆蓋 Detail\n"
                "- 產生後仍可在中間欄位手動修改，再按「儲存」\n"
                "- 建議先確認 Actor / Use Case 已整理完畢再使用"
            ).classes("text-sm text-gray-600 whitespace-pre-line")

            ui.separator()

            ui.button(
                "🧠 一鍵產生 / 更新全部 Use Case Detail（AI）",
                color="primary",
                on_click=_generate_all_details_by_ai,
            )