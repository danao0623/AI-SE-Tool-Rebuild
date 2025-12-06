# views/usecase_and_actor_view.py

from nicegui import ui, app
from flow_controllers.usecase_actor_flow import UsecaseActorFlowController


class State:
    """頁面狀態容器"""
    actors_rows: list[dict] = []
    usecases_rows_full: list[dict] = []
    actors_grid = None
    usecase_grid = None
    current_actor_name: str | None = None
    loading: bool = False


def usecase_actor_page() -> None:
    """專案案例管理頁面（Actor + UseCase）"""

    # 檢查是否已在上一頁選好專案
    current_project = app.storage.user.get("current_project")
    if not current_project:
        with ui.column().classes(
            "w-full h-screen items-center justify-center bg-gray-50 p-8 gap-4"
        ):
            ui.label("專案案例管理").classes("text-2xl font-bold text-red-600")
            ui.label("尚未選擇專案，請先回到「專案管理」頁面選擇一個專案。")
            ui.button(
                "回到專案管理",
                color="primary",
                on_click=lambda: ui.navigate.to("/project"),
            )
        return

    # ======================= 事件函式 =======================

    async def generate_from_ai() -> None:
        """呼叫 FlowController → Agent 產生 Actors + UseCases"""
        if State.loading:
            return
        State.loading = True

        # 會回傳一個 notification 物件，等下要手動關掉
        notice = ui.notify(
            "正在呼叫 AI 產生 Actor 與 Use Case…", type="ongoing", position="top"
        )

        try:
            result = await UsecaseActorFlowController.generate_for_current_project()

            # --- 錯誤 / 空結果處理 ---
            if not result.get("ok"):
                reason = result.get("reason", "unknown")
                msg = "AI 產生失敗，請稍後再試一次。"

                if reason == "no_project":
                    msg = "尚未選擇專案，請先到「專案管理」頁面建立或選擇專案。"
                elif reason == "empty_response":
                    msg = "AI 沒有回傳任何 Actor / Use Case 資料（可能是 API 配額已用完），請稍後再試一次。"

                ui.notify(msg, type="negative", position="top", timeout=5000)

                # 清空舊資料，避免畫面殘留之前的結果
                clear_result()
                return

            # --- 正常成功情況 ---
            State.actors_rows = result.get("actors_rows", []) or []
            State.usecases_rows_full = result.get("usecases_rows", []) or []

            # 更新 Actors Grid
            if State.actors_grid is not None:
                State.actors_grid.options["rowData"] = State.actors_rows
                State.actors_grid.update()

            # 預設選中第一個 Actor，並過濾 Use Case
            if State.actors_rows:
                first_name = State.actors_rows[0].get("名稱", "")
                State.current_actor_name = first_name
                _update_usecase_grid_by_actor(first_name)
            else:
                State.current_actor_name = None
                _update_usecase_grid_by_actor(None)

            ui.notify("AI 產生完成！", type="positive", position="top", timeout=2500)

        except Exception as e:  # noqa: BLE001
            ui.notify(
                f"AI 產生發生例外：{e}", type="negative", position="top", timeout=5000
            )
        finally:
            # 不管成功 / 失敗 / 例外，都關掉「正在呼叫」的 ongoing 通知
            try:
                notice.close()
            except Exception:
                pass
            State.loading = False

    def clear_result() -> None:
        """清空目前的 Actors / UseCases"""
        State.actors_rows = []
        State.usecases_rows_full = []
        State.current_actor_name = None

        if State.actors_grid is not None:
            State.actors_grid.options["rowData"] = []
            State.actors_grid.update()

        if State.usecase_grid is not None:
            State.usecase_grid.options["rowData"] = []
            State.usecase_grid.update()

    def _update_usecase_grid_by_actor(actor_name: str | None) -> None:
        """依選取的 Actor 名稱過濾 UseCase 表格內容"""
        if State.usecase_grid is None:
            return

        if not actor_name:
            filtered: list[dict] = []
        else:
            filtered = [
                row
                for row in State.usecases_rows_full
                if row.get("主要角色") == actor_name
            ]

        State.usecase_grid.options["rowData"] = filtered
        State.usecase_grid.update()

    def on_actor_selection(event) -> None:  # noqa: ARG001
        """當使用者在 Actors Grid 裡選取某一列時觸發"""
        grid = State.actors_grid
        if grid is None:
            _update_usecase_grid_by_actor(None)
            return

        rows = grid.get_selected_rows()
        if not rows:
            State.current_actor_name = None
            _update_usecase_grid_by_actor(None)
            return

        row = rows[0]
        actor_name = row.get("名稱")
        State.current_actor_name = actor_name
        _update_usecase_grid_by_actor(actor_name)

    # ======================= 版面配置 =======================

    with ui.element().classes(
        "grid grid-cols-4 gap-6 w-full h-screen bg-gray-50 p-6 items-start"
    ):
        # ---------- 左欄：專案流程 ---------- #
        with ui.card().classes(
            "col-span-1 p-5 bg-white rounded-xl shadow-md h-full flex flex-col justify-between"
        ):
            ui.label("🧭 專案流程").classes("text-lg font-bold mb-3 text-gray-800")

            # 正確設定 Stepper：第一格「專案管理」已完成，第二格「專案案例管理」為目前所在
            with ui.stepper().props("vertical").classes("w-full") as stepper:
                step_project = ui.step("專案管理")
                step_usecase = ui.step("專案案例管理")     # ← 這一格就是你現在這頁
                ui.step("使用案例明細").props("name=3")
                ui.step("專案物件瀏覽").props("name=4")
                ui.step("程式碼生成").props("name=5")
            step_project.props("done")
            
            stepper.value = step_usecase
            
            with ui.row().classes("w-full gap-2 mt-4"):
                ui.button(
                    "上一步",
                    color="grey",
                    on_click=lambda: ui.navigate.to("/project"),
                ).classes("flex-1")
                ui.button(
                    "下一步",
                    color="blue",
                    on_click=lambda: ui.notify("下一步頁面尚未實作"),
                ).classes("flex-1")

        # ---------- 中欄：主內容（專案資訊 + 表格） ---------- #
        with ui.card().classes(
            "col-span-2 p-6 bg-white rounded-xl shadow-md flex flex-col gap-4 overflow-y-auto"
        ):
            # 標題換成「專案案例管理」
            ui.label("專案案例管理").classes("text-2xl font-bold text-indigo-700")

            # 專案資訊區塊
            ui.label(f"目前專案：{current_project.get('name', '未命名專案')}").classes(
                "text-base font-semibold text-gray-800 mt-2"
            )
            ui.label(f"專案 ID：{current_project.get('id')}").classes(
                "text-sm text-gray-600 mt-1"
            )
            ui.label(
                f"專案描述：{current_project.get('description') or '（尚未填寫）'}"
            ).classes("mt-2 text-sm text-gray-700")
            ui.label(
                f"系統架構：{current_project.get('architecture') or '（尚未填寫）'}"
            ).classes("mt-1 text-sm text-gray-700")

            # 表格：Actors
            ui.separator().classes("my-3")
            ui.label("Actors（系統角色）").classes("text-lg font-semibold")

            State.actors_grid = ui.aggrid(
                {
                    "columnDefs": [
                        {
                            "headerName": "名稱",
                            "field": "名稱",
                            "checkboxSelection": True,
                        },
                        {
                            "headerName": "說明",
                            "field": "說明",
                            "flex": 2,
                            "wrapText": True,
                            "autoHeight": True,
                        },
                    ],
                    "rowSelection": "single",
                    "domLayout": "autoHeight",
                }
            ).classes("w-full bg-white")
            State.actors_grid.on("selectionChanged", on_actor_selection)

            # 表格：Use Cases
            ui.label("Use Case（使用案例）").classes("text-lg font-semibold mt-4")

            State.usecase_grid = ui.aggrid(
                {
                    "columnDefs": [
                        {
                            "headerName": "使用案例名稱",
                            "field": "使用案例名稱",
                            "width": 220,
                        },
                        {
                            "headerName": "概述",
                            "field": "概述",
                            "flex": 2,
                            "wrapText": True,
                            "autoHeight": True,
                        },
                        {
                            "headerName": "主要角色",
                            "field": "主要角色",
                            "width": 160,
                        },
                        {
                            "headerName": "其他角色",
                            "field": "其他角色",
                            "flex": 1,
                        },
                    ],
                    "rowSelection": "single",
                    "domLayout": "autoHeight",
                }
            ).classes("w-full bg-white")

        # ---------- 右欄：AI 操作與說明 ---------- #
        with ui.card().classes(
            "col-span-1 p-5 bg-white rounded-xl shadow-md flex flex-col gap-4"
        ):
            ui.label("🤖 AI 產生").classes("text-lg font-bold text-gray-800")

            ui.button(
                "生成 ACTOR 與 USECASE",
                color="primary",
                on_click=generate_from_ai,
            ).classes("w-full")
            ui.button(
                "清空目前結果",
                color="red",
                on_click=clear_result,
            ).classes("w-full")

            ui.separator().classes("my-2")

            ui.label("說明").classes("font-semibold")
            with ui.column().classes("text-sm text-gray-700 gap-1"):
                ui.label("① 左側流程目前停在「專案案例管理」。")
                ui.label("② 點選上方 Actors 表格中的角色，下方會顯示該角色的使用案例。")
                ui.label("③ 重新按「生成 ACTOR 與 USECASE」會覆蓋原本的 AI 結果。")