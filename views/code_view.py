from __future__ import annotations

from typing import Any, Dict, List
from pathlib import Path, PurePosixPath
import zipfile
import datetime
import json

from nicegui import ui, app

from flow_controllers.code_flow import CodeFlowController
from controllers.code_controller import CodeController
from init_db import get_async_session_context


# =========================
# 工具函式
# =========================

def _current_project_id() -> int:
    for k in ("current_project_id", "project_id", "selected_project_id"):
        v = app.storage.user.get(k)
        if v is None:
            continue
        try:
            pid = int(v)
            if pid > 0:
                return pid
        except Exception:
            pass

    p = app.storage.user.get("current_project")
    if isinstance(p, dict) and p.get("id"):
        try:
            pid = int(p["id"])
            if pid > 0:
                app.storage.user["current_project_id"] = pid
                return pid
        except Exception:
            pass

    return 0


def _open_in_new_tab(url: str) -> None:
    safe = url.replace("\\", "/").replace('"', '\\"')
    ui.run_javascript(f'window.open("{safe}", "_blank");')


def _safe_zip_arcname(path: str) -> str:
    p = (path or "").strip().replace("\\", "/").lstrip("/")
    if not p:
        return ""
    parts = [x for x in p.split("/") if x]
    if any(x == ".." for x in parts):
        return ""
    return str(PurePosixPath(*parts))


def _zip_and_save(
    *,
    project_id: int,
    account: str,
    package_name: str,
    files: List[Dict[str, str]],
) -> str:

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("files") / account / str(project_id) / "code_zip"
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_path = out_dir / f"{package_name}_{ts}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            rel = _safe_zip_arcname(f.get("path"))
            if not rel:
                continue
            arcname = f"{package_name}/{rel}"
            zf.writestr(arcname, f.get("content") or "")

    rel_url = zip_path.relative_to(Path("files")).as_posix()
    return f"/files/{rel_url}"


def _group_by_mvc_preview(files: List[Dict[str, str]], package_name: str) -> Dict[str, List[Dict[str, str]]]:

    groups = {"models": [], "controllers": [], "flow_controllers": [], "views": [], "others": []}
    pkg_prefix = f"{package_name}/"

    for f in files or []:
        p = (f.get("path") or "").replace("\\", "/").lstrip("/")

        if p.startswith(pkg_prefix):
            p = p[len(pkg_prefix):]

        f["path"] = p
        top = p.split("/", 1)[0] if "/" in p else p

        if top in groups:
            groups[top].append(f)
        else:
            groups["others"].append(f)

    for k in groups:
        groups[k] = sorted(groups[k], key=lambda x: x.get("path") or "")

    return groups


# =========================
# 主頁
# =========================

@ui.page("/code")
def code_page() -> None:

    ui.label("🧩 產生程式碼（MVC 骨架）").classes("text-2xl font-bold mb-4")

    current_project: Dict[str, Any] = app.storage.user.get("current_project") or {}
    account = (app.storage.user.get("current_user_account") or "guest").strip() or "guest"

    state: Dict[str, Any] = {
        "busy": False,
        "preview_files": [],
        "zip_url": "",
    }

    with ui.grid(columns=12).classes("w-full gap-4"):

        # LEFT
        with ui.card().classes("col-span-2 p-5 bg-white rounded-xl shadow-md h-full flex flex-col"):
            ui.label("🧭 專案流程").classes("text-lg font-bold mb-3 text-gray-800")

            with ui.stepper(value=8).props("vertical").classes("w-full"):
                ui.step("專案管理").props("name=1 done")
                ui.step("專案案例管理").props("name=2 done")
                ui.step("使用案例明細").props("name=3 done")
                ui.step("三段式事件列表").props("name=4 done")
                ui.step("專案物件瀏覽").props("name=5 done")
                ui.step("UML 圖生成").props("name=6 done")
                ui.step("介面藍圖").props("name=7 done")
                ui.step("產生程式碼").props("name=8")

            ui.separator().classes("my-4")
            ui.button("上一頁（介面藍圖）", on_click=lambda: ui.navigate.to("/blueprint")).props("outline").classes("w-full")

        # MIDDLE
        with ui.card().classes("col-span-6 p-5 bg-white rounded-xl shadow-md h-full"):

            ui.label("📌 檔案分類（MVC）").classes("text-lg font-bold")
            ui.label(f"目前專案：{current_project.get('name', '(未選擇)')}").classes("text-sm text-gray-600")

            status = ui.label("").classes("text-sm text-red-600 mt-2")

            def set_status(msg: str = ""):
                status.text = msg

            ui.separator().classes("my-3")

            with ui.row().classes("w-full gap-2"):
                btn_gen = ui.button("① 生成 CODE", color="primary")
                btn_save = ui.button("② 儲存進資料庫", color="secondary")
                btn_zip = ui.button("③ 下載 ZIP", color="positive")
                btn_zip.disable()

            ui.separator().classes("my-3")

            package_name = ui.input("Package 名稱", value="generated_app").classes("w-full")

            ui.separator().classes("my-3")

            info = ui.label("").classes("text-sm text-gray-600")
            list_container = ui.column().classes("w-full gap-2")

        # RIGHT
        with ui.card().classes("col-span-4 p-5 bg-white rounded-xl shadow-md h-full"):
            ui.label("👀 檔案預覽").classes("text-lg font-bold mb-2")
            preview_title = ui.label("尚未選擇檔案").classes("text-sm text-gray-600")

            # NiceGUI 版本差異：language / lang 都有人用過
            preview_box = ui.column().classes("w-full")
            preview_code = None  # type: ignore

    # ✅ 關鍵：統一處理預覽更新（兼容不同 NiceGUI 版本）
    def show_preview(path: str, content: str) -> None:
        nonlocal preview_code
        preview_title.text = path

        preview_box.clear()

        with preview_box:
            preview_code = ui.code(content or "").classes("w-full")
            preview_code.props("language=python")
        preview_code.props("lang=python")
    # =========================
    # 生成
    # =========================

    async def do_generate():
        if state["busy"]:
            return

        state["busy"] = True
        btn_gen.disable()
        btn_zip.disable()
        set_status("")
        list_container.clear()
        preview_title.text = "尚未選擇檔案"
        show_preview("", "")  # 清空預覽

        try:
            pid = _current_project_id()
            if pid <= 0:
                set_status("請先選擇專案")
                return

            res = await CodeFlowController.generate_preview(
                project_id=pid,
                package_name=package_name.value,
                mode="cover",
            )

            if not res.ok:
                set_status(res.message)
                return

            state["preview_files"] = res.files or []
            info.text = f"生成完成：{res.file_count} 檔案"
            render_files()
            btn_zip.enable()

        finally:
            state["busy"] = False
            btn_gen.enable()

    # =========================
    # 儲存（單筆覆蓋）
    # =========================

    async def do_save():
        if state["busy"]:
            return

        if not state["preview_files"]:
            set_status("請先生成 CODE")
            return

        state["busy"] = True
        btn_save.disable()

        try:
            pid = _current_project_id()
            if pid <= 0:
                set_status("請先選擇專案")
                return

            files_json = json.dumps({"files": state["preview_files"]}, ensure_ascii=False)
            existing = await CodeController.get_latest_by_project(pid)

            if existing:
                async with get_async_session_context() as session:
                    existing.files_json = files_json
                    session.add(existing)
                    await session.commit()
                set_status("已覆蓋舊版 CODE")
            else:
                await CodeController.create_snapshot(
                    project_id=pid,
                    files_json=files_json,
                    package_name=package_name.value,
                    mode="cover",
                )
                set_status("已儲存 CODE")

            ui.notify("儲存完成", type="positive")

        finally:
            state["busy"] = False
            btn_save.enable()

    # =========================
    # 下載
    # =========================

    async def do_download():
        if not state["preview_files"]:
            set_status("請先生成 CODE")
            return

        pid = _current_project_id()
        url = _zip_and_save(
            project_id=pid,
            account=account,
            package_name=package_name.value,
            files=state["preview_files"],
        )

        _open_in_new_tab(url)

    # =========================
    # 顯示檔案
    # =========================

    def render_files():
        list_container.clear()
        groups = _group_by_mvc_preview(state["preview_files"], package_name.value)

        for key, items in groups.items():
            with list_container:
                with ui.expansion(f"📁 {key} ({len(items)})", value=True):
                    for f in items:
                        p = f.get("path", "")
                        c = f.get("content", "")
                        with ui.row().classes("w-full justify-between"):
                            ui.label(p)
                            ui.button("預覽", on_click=lambda p=p, c=c: show_preview(p, c))

    btn_gen.on_click(do_generate)
    btn_save.on_click(do_save)
    btn_zip.on_click(do_download)