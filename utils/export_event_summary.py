from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from nicegui import app

from read.md2pdf import GeneratePDF


def _safe_slug(text: str) -> str:
    if not text:
        return "usecase"
    keep = []
    for ch in text:
        if ch.isalnum() or ch in ("-", "_", " "):
            keep.append(ch)
    s = "".join(keep).strip().replace(" ", "_")
    return s or "usecase"


def _get_account_and_project() -> Tuple[str, str]:
    # ✅ 不管登入/不管是否選專案，永遠給 fallback
    account = str(app.storage.user.get("current_user_account") or "guest")
    project = app.storage.user.get("current_project") or {}
    project_id = str(project.get("id") or "default")
    return account, project_id


def _build_md(usecase_id: int, usecase_name: str, normal_rows: List[Dict[str, Any]], exc_rows: List[Dict[str, Any]]) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_table(title: str, rows: List[Dict[str, Any]]) -> str:
        lines = [f"## {title}", "", "| 順序 | 類型 | 說明 |", "|---:|---|---|"]
        if not rows:
            lines.append("|  |  | （無資料） |")
            lines.append("")
            return "\n".join(lines)

        for r in rows:
            seq = str(r.get("sequence_no", "")).replace("\n", " ").replace("|", "｜")
            typ = str(r.get("type", "")).replace("\n", " ").replace("|", "｜")
            desc = str(r.get("description", "")).replace("\n", " ").replace("|", "｜")
            lines.append(f"| {seq} | {typ} | {desc} |")
        lines.append("")
        return "\n".join(lines)

    md = []
    md.append("# 三段式事件列表匯出")
    md.append("")
    md.append(f"- 匯出時間：{ts}")
    md.append(f"- UseCase ID：{usecase_id}")
    md.append(f"- UseCase 名稱：{usecase_name}")
    md.append("")
    md.append("---")
    md.append("")
    md.append(to_table("正常程序", normal_rows))
    md.append(to_table("例外程序", exc_rows))
    return "\n".join(md)


async def export_event_summary_md_pdf(usecase_id: int, usecase_name: str) -> Dict[str, str]:
    """
    匯出 MD + PDF（不檢查登入/專案，永遠可用）
    回傳 md_path/pdf_path 與 md_url/pdf_url
    """
    account, project_id = _get_account_and_project()
    out_dir = Path("files") / account / project_id / "event_summary"
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = _safe_slug(usecase_name)

    md_path = out_dir / f"{ts}_usecase_{usecase_id}_{safe_name}.md"
    pdf_path = out_dir / f"{ts}_usecase_{usecase_id}_{safe_name}.pdf"

    # 1) 從 Flow 抓事件（抓不到就用空資料，但仍輸出檔案）
    normal_rows: List[Dict[str, Any]] = []
    exc_rows: List[Dict[str, Any]] = []
    try:
        from flow_controllers.event_summary_flow import EventSummaryFlowController
        data = await EventSummaryFlowController.load_events_by_usecase(usecase_id)
        normal_rows = data.get("正常程序", []) or []
        exc_rows = data.get("例外程序", []) or []
    except Exception:
        normal_rows, exc_rows = [], []

    # 2) 產 MD
    md_text = _build_md(usecase_id, usecase_name, normal_rows, exc_rows)
    md_path.write_text(md_text, encoding="utf-8")

    # 3) 產 PDF（WeasyPrint）
    GeneratePDF.md_text_to_pdf(md_text, pdf_path, title=f"UseCase：{usecase_name}")

    # 4) 回傳下載資訊（需 main.py: app.add_static_files('/files','files')）
    md_url = "/" + md_path.as_posix()
    pdf_url = "/" + pdf_path.as_posix()

    return {
        "md_path": str(md_path),
        "pdf_path": str(pdf_path),
        "md_url": md_url,
        "pdf_url": pdf_url,
    }
