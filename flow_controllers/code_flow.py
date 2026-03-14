# flow_controllers/code_flow.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from init_db import get_async_session_context
from models.project import Project

from agents.code_agent_openai import CodeAgentOpenAI
from controllers.code_controller import CodeController
from controllers.blueprint_state_controller import BlueprintStateController

# =========================================================
# DTO
# =========================================================
@dataclass
class CodeFlowResult:
    ok: bool
    message: str
    snapshot_id: Optional[int] = None
    file_count: int = 0
    files: Optional[List[Dict[str, str]]] = None  # [{path, content}]


class CodeFlowController:
    """
    Code Flow（配合 Agent + 可選 DB Snapshot）

    主要提供 3 個 dataclass API：
      - generate_preview(): 只生成（不寫DB）
      - generate_and_save_snapshot(): 生成 + 存 DB（CodeSnapshot）
      - load_latest_snapshot(): 讀 DB 最新快照

    另外提供 1 個相容 API（給舊版 View 用）：
      - generate_code_preview(): 回傳 dict，且支援舊參數名稱 agent_mode
    """

    # -----------------------------------------------------
    # 1) Preview only (NO DB write)
    # -----------------------------------------------------
    @classmethod
    async def generate_preview(
        cls,
        project_id: int,
        package_name: str = "generated_app",
        mode: str = "cover",  # "cover" | "patch"
        patch_instruction: str = "",
        existing_files: Optional[List[Dict[str, str]]] = None,
    ) -> CodeFlowResult:
        if project_id <= 0:
            return CodeFlowResult(ok=False, message="project_id 無效", files=[])

        project_meta = await cls._get_project_meta(project_id)
        if not project_meta:
            return CodeFlowResult(ok=False, message=f"找不到專案 id={project_id}", files=[])

        rows = await BlueprintStateController.list(project_id=project_id)

        print("======== Blueprint Debug ========")
        for r in rows:
            print("id:", r.id)
            print("project_id:", r.project_id)
            print("boundary_id:", r.boundary_id)
            print("screen_name:", r.screen_name)
            print("payload_json_len:", len(r.payload_json or ""))
            print("canvas_jpg_len:", len(r.canvas_jpg) if r.canvas_jpg else 0)
            print("---------------------------------")
        print("==================================")

        # ✅ 呼叫 Agent：一定傳 project_id + project_meta（避免 storage 不同步）
        agent_res = await CodeAgentOpenAI.generate_files_for_current_project(
            project_id=project_id,
            project_meta=project_meta,
            package_name=package_name,
            mode=mode,
            patch_instruction=patch_instruction,
            existing_files=existing_files,
        )

        files = cls._normalize_files(agent_res.get("files"))
        if not files:
            err = agent_res.get("error") or "agent_return_empty"
            return CodeFlowResult(ok=False, message=f"AI 生成失敗：{err}", files=[])

        return CodeFlowResult(
            ok=True,
            message="preview_ready",
            file_count=len(files),
            files=files,
        )

    # -----------------------------------------------------
    # 2) Generate + Save Snapshot to DB
    # -----------------------------------------------------
    @classmethod
    async def generate_and_save_snapshot(
        cls,
        project_id: int,
        package_name: str = "generated_app",
        mode: str = "cover",
        patch_instruction: str = "",
        existing_files: Optional[List[Dict[str, str]]] = None,
        return_files: bool = True,
    ) -> CodeFlowResult:
        """
        生成後把結果存進 DB 的 CodeSnapshot.files_json
        """
        preview = await cls.generate_preview(
            project_id=project_id,
            package_name=package_name,
            mode=mode,
            patch_instruction=patch_instruction,
            existing_files=existing_files,
        )
        if not preview.ok:
            return preview

        files = preview.files or []
        files_json = json.dumps({"files": files}, ensure_ascii=False)

        # ✅ 寫 DB（由 CodeController 維護 is_latest）
        snap = await CodeController.create_snapshot(
            project_id=project_id,
            files_json=files_json,
            package_name=package_name,
            mode=mode,
        )

        snap_id = getattr(snap, "id", None)
        try:
            snap_id = int(snap_id) if snap_id is not None else None
        except Exception:
            snap_id = None

        return CodeFlowResult(
            ok=True,
            message="saved_snapshot_ok",
            snapshot_id=snap_id,
            file_count=len(files),
            files=files if return_files else None,
        )

    # -----------------------------------------------------
    # 3) Load latest snapshot from DB
    # -----------------------------------------------------
    @classmethod
    async def load_latest_snapshot(
        cls,
        project_id: int,
    ) -> CodeFlowResult:
        if project_id <= 0:
            return CodeFlowResult(ok=False, message="project_id 無效", files=[])

        snap = await CodeController.get_latest_by_project(project_id)
        if not snap:
            return CodeFlowResult(ok=False, message="尚無任何 code snapshot", files=[])

        raw = getattr(snap, "files_json", "") or ""
        try:
            obj = json.loads(raw)
        except Exception:
            return CodeFlowResult(ok=False, message="snapshot JSON 解析失敗", files=[])

        files = cls._normalize_files(obj.get("files"))
        snap_id = getattr(snap, "id", None)
        try:
            snap_id = int(snap_id) if snap_id is not None else None
        except Exception:
            snap_id = None

        return CodeFlowResult(
            ok=True,
            message="loaded_latest_snapshot",
            snapshot_id=snap_id,
            file_count=len(files),
            files=files,
        )

    # -----------------------------------------------------
    # 4) Backward-compatible alias (old view expects dict + .get)
    # -----------------------------------------------------
    @classmethod
    async def generate_code_preview(
        cls,
        project_id: int,
        package_name: str = "generated_app",
        agent_mode: str = "cover",  # 舊參數名
        patch_instruction: str = "",
        existing_files: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        舊版 code_view 會：
          - 呼叫 generate_code_preview
          - 把回傳當 dict 用（res.get("ok")...）
        這裡做相容層，避免 AttributeError。
        """
        res = await cls.generate_preview(
            project_id=project_id,
            package_name=package_name,
            mode=agent_mode,
            patch_instruction=patch_instruction,
            existing_files=existing_files,
        )
        return {
            "ok": res.ok,
            "message": res.message,
            "files": res.files or [],
            "file_count": res.file_count,
            # 你舊 UI 可能會顯示這兩個欄位；若要精準統計再從 Agent/DB 補
            "used_objects": 0,
            "used_events": 0,
        }

    # =========================================================
    # Internals
    # =========================================================
    @classmethod
    async def _get_project_meta(cls, project_id: int) -> Dict[str, Any]:
        """
        從 DB 拿 project meta，確保 Agent 用「指定 project_id」。
        """
        async with get_async_session_context() as session:
            r = await session.execute(select(Project).where(Project.id == project_id))
            p = r.scalar_one_or_none()
            if not p:
                return {}

            meta: Dict[str, Any] = {
                "id": int(getattr(p, "id")),
                "name": getattr(p, "name", "") or "",
                "description": getattr(p, "description", "") or "",
            }

            # 這些欄位不一定都有，安全 getattr
            for k in (
                "frontend_language",
                "frontend_framework",
                "backend_language",
                "backend_framework",
                "database",
                "architecture",
                "system_architecture",
            ):
                if hasattr(p, k):
                    v = getattr(p, k)
                    if v is not None and str(v).strip() != "":
                        meta[k] = v

            return meta

    @staticmethod
    def _normalize_files(files: Any) -> List[Dict[str, str]]:
        """
        把 Agent 或 snapshot 的輸出統一成：
          [{ "path": "...", "content": "..." }, ...]
        並做基本防呆。
        """
        out: List[Dict[str, str]] = []
        if not files or not isinstance(files, list):
            return out

        for f in files:
            if not isinstance(f, dict):
                continue
            path = (f.get("path") or "").strip().replace("\\", "/").lstrip("/")
            if not path:
                continue
            content = f.get("content")
            if content is None:
                content = ""
            out.append({"path": str(path), "content": str(content)})
        return out