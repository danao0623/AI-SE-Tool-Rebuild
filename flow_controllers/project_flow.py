# 📁 flow_controllers/project_flow.py
from nicegui import app
from agents.project_agent import ProjectAgent
from controllers.project_controller import ProjectController
from controllers.user_account_controller import UserAccountController

# 可選：若你有這些 controller，就 import；沒有也沒關係（在 purge 內會 try/except）
try:
    from controllers.usecase_controller import UseCaseController
    from controllers.usecasedetail_controller import UseCaseDetailController
    from controllers.event_controller import EventController
    from controllers.object_controller import ObjectController
    from controllers.diagram_controller import DiagramController
    from controllers.file_controller import FileController  # 例如產出的 md/pdf/code 管理
except Exception:
    UseCaseController = UseCaseDetailController = EventController = None
    ObjectController = DiagramController = FileController = None


class ProjectFlowController:
    """整合 AI、資料庫、流程控制（含級聯清理）"""

    # === 登入使用者 ===
    @staticmethod
    async def get_current_user_id():
        current_user = (
            app.storage.user.get('current_user_account')
            or app.storage.user.get('account')
            or app.storage.user.get('user')
        )
        if not current_user:
            return None
        user = await UserAccountController.get_single(account=current_user)
        return user.id if user else None

    # === 初次生成 ===
    @staticmethod
    async def generate_project_data(project_name: str):
        result = await ProjectAgent.generate_project_json(project_name)
        return ProjectFlowController._to_grid_rows(result)

    # === 再生（完整重生，但只覆蓋選取欄位）===
    @staticmethod
    async def regenerate_selected_fields(project_name: str, fields: list[str], old_data: dict):
        new_result = await ProjectAgent.generate_project_json(project_name)
        if not new_result:
            return ProjectFlowController._to_grid_rows(old_data or {})

        mapping = {
            "專案描述": ("description",),
            "系統架構": ("architecture",),
            "前端語言": ("frontend", "language"),
            "前端平台": ("frontend", "platform"),
            "前端函式庫": ("frontend", "library"),
            "後端語言": ("backend", "language"),
            "後端平台": ("backend", "platform"),
            "後端函式庫": ("backend", "library"),
        }

        updated = (old_data or {}).copy()
        for field in fields:
            path = mapping.get(field)
            if not path:
                continue
            value = new_result
            for k in path:
                value = value.get(k, {}) if isinstance(value, dict) else ""
            if isinstance(value, str):
                ref = updated
                for k in path[:-1]:
                    ref = ref.setdefault(k, {})
                ref[path[-1]] = value

        return ProjectFlowController._to_grid_rows(updated)

    # === 儲存（若核心欄位變更 → 級聯清空） ===
    @staticmethod
    async def save_project(data: dict):
        uid = await ProjectFlowController.get_current_user_id()
        if not uid:
            return {"ok": False}
        data = {k: (v or "").strip() if isinstance(v, str) else v for k, v in data.items()}
        data["user_id"] = uid

        existing = await ProjectController.get_single(name=data["name"])
        if not existing:
            await ProjectController.add(**data)
            return {"ok": True, "action": "created"}

        # 比對「核心欄位」是否有變更
        core_changed = ProjectFlowController._has_core_changes(existing, data)
        if core_changed:
            await ProjectFlowController.purge_downstream(existing.id)  # 🔥 清掉 2/3 階段
            await ProjectController.update(existing.id, **data)
            return {"ok": True, "action": "updated_purged"}

        # 沒變更就單純更新（或略過）
        await ProjectController.update(existing.id, **data)
        return {"ok": True, "action": "updated"}

    # === 取得專案清單 ===
    @staticmethod
    async def list_user_projects():
        uid = await ProjectFlowController.get_current_user_id()
        if not uid:
            return []
        projects = await ProjectController.list(user_id=uid)
        return [
            {"id": p.id, "專案名稱": p.name, "專案描述": p.description or "", "系統架構": p.architecture or ""}
            for p in projects
        ]

    # === 刪除專案（含級聯清空） ===
    @staticmethod
    async def delete_project(project_id: int):
        await ProjectFlowController.purge_downstream(project_id)
        return await ProjectController.delete(project_id)

    # === 取得專案詳細（回填用） ===
    @staticmethod
    async def get_project_detail(project_id: int):
        p = await ProjectController.get_single(id=project_id)
        if not p:
            return None
        return {
            "name": p.name,
            "description": p.description or "",
            "architecture": p.architecture or "",
            "frontend_language": p.frontend_language or "",
            "frontend_platform": p.frontend_platform or "",
            "frontend_library": p.frontend_library or "",
            "backend_language": p.backend_language or "",
            "backend_platform": p.backend_platform or "",
            "backend_library": p.backend_library or "",
        }

    # === 級聯清除：UseCase / Detail / Event / Object / Diagram / Files ===
    @staticmethod
    async def purge_downstream(project_id: int):
        # 這裡盡量不 throw，中間某一層沒有就跳過
        async def _try(coro, label):
            try:
                if coro:
                    await coro
            except Exception as e:
                print(f"⚠️ 清理 {label} 失敗：{e}")

        if UseCaseDetailController:
            await _try(UseCaseDetailController.delete_by_project(project_id), "UseCaseDetail")
        if UseCaseController:
            await _try(UseCaseController.delete_by_project(project_id), "UseCase")
        if EventController:
            await _try(EventController.delete_by_project(project_id), "Event")
        if ObjectController:
            await _try(ObjectController.delete_by_project(project_id), "Object")
        if DiagramController:
            await _try(DiagramController.delete_by_project(project_id), "Diagram")
        if FileController:
            await _try(FileController.delete_project_outputs(project_id), "Files")

    # === 判斷核心欄位是否有變更（影響後續 2/3 階段） ===
    @staticmethod
    def _has_core_changes(existing, new_data: dict) -> bool:
        fields = [
            ("description", "description"),
            ("architecture", "architecture"),
            ("frontend_language", "frontend_language"),
            ("frontend_platform", "frontend_platform"),
            ("frontend_library", "frontend_library"),
            ("backend_language", "backend_language"),
            ("backend_platform", "backend_platform"),
            ("backend_library", "backend_library"),
        ]
        for model_attr, new_key in fields:
            old = (getattr(existing, model_attr) or "").strip()
            new = (new_data.get(new_key) or "").strip()
            if old != new:
                return True
        return False

    # === JSON → 表格（供 View 顯示） ===
    @staticmethod
    def _to_grid_rows(result: dict):
        if not result:
            return []
        mapping = {
            "project_name": "專案名稱",
            "description": "專案描述",
            "architecture": "系統架構",
            "frontend.language": "前端語言",
            "frontend.platform": "前端平台",
            "frontend.library": "前端函式庫",
            "backend.language": "後端語言",
            "backend.platform": "後端平台",
            "backend.library": "後端函式庫",
        }
        rows = []
        for key, label in mapping.items():
            value = result
            for part in key.split('.'):
                value = value.get(part, {}) if isinstance(value, dict) else ""
            if isinstance(value, dict):
                value = ""
            rows.append({"項目": label, "內容": value or ""})
        return rows