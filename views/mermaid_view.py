from __future__ import annotations

import asyncio
from typing import Any, Optional

from nicegui import ui, app
from flow_controllers.mermaid_flow import DiagramFlowController


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


def _event_value(e: Any) -> Any:
    if e is None:
        return None
    if hasattr(e, "value"):
        return getattr(e, "value")
    args = getattr(e, "args", None)
    if isinstance(args, dict):
        if "value" in args:
            return args["value"]
        if "newValue" in args:
            return args["newValue"]
    return None


def _normalize_mermaid(text: str | None, header: str) -> str:
    """
    關鍵：ui.mermaid 遇到空字串會 UnknownDiagramError，
    所以永遠至少回傳 header（例如 classDiagram\\n）。
    """
    t = (text or "").strip()
    if not t:
        return header
    if not t.lstrip().startswith(header.strip()):
        return header + t
    return t


def mermaid_page() -> None:
    ui.label("📝 UML 圖生成（Mermaid）").classes("text-2xl font-bold mb-4")

    last_tab = app.storage.user.get("mermaid_last_tab") or "erd"
    if last_tab not in ("erd", "class", "sequence"):
        last_tab = "erd"

    state = {"tab": last_tab, "seq_load_token": 0}

    def _next_token() -> int:
        state["seq_load_token"] = int(state.get("seq_load_token", 0)) + 1
        return state["seq_load_token"]

    def _spawn(coro) -> None:
        try:
            asyncio.create_task(coro)
        except Exception:
            pass

    zoom = {"erd": 1.0, "class": 1.0, "sequence": 1.0}

    def _apply_zoom(tab: str, container: ui.element) -> None:
        s = float(zoom.get(tab, 1.0) or 1.0)
        container.style(f"transform: scale({s}); transform-origin: top left;")
        container.props(f"data-scale={s}")

    def _zoom_bar(tab: str, container: ui.element) -> None:
        with ui.row().classes("w-full items-center justify-between mb-2"):
            ui.label("縮放").classes("text-sm text-gray-600")
            with ui.row().classes("items-center gap-2"):
                btn_minus = ui.button("－").props("dense outline").classes("px-3")
                slider = (
                    ui.slider(min=0.5, max=2.0, value=float(zoom.get(tab, 1.0)), step=0.1)
                    .classes("w-56")
                    .props("label-always")
                )
                btn_plus = ui.button("＋").props("dense outline").classes("px-3")
                btn_reset = ui.button("100%").props("dense outline").classes("px-3")

        def set_scale(v: float) -> None:
            try:
                v = float(v)
            except Exception:
                v = 1.0
            v = max(0.5, min(2.0, v))
            zoom[tab] = v
            slider.value = v
            _apply_zoom(tab, container)

        def on_slider(e: Any) -> None:
            v = _event_value(e)
            if v is not None:
                set_scale(v)

        btn_minus.on("click", lambda e=None: set_scale((zoom.get(tab, 1.0) or 1.0) - 0.1))
        btn_plus.on("click", lambda e=None: set_scale((zoom.get(tab, 1.0) or 1.0) + 0.1))
        btn_reset.on("click", lambda e=None: set_scale(1.0))
        slider.on("update:model-value", on_slider)
        _apply_zoom(tab, container)

    def _install_pan_zoom(scroll_id: str, zoom_container_id: str) -> None:
        ui.run_javascript(f"""
        (function() {{
          const root = document.getElementById({scroll_id!r});
          const zoomEl = document.getElementById({zoom_container_id!r});
          if (!root || !zoomEl) return;

          root.classList.add('bp-pan-area');
          const scroller = root.querySelector('.q-scrollarea__container') || root;

          root.addEventListener('wheel', (ev) => {{
            if (!ev.ctrlKey) return;
            ev.preventDefault();
            let s = parseFloat(zoomEl.dataset.scale || '1');
            const delta = ev.deltaY > 0 ? -0.1 : 0.1;
            s = Math.max(0.5, Math.min(2.0, s + delta));
            zoomEl.dataset.scale = String(s);
            zoomEl.style.transformOrigin = 'top left';
            zoomEl.style.transform = `scale(${{s}})`;
          }}, {{ passive: false }});

          let dragging = false;
          let startX = 0, startY = 0;
          let startLeft = 0, startTop = 0;

          root.addEventListener('mousedown', (ev) => {{
            if (ev.button !== 0) return;
            dragging = true;
            root.classList.add('bp-grabbing');
            startX = ev.clientX;
            startY = ev.clientY;
            startLeft = scroller.scrollLeft;
            startTop = scroller.scrollTop;
          }});

          window.addEventListener('mousemove', (ev) => {{
            if (!dragging) return;
            const dx = ev.clientX - startX;
            const dy = ev.clientY - startY;
            scroller.scrollLeft = startLeft - dx;
            scroller.scrollTop = startTop - dy;
          }});

          window.addEventListener('mouseup', () => {{
            if (!dragging) return;
            dragging = false;
            root.classList.remove('bp-grabbing');
          }});
        }})();
        """)

    with ui.grid(columns=12).classes("w-full gap-4"):

        # LEFT
        with ui.card().classes("col-span-2 p-5 bg-white rounded-xl shadow-md h-full flex flex-col justify-between"):
            ui.label("🧭 專案流程").classes("text-lg font-bold mb-3 text-gray-800")

            with ui.stepper(value=6).props("vertical").classes("w-full"):
                ui.step("專案管理").props("name=1 done")
                ui.step("專案案例管理").props("name=2 done")
                ui.step("使用案例明細").props("name=3 done")
                ui.step("三段式事件列表").props("name=4 done")
                ui.step("專案物件瀏覽").props("name=5 done")
                ui.step("UML 圖生成").props("name=6")
                ui.step("介面藍圖").props("name=7")
                ui.step("產生程式碼").props("name=8")

            ui.separator().classes("my-4")
            ui.button("上一頁", on_click=lambda: ui.navigate.to("/svo")).props("outline")
            ui.button("下一頁", on_click=lambda: ui.navigate.to("/blueprint")).props("outline")

        # MIDDLE
        with ui.card().classes("col-span-8 p-5 bg-white rounded-xl shadow-md h-full"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("📌 圖形預覽").classes("text-lg font-bold text-gray-800")

            status = ui.label("").classes("text-sm text-red-600 mt-1")

            def _set_status(msg: str = "") -> None:
                status.text = msg or ""

            tabs = ui.tabs(value=last_tab).classes("w-full mt-2")
            with tabs:
                ui.tab("ERD").props("name=erd")
                ui.tab("類別圖").props("name=class")
                ui.tab("循序圖（依 USECASE）").props("name=sequence")

            panels = ui.tab_panels(tabs, value=last_tab).classes("w-full mt-3")

            erd_scroll_id = "bp_erd_scroll"
            class_scroll_id = "bp_class_scroll"
            seq_scroll_id = "bp_seq_scroll"
            erd_zoom_id = "bp_erd_zoom"
            class_zoom_id = "bp_class_zoom"
            seq_zoom_id = "bp_seq_zoom"

            with panels:
                with ui.tab_panel("erd").classes("w-full"):
                    with ui.scroll_area().classes("w-full h-[620px] border rounded-lg p-2").props(
                        f"id={erd_scroll_id} horizontal"
                    ):
                        erd_zoom_container = ui.column().classes("w-full").props(f"id={erd_zoom_id}")
                    _zoom_bar("erd", erd_zoom_container)
                    with erd_zoom_container:
                        mermaid_erd = ui.mermaid(_normalize_mermaid("", "erDiagram\n")).classes("w-full")

                with ui.tab_panel("class").classes("w-full"):
                    with ui.scroll_area().classes("w-full h-[620px] border rounded-lg p-2").props(
                        f"id={class_scroll_id} horizontal"
                    ):
                        class_zoom_container = ui.column().classes("w-full").props(f"id={class_zoom_id}")
                    _zoom_bar("class", class_zoom_container)
                    with class_zoom_container:
                        # ✅ 這裡改成跟 ERD 一樣用 ui.mermaid
                        mermaid_class = ui.mermaid(_normalize_mermaid("", "classDiagram\n")).classes("w-full")

                with ui.tab_panel("sequence").classes("w-full"):
                    usecase_select = ui.select(options={}, label="選擇 Use Case（循序圖）", value=None).classes(
                        "w-full mb-3"
                    )
                    with ui.scroll_area().classes("w-full h-[560px] border rounded-lg p-2").props(
                        f"id={seq_scroll_id} horizontal"
                    ):
                        seq_zoom_container = ui.column().classes("w-full").props(f"id={seq_zoom_id}")
                    _zoom_bar("sequence", seq_zoom_container)
                    with seq_zoom_container:
                        mermaid_seq = ui.mermaid(_normalize_mermaid("", "sequenceDiagram\n")).classes("w-full")

        # RIGHT
        with ui.card().classes("col-span-2 p-5 bg-white rounded-xl shadow-md h-full"):
            ui.label("♻️ 重生 / 設定").classes("text-lg font-bold mb-3 text-gray-800")
            btn_regen_erd = ui.button("重生 ERD").classes("w-full")
            btn_regen_class = ui.button("重生 類別圖").classes("w-full mt-2")
            btn_regen_all_seq = ui.button("一鍵重生全部循序圖").classes("w-full mt-2")

    def _current_usecase_id() -> Optional[int]:
        if not usecase_select.value:
            return None
        try:
            return int(str(usecase_select.value))
        except Exception:
            return None

    async def load_usecases() -> None:
        pid = _current_project_id()
        if pid <= 0:
            usecase_select.options = {}
            usecase_select.value = None
            return

        rows = await DiagramFlowController.list_usecases(project_id=pid)
        options: dict[str, str] = {}
        first_id: Optional[int] = None

        for r in rows or []:
            uc_id = int((r.get("id") if isinstance(r, dict) else getattr(r, "id", 0)) or 0)
            uc_name = str((r.get("name") if isinstance(r, dict) else getattr(r, "name", f"UseCase {uc_id}")) or "")
            if uc_id <= 0:
                continue
            options[str(uc_id)] = uc_name
            if first_id is None:
                first_id = uc_id

        usecase_select.options = options
        if usecase_select.value not in options:
            usecase_select.value = str(first_id) if first_id is not None else None

    async def load_current(tab: str) -> None:
        _set_status("")
        pid = _current_project_id()
        if pid <= 0:
            _set_status("尚未取得 current_project_id，請回到專案頁重新選取專案。")
            return

        try:
            if tab == "erd":
                text = await DiagramFlowController.get_current_mermaid("erd", project_id=pid)
                mermaid_erd.content = _normalize_mermaid(text, "erDiagram\n")
                return

            if tab == "class":
                text = await DiagramFlowController.get_current_mermaid("class", project_id=pid)
                mermaid_class.content = _normalize_mermaid(text, "classDiagram\n")
                return

            if tab == "sequence":
                await load_usecases()
                uc_id = _current_usecase_id()
                token = _next_token()
                text = await DiagramFlowController.get_current_mermaid("sequence", project_id=pid, usecase_id=uc_id)
                if token != state.get("seq_load_token"):
                    return
                mermaid_seq.content = _normalize_mermaid(text, "sequenceDiagram\n")
                return

        except Exception as e:
            _set_status(f"載入 {tab.upper()} 失敗：{type(e).__name__}: {e}")

    async def regen(diagram_type: str) -> None:
        _set_status("")
        pid = _current_project_id()
        if pid <= 0:
            _set_status("尚未選擇專案，無法重生。")
            return
        try:
            await DiagramFlowController.generate_mermaid(diagram_type, project_id=pid, force_regen=True)
            await load_current(diagram_type)
            _set_status(f"重生 {diagram_type.upper()} 完成")
        except Exception as e:
            _set_status(f"重生 {diagram_type.upper()} 失敗：{type(e).__name__}: {e}")

    async def regen_all_sequences() -> None:
        _set_status("")
        pid = _current_project_id()
        if pid <= 0:
            _set_status("尚未選擇專案，無法重生。")
            return
        try:
            n = await DiagramFlowController.generate_all_sequences(project_id=pid, force_regen=True)
            await load_current("sequence")
            _set_status(f"一鍵重生全部循序圖完成：{n} 張")
        except Exception as e:
            _set_status(f"一鍵重生循序圖失敗：{type(e).__name__}: {e}")

    async def on_tab_change(e: Any) -> None:
        v = _event_value(e)
        tab = str(v) if v is not None else "erd"
        if tab not in ("erd", "class", "sequence"):
            tab = "erd"
        state["tab"] = tab
        app.storage.user["mermaid_last_tab"] = tab
        ui.timer(0.01, lambda: _spawn(load_current(tab)), once=True)

    async def on_usecase_change(e: Any) -> None:
        if state.get("tab") == "sequence":
            await load_current("sequence")

    tabs.on("update:model-value", on_tab_change)
    usecase_select.on("update:model-value", on_usecase_change)

    btn_regen_erd.on("click", lambda e=None: _spawn(regen("erd")))
    btn_regen_class.on("click", lambda e=None: _spawn(regen("class")))
    btn_regen_all_seq.on("click", lambda e=None: _spawn(regen_all_sequences()))

    ui.timer(0.1, lambda: _install_pan_zoom(erd_scroll_id, erd_zoom_id), once=True)
    ui.timer(0.1, lambda: _install_pan_zoom(class_scroll_id, class_zoom_id), once=True)
    ui.timer(0.1, lambda: _install_pan_zoom(seq_scroll_id, seq_zoom_id), once=True)

    ui.timer(0.1, lambda: _spawn(load_current(last_tab)), once=True)
