from typing import Any, Dict, List
import asyncio

from nicegui import ui, app
from flow_controllers.usecase_actor_flow import UsecaseActorFlowController


class State:
    """頁面狀態 container"""
    # 中間 Grid：目前專案中「已選擇／準備存進資料庫」的資料
    actors_rows: List[Dict[str, Any]] = []
    usecases_rows_full: List[Dict[str, Any]] = []

    # 右側候選區：AI 剛產生、尚未匯入的資料
    candidate_actors: List[Dict[str, Any]] = []
    candidate_usecases: List[Dict[str, Any]] = []
    candidate_actor_checkboxes: Dict[str, Any] = {}
    candidate_usecase_checkboxes: Dict[tuple, Any] = {}
    candidate_container = None

    # Grid 元件與狀態
    actors_grid = None
    usecase_grid = None
    current_actor_name: str | None = None
    loading: bool = False


def usecase_actor_page() -> None:
    """專案案例管理頁面（Actor + UseCase）"""

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

    # ======================================================
    # 小工具
    # ======================================================
    def clear_result() -> None:
        """清空畫面資料（中間 Grid，不動資料庫 & 候選區）"""
        State.actors_rows = []
        State.usecases_rows_full = []
        State.current_actor_name = None

        if State.actors_grid is not None:
            State.actors_grid.options["rowData"] = []
            State.actors_grid.update()

        if State.usecase_grid is not None:
            State.usecase_grid.options["rowData"] = []
            State.usecase_grid.update()

    def render_candidates() -> None:
        """根據 State.candidate_* 重畫右側候選區"""
        container = State.candidate_container
        if container is None:
            return

        container.clear()
        State.candidate_actor_checkboxes = {}
        State.candidate_usecase_checkboxes = {}

        with container:
            if not State.candidate_actors:
                ui.label(
                    "目前尚無 AI 產生的候選角色，請先點上方「生成候選」按鈕。"
                ).classes("text-sm text-gray-500")
                return

            ui.label(
                "AI 產生的候選角色與使用案例（勾選後按『匯入』）"
            ).classes("text-sm font-semibold mb-2")

            for actor in State.candidate_actors:
                name = (actor.get("名稱") or "").strip()
                desc = (actor.get("說明") or "").strip()
                if not name:
                    continue

                cb = ui.checkbox(name).classes("text-sm font-medium")
                State.candidate_actor_checkboxes[name] = cb

                if desc:
                    ui.label(desc).classes("text-xs text-gray-600 ml-6")

                related_ucs = [
                    u
                    for u in State.candidate_usecases
                    if (u.get("主要角色") or "").strip() == name
                ]
                for u in related_ucs:
                    title = (u.get("使用案例名稱") or "").strip()
                    summary = (u.get("概述") or "").strip()
                    if not title:
                        continue
                    key = (name, title)
                    uc_cb = ui.checkbox(
                        f"- {title}：{summary}"
                    ).classes("text-xs text-gray-700 ml-8")
                    State.candidate_usecase_checkboxes[key] = uc_cb

    def _update_usecase_grid_by_actor(actor_name: str | None) -> None:
        """依目前選擇的 Actor 來更新下方 UseCase Grid"""
        if State.usecase_grid is None:
            return

        if not State.usecases_rows_full:
            rows: list[dict] = []
        else:
            if not actor_name:
                rows = State.usecases_rows_full
            else:
                rows = [
                    r
                    for r in State.usecases_rows_full
                    if (r.get("主要角色") or "").strip()
                    == (actor_name or "").strip()
                ]
                # 如果完全對不到，先顯示全部，避免你以為壞掉
                if not rows:
                    rows = State.usecases_rows_full

        State.usecase_grid.options["rowData"] = rows
        State.usecase_grid.update()

    # ======================================================
    # 事件處理
    # ======================================================
    async def on_actor_selection(event) -> None:  # noqa: ARG001
        """選了某一個 Actor"""
        grid = State.actors_grid
        if grid is None:
            _update_usecase_grid_by_actor(None)
            return

        rows = await grid.get_selected_rows()
        if not rows:
            State.current_actor_name = None
            _update_usecase_grid_by_actor(None)
            return

        actor_name = rows[0].get("名稱")
        State.current_actor_name = actor_name
        _update_usecase_grid_by_actor(actor_name)

    async def load_from_db() -> None:
        """從 DB 載入目前專案資料"""
        if State.loading:
            return
        State.loading = True
        try:
            result = await UsecaseActorFlowController.load_from_db_for_current_project()
            if not result.get("ok"):
                reason = result.get("reason")
                if reason == "no_project":
                    ui.notify("尚未選擇專案，無法載入資料", type="warning")
                elif reason == "no_project_id":
                    ui.notify("目前專案沒有 ID，無法載入資料", type="warning")
                else:
                    ui.notify("載入資料失敗", type="negative")
                return

            State.actors_rows = result.get("actors_rows", []) or []
            State.usecases_rows_full = result.get("usecases_rows", []) or []

            if State.actors_grid is not None:
                State.actors_grid.options["rowData"] = State.actors_rows
                State.actors_grid.update()

            # 預設選第一個 Actor
            if State.actors_rows:
                first = State.actors_rows[0].get("名稱", "")
                State.current_actor_name = first
                _update_usecase_grid_by_actor(first)
            else:
                State.current_actor_name = None
                _update_usecase_grid_by_actor(None)
        finally:
            State.loading = False

    async def generate_from_ai() -> None:
        """呼叫 AI 產生 Actor + UseCase，結果先放在右側候選區"""
        if State.loading:
            return
        State.loading = True
        notice = ui.notify(
            "正在呼叫 AI 產生 Actor 與 Use Case…",  type="info", timeout=1500, position="top"
        )
        try:
            result = await UsecaseActorFlowController.generate_for_current_project()

            if not result.get("ok"):
                reason = result.get("reason", "unknown")
                if reason == "no_project":
                    msg = "尚未選擇專案，請先到「專案管理」建立或選擇專案。"
                elif reason == "no_project_id":
                    msg = "目前專案沒有 ID，請檢查專案是否已成功儲存。"
                elif reason == "empty_response":
                    msg = "AI 沒有回傳任何 Actor / Use Case，請稍後重試。"
                else:
                    msg = "AI 產生失敗，請稍後再試一次。"

                ui.notify(msg, type="negative", position="top", timeout=5000)
                # 若失敗，清空候選區即可；中間 Grid 保持不動
                State.candidate_actors = []
                State.candidate_usecases = []
                render_candidates()
                return

            # 將 AI 回傳結果放到「候選區」，不直接覆蓋目前 Grid / DB
            State.candidate_actors = result.get("actors_rows", []) or []
            State.candidate_usecases = result.get("usecases_rows", []) or []

            render_candidates()

            ui.notify(
                "AI 產生完成！請在右側勾選想要的角色或個別 Use Case，按下『匯入』後才會加入中間表格。",
                type="positive",
                position="top",
                timeout=3500,
            )
        except Exception as e:  # noqa: BLE001
            ui.notify(
                f"AI 產生發生例外：{e}", type="negative", position="top", timeout=5000
            )
        finally:
            try:
                notice.close()
            except Exception:
                pass
            State.loading = False

    async def regenerate_selected_actors() -> None:
        """重新生成勾選的 Actor（連同該 Actor 的所有 UseCases 一起重生）"""
        if State.loading:
            return

        grid = State.actors_grid
        if grid is None:
            return

        selected = await grid.get_selected_rows()
        if not selected:
            ui.notify("請先勾選要重新生成的 Actor", type="warning")
            return

        old_actor_row = selected[0]
        old_actor_name = (old_actor_row.get("名稱") or "").strip()

        # 收集舊的 UseCases
        related_usecases = [
            {
                "name": r.get("使用案例名稱", ""),
                "summary": r.get("概述", ""),
            }
            for r in State.usecases_rows_full
            if (r.get("主要角色") or "").strip() == old_actor_name
        ]

        State.loading = True
        notice = ui.notify(
            f"正在重新生成 Actor「{old_actor_name}」及其所有 Use Case…",
            type="info", timeout=1500,
            position="top",
        )
        try:
            result = await UsecaseActorFlowController.regenerate_actor_for_current_project(
                old_actor_row=old_actor_row,
                old_usecases_for_actor=related_usecases,
            )

            if not result.get("ok"):
                ui.notify("重生 Actor 失敗", type="negative")
                return

            new_actor_row = result["actor_row"]
            new_usecases_rows = result["usecases_rows"]
            new_actor_name = new_actor_row.get("名稱", old_actor_name)

            # 1) 更新 Actors 列表
            for i, row in enumerate(State.actors_rows):
                if (row.get("名稱") or "").strip() == old_actor_name:
                    State.actors_rows[i] = new_actor_row
                    break

            # 2) 移除舊 Actor 的 UseCases，加入新的
            State.usecases_rows_full = [
                r
                for r in State.usecases_rows_full
                if (r.get("主要角色") or "").strip() != old_actor_name
            ]
            State.usecases_rows_full.extend(new_usecases_rows)

            # 3) 更新目前 Actor，重畫 Grid
            State.current_actor_name = new_actor_name

            if State.actors_grid is not None:
                State.actors_grid.options["rowData"] = State.actors_rows
                State.actors_grid.update()

            _update_usecase_grid_by_actor(new_actor_name)

            ui.notify(
                f"已重新生成 Actor「{new_actor_name}」與其 Use Cases！",
                type="positive",
                position="top",
                timeout=2500,
            )
        except Exception as e:  # noqa: BLE001
            ui.notify(
                f"重生 Actor 時發生例外：{e}",
                type="negative",
                position="top",
                timeout=5000,
            )
        finally:
            try:
                notice.close()
            except Exception:
                pass
            State.loading = False

    async def regenerate_selected_usecases() -> None:
        """重新生成勾選的 UseCase"""
        if State.loading:
            return

        grid = State.usecase_grid
        if grid is None:
            return

        selected = await grid.get_selected_rows()
        if not selected:
            ui.notify("請先勾選要重新生成的 Use Case", type="warning")
            return

        if not State.current_actor_name:
            ui.notify("請先在上方選一個 Actor（主要角色）", type="warning")
            return

        State.loading = True
        notice = ui.notify(
            "正在重新生成勾選的 Use Case…", type="info", timeout=1500
        )

        try:
            for old_row in selected:
                old_uc = {
                    "name": old_row.get("使用案例名稱", ""),
                    "summary": old_row.get("概述", ""),
                }
                result = await UsecaseActorFlowController.regenerate_usecase_for_current_project(
                    actor_name=State.current_actor_name,
                    old_usecase=old_uc,
                )
                if not result.get("ok"):
                    continue

                new_row = result["row"]

                for i, row in enumerate(State.usecases_rows_full):
                    if (
                        row.get("使用案例名稱")
                        == old_row.get("使用案例名稱")
                        and row.get("主要角色") == old_row.get("主要角色")
                    ):
                        State.usecases_rows_full[i] = new_row
                        break

            _update_usecase_grid_by_actor(State.current_actor_name)
            ui.notify(
                "已重新生成勾選的 Use Case！",
                type="positive",
                position="top",
                timeout=2500,
            )
        except Exception as e:  # noqa: BLE001
            ui.notify(
                f"重新生成 Use Case 時發生例外：{e}",
                type="negative",
                position="top",
                timeout=5000,
            )
        finally:
            try:
                notice.close()
            except Exception:
                pass
            State.loading = False

    async def delete_selected_actors() -> None:
        """從中間 Actors Grid 刪除勾選的 Actor（並連帶刪除其 UseCases）"""
        grid = State.actors_grid
        if grid is None:
            return

        selected = await grid.get_selected_rows()
        if not selected:
            ui.notify("請先在上方表格勾選要刪除的 Actor", type="warning")
            return

        names = [(row.get("名稱") or "").strip() for row in selected]

        # 刪除 Actors
        State.actors_rows = [
            row
            for row in State.actors_rows
            if (row.get("名稱") or "").strip() not in names
        ]

        # 連帶刪除其 UseCases
        State.usecases_rows_full = [
            uc
            for uc in State.usecases_rows_full
            if (uc.get("主要角色") or "").strip() not in names
        ]

        if State.actors_grid is not None:
            State.actors_grid.options["rowData"] = State.actors_rows
            State.actors_grid.update()

        # 重新選擇目前 Actor
        if State.actors_rows:
            State.current_actor_name = (State.actors_rows[0].get("名稱") or "").strip()
        else:
            State.current_actor_name = None
        _update_usecase_grid_by_actor(State.current_actor_name)

        ui.notify(
            "已從中間表格刪除勾選的 Actor（以及其所有 Use Case）。",
            type="positive",
            position="top",
            timeout=2500,
        )

    async def delete_selected_usecases() -> None:
        """從中間 UseCase Grid 刪除勾選的 UseCase"""
        grid = State.usecase_grid
        if grid is None:
            return

        selected = await grid.get_selected_rows()
        if not selected:
            ui.notify("請先在下方表格勾選要刪除的 Use Case", type="warning")
            return

        targets = {
            ((row.get("使用案例名稱") or "").strip(), (row.get("主要角色") or "").strip())
            for row in selected
        }

        State.usecases_rows_full = [
            uc
            for uc in State.usecases_rows_full
            if (
                (uc.get("使用案例名稱") or "").strip(),
                (uc.get("主要角色") or "").strip(),
            )
            not in targets
        ]

        _update_usecase_grid_by_actor(State.current_actor_name)

        ui.notify(
            "已從中間表格刪除勾選的 Use Case。",
            type="positive",
            position="top",
            timeout=2500,
        )

    def import_selected_candidates() -> None:
        """將右側勾選的候選 Actor / UseCase 匯入中間 Grid（只在記憶體）"""

        # 如果候選區本身就沒有資料
        if not State.candidate_actor_checkboxes and not State.candidate_usecase_checkboxes:
            ui.notify("目前沒有可匯入的候選資料，請先讓 AI 產生。", type="warning")
            return

        # 右側有打勾的 Actor
        selected_actor_names = [
            name
            for name, cb in State.candidate_actor_checkboxes.items()
            if cb.value
        ]

        # 右側有打勾的 Use Case（key 是 (actor_name, uc_name)）
        selected_usecase_keys = [
            key
            for key, cb in State.candidate_usecase_checkboxes.items()
            if cb.value
        ]

        if not selected_actor_names and not selected_usecase_keys:
            ui.notify("請先在右側勾選至少一個角色或使用案例。", type="warning")
            return

        # 1) 決定哪些 Actor 一定要被匯入
        actors_to_import: set[str] = set(selected_actor_names)

        # 只勾 Use Case 但沒勾 Actor，也要把對應 Actor 匯入
        for actor_name, _ in selected_usecase_keys:
            actors_to_import.add(actor_name)

        # 匯入必要的 Actors（如果中間 Grid 尚未有）
        for actor_name in actors_to_import:
            if not any(
                (row.get("名稱") or "").strip() == actor_name
                for row in State.actors_rows
            ):
                actor = next(
                    (
                        a
                        for a in State.candidate_actors
                        if (a.get("名稱") or "").strip() == actor_name
                    ),
                    None,
                )
                if actor:
                    State.actors_rows.append(actor)

        # 2) 決定要匯入哪些 Use Case
        # 規則：只匯入「有勾 Use Case checkbox」的那幾個
        for (actor_name, uc_name) in selected_usecase_keys:
            uc = next(
                (
                    u
                    for u in State.candidate_usecases
                    if (u.get("主要角色") or "").strip() == actor_name
                    and (u.get("使用案例名稱") or "").strip() == uc_name
                ),
                None,
            )
            if not uc:
                continue

            # 避免重複塞進中間 Grid
            exists = any(
                (row.get("使用案例名稱") == uc.get("使用案例名稱")
                 and row.get("主要角色") == uc.get("主要角色"))
                for row in State.usecases_rows_full
            )
            if not exists:
                State.usecases_rows_full.append(uc)

        # 3) 更新中間 Grid 顯示
        if State.actors_grid is not None:
            State.actors_grid.options["rowData"] = State.actors_rows
            State.actors_grid.update()

        # 決定要顯示哪一個 Actor 的 Use Case
        if selected_actor_names:
            first = selected_actor_names[0]
        elif selected_usecase_keys:
            first = selected_usecase_keys[0][0]
        else:
            first = None

        State.current_actor_name = first
        _update_usecase_grid_by_actor(first)

        ui.notify(
            "已將勾選的角色與使用案例匯入中間表格。",
            type="positive",
            position="top",
            timeout=3000,
        )

    async def save_to_db() -> None:
        """將目前 Grid 的結果存回資料庫（覆蓋目前專案的 Actor & UseCase）"""
        if State.loading:
            return

        if not State.actors_rows and not State.usecases_rows_full:
            ui.notify("目前沒有任何資料可儲存", type="warning")
            return

        State.loading = True
        notice = ui.notify(
            "正在將目前結果儲存到資料庫…", type="info", timeout=1500, position="top"
        )
        try:
            result = await UsecaseActorFlowController.save_current_to_db(
                actors_rows=State.actors_rows,
                usecases_rows=State.usecases_rows_full,
            )
            if not result.get("ok"):
                reason = result.get("reason")
                if reason == "no_project":
                    msg = "尚未選擇專案，無法儲存資料。"
                elif reason == "no_project_id":
                    msg = "目前專案沒有 ID，無法儲存資料。"
                else:
                    msg = "儲存失敗，請稍後再試一次。"
                ui.notify(msg, type="negative", position="top", timeout=5000)
                return

            ui.notify(
                f"儲存成功！新增 Actors：{result.get('actor_count', 0)} 筆，"
                f"Use Cases：{result.get('usecase_count', 0)} 筆。",
                type="positive",
                position="top",
                timeout=4000,
            )
        except Exception as e:  # noqa: BLE001
            ui.notify(
                f"儲存至資料庫時發生例外：{e}",
                type="negative",
                position="top",
                timeout=5000,
            )
        finally:
            try:
                notice.close()
            except Exception:
                pass
            State.loading = False

    # ======= 手動編輯：彈出式對話框 ========

    async def edit_selected_actor() -> None:
        """以對話框方式手動修改選取的 Actor"""
        grid = State.actors_grid
        if grid is None:
            return

        selected = await grid.get_selected_rows()
        if not selected:
            ui.notify("請先在上方表格勾選要編輯的 Actor", type="warning")
            return

        row = selected[0]
        old_name = (row.get("名稱") or "").strip()
        old_desc = row.get("說明") or ""

        with ui.dialog() as dialog, ui.card().classes("w-[480px]"):
            ui.label("編輯 Actor").classes("text-lg font-bold mb-2")
            name_input = ui.input("名稱", value=old_name).classes("w-full")
            desc_input = ui.textarea("說明", value=old_desc).classes("w-full h-40")

            with ui.row().classes("justify-end w-full mt-3"):
                ui.button("取消", on_click=dialog.close)

                def _save() -> None:
                    new_name = (name_input.value or "").strip()
                    new_desc = desc_input.value or ""
                    if not new_name:
                        ui.notify("Actor 名稱不可為空", type="warning")
                        return

                    # 更新 actors_rows
                    for r in State.actors_rows:
                        if (r.get("名稱") or "").strip() == old_name:
                            r["名稱"] = new_name
                            r["說明"] = new_desc
                    # 同步更新 UseCase 中的主要角色欄位
                    for uc in State.usecases_rows_full:
                        if (uc.get("主要角色") or "").strip() == old_name:
                            uc["主要角色"] = new_name

                    # 更新 Grid 顯示
                    if State.actors_grid is not None:
                        State.actors_grid.options["rowData"] = State.actors_rows
                        State.actors_grid.update()
                    _update_usecase_grid_by_actor(new_name)
                    State.current_actor_name = new_name

                    ui.notify("Actor 已更新", type="positive")
                    dialog.close()

                ui.button("儲存", color="primary", on_click=_save)

            dialog.open()

    async def edit_selected_usecase() -> None:
        """以對話框方式手動修改選取的 Use Case"""
        grid = State.usecase_grid
        if grid is None:
            return

        selected = await grid.get_selected_rows()
        if not selected:
            ui.notify("請先在下方表格勾選要編輯的 Use Case", type="warning")
            return

        row = selected[0]
        old_name = row.get("使用案例名稱") or ""
        old_summary = row.get("概述") or ""
        old_actor = row.get("主要角色") or State.current_actor_name or ""

        with ui.dialog() as dialog, ui.card().classes("w-[520px]"):
            ui.label("編輯 Use Case").classes("text-lg font-bold mb-2")
            name_input = ui.input("使用案例名稱", value=old_name).classes("w-full")
            summary_input = ui.textarea("概述", value=old_summary).classes(
                "w-full h-32"
            )
            actor_input = ui.input("主要角色", value=old_actor).classes("w-full")

            with ui.row().classes("justify-end w-full mt-3"):
                ui.button("取消", on_click=dialog.close)

                def _save() -> None:
                    new_name = (name_input.value or "").strip()
                    new_summary = summary_input.value or ""
                    new_actor = (actor_input.value or "").strip()
                    if not new_name:
                        ui.notify("Use Case 名稱不可為空", type="warning")
                        return
                    if not new_actor:
                        ui.notify("主要角色不可為空", type="warning")
                        return

                    # 更新 usecases_rows_full 中對應列
                    for uc in State.usecases_rows_full:
                        if (
                            uc.get("使用案例名稱") == old_name
                            and (uc.get("主要角色") or "") == old_actor
                        ):
                            uc["使用案例名稱"] = new_name
                            uc["概述"] = new_summary
                            uc["主要角色"] = new_actor

                    _update_usecase_grid_by_actor(State.current_actor_name)
                    ui.notify("Use Case 已更新", type="positive")
                    dialog.close()

                ui.button("儲存", color="primary", on_click=_save)

            dialog.open()

    # ======================================================
    # 版面配置
    # ======================================================
    with ui.element().classes(
        "grid grid-cols-4 gap-6 w-full h-screen bg-gray-50 p-6 items-start"
    ):
        # 左側流程 Stepper
        with ui.card().classes(
            "col-span-1 p-5 bg-white rounded-xl shadow-md h-full flex flex-col justify-between"
        ):
            ui.label("🧭 專案流程").classes("text-lg font-bold mb-3 text-gray-800")

            with ui.stepper(value=2).props('vertical').classes('w-full'):
                ui.step('專案管理').props('name=1 done')
                ui.step('專案案例管理').props('name=2 ')
                ui.step('使用案例明細').props('name=3')
                ui.step('三段式事件列表').props('name=4')
                ui.step('專案物件瀏覽').props('name=5')
                ui.step('UML 圖生成').props('name=6')
                ui.step('產生程式碼').props('name=7')

            with ui.row().classes("w-full justify-between mt-4"):
                ui.button(
                    "上一頁",
                    color="grey",
                    on_click=lambda: ui.navigate.to("/project"),
                ).props("outline")
                ui.button(
                    "下一步（使用案例明細）",
                    color="primary",
                    on_click=lambda: ui.navigate.to("/usecase_detail"),
                )

        # 中間主要內容：Actors & UseCases Grid
        with ui.card().classes(
            "col-span-2 p-6 bg-white rounded-xl shadow-md flex flex-col gap-4 h-full"
        ):
            ui.label("使用案例管理").classes("text-2xl font-bold text-gray-800")

            ui.label(
                "步驟二：由 AI 協助產生候選 Actor / Use Case，經由使用者勾選、調整與手動編輯後，形成正式的使用案例清單。"
            ).classes("text-sm text-gray-600 mb-2")

            ui.separator().classes("my-2")

            ui.label("Actors（系統角色）").classes("text-lg font-semibold")

            with ui.element().classes("w-full max-h-64 overflow-y-auto"):
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

            ui.label("Use Case（使用案例）").classes("text-lg font-semibold mt-4")
            with ui.element().classes("w-full max-h-72 overflow-y-auto"):
                State.usecase_grid = ui.aggrid(
                    {
                        "columnDefs": [
                            {
                                "headerName": "使用案例名稱",
                                "field": "使用案例名稱",
                                "width": 220,
                                "checkboxSelection": True,
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
                        ],
                        "rowSelection": "multiple",
                        "domLayout": "autoHeight",
                    }
                ).classes("w-full bg-white")

        # 右側操作區
        with ui.card().classes(
            "col-span-1 p-5 bg-white rounded-xl shadow-md flex flex-col gap-4"
        ):
            ui.label("🤖 AI 產生 / 資料操作").classes(
                "text-lg font-bold text-gray-800"
            )

            ui.button(
                "生成候選 ACTOR 與 USE CASE（AI）",
                color="primary",
                on_click=generate_from_ai,
            ).classes("w-full")

            ui.button(
                "清空目前結果（中間表格）",
                color="red",
                on_click=clear_result,
            ).classes("w-full")

            ui.separator().classes("my-2")

            ui.label("📥 從右側候選匯入").classes("font-semibold")
            ui.button(
                "匯入勾選的候選 ACTOR / USE CASE 到中間表格",
                color="secondary",
                on_click=import_selected_candidates,
            ).classes("w-full")

            State.candidate_container = ui.column().classes(
                "w-full max-h-80 overflow-y-auto border rounded-lg p-3 bg-gray-50"
            )

            ui.separator().classes("my-2")
            ui.label("🛠 再次生成 / 編輯").classes("font-semibold")

            ui.button(
                "重新生成勾選的 ACTOR",
                color="secondary",
                on_click=regenerate_selected_actors,
            ).classes("w-full")

            ui.button(
                "重新生成勾選的 USE CASE",
                color="secondary",
                on_click=regenerate_selected_usecases,
            ).classes("w-full")

            ui.button(
                "刪除勾選的 ACTOR（中間表格）",
                color="warning",
                on_click=delete_selected_actors,
            ).classes("w-full")

            ui.button(
                "刪除勾選的 USE CASE（中間表格）",
                color="warning",
                on_click=delete_selected_usecases,
            ).classes("w-full")

            ui.button(
                "編輯選取的 ACTOR（手動修改）",
                color="grey",
                on_click=edit_selected_actor,
            ).classes("w-full")

            ui.button(
                "編輯選取的 USE CASE（手動修改）",
                color="grey",
                on_click=edit_selected_usecase,
            ).classes("w-full")

            ui.separator().classes("my-2")
            ui.label("💾 資料儲存").classes("font-semibold")

            ui.button(
                "將目前結果儲存到資料庫",
                color="primary",
                on_click=save_to_db,
            ).classes("w-full")

    # 頁面載入後自動從 DB 把資料讀回來
    ui.timer(0.1, lambda: asyncio.create_task(load_from_db()), once=True)