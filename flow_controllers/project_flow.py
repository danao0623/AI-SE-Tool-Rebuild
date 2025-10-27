# 📁 flow_controllers/project_flow.py
from nicegui import app
from agents.project_agent import ProjectAgent
from controllers.project_controller import ProjectController
from controllers.user_account_controller import UserAccountController


class ProjectFlowController:
    """整合 AI、資料庫、使用者流程的中介層"""

    # === 取得登入使用者 ===
    @staticmethod
    async def get_current_user_id():
        current_user = (
            app.storage.user.get('current_user_account')
            or app.storage.user.get('account')
            or app.storage.user.get('user')
        )
        print(f"🔍 目前登入帳號: {current_user}")
        if not current_user:
            return None
        user = await UserAccountController.get_single(account=current_user)
        return user.id if user else None

    # === 生成專案資料（AI） ===
    @staticmethod
    async def generate_project_data(project_name: str):
        result = await ProjectAgent.generate_project_json(project_name)
        return ProjectFlowController._to_grid_rows(result)

    # === 儲存專案（新增/更新） ===
    @staticmethod
    async def save_project(data: dict):
        user_id = await ProjectFlowController.get_current_user_id()
        if not user_id:
            print("⚠️ 尚未登入，無法儲存專案")
            return False

        def safe(v):
            return v if v and str(v).strip() != "" else ""

        clean_data = {k: safe(v) for k, v in data.items()}
        clean_data["user_id"] = user_id

        existing = await ProjectController.get_single(name=clean_data["name"])
        if existing:
            await ProjectController.update(existing.id, **clean_data)
            print(f"✅ 更新專案：{clean_data['name']}")
        else:
            await ProjectController.add(**clean_data)
            print(f"✅ 新增專案：{clean_data['name']}")
        return True

    # === 專案清單 ===
    @staticmethod
    async def list_user_projects():
        user_id = await ProjectFlowController.get_current_user_id()
        if not user_id:
            return []
        projects = await ProjectController.list(user_id=user_id)
        return [
            {"id": p.id, "專案名稱": p.name, "專案描述": p.description or "", "系統架構": p.architecture or ""}
            for p in projects
        ]

    # === 刪除專案 ===
    @staticmethod
    async def delete_project(project_id: int):
        return await ProjectController.delete(project_id)

    # === 重新生成欄位 ===
    @staticmethod
    async def regenerate_selected_fields(project_name: str, fields: list[str]):
        result = await ProjectAgent.regenerate_fields(project_name, fields)
        return ProjectFlowController._to_grid_rows(result)

    # === ✅ 取得完整專案資料 ===
    @staticmethod
    async def get_project_detail(project_id: int):
        """從資料庫查出完整專案內容"""
        project = await ProjectController.get_single(id=project_id)
        if not project:
            return None
        return {
            "name": project.name,
            "description": project.description or "",
            "architecture": project.architecture or "",
            "frontend_language": project.frontend_language or "",
            "frontend_platform": project.frontend_platform or "",
            "frontend_library": project.frontend_library or "",
            "backend_language": project.backend_language or "",
            "backend_platform": project.backend_platform or "",
            "backend_library": project.backend_library or "",
        }

    # === JSON → 表格 ===
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