from agents.project import ProjectAgent
from controllers.project import ProjectController
from controllers.user_account import UserAccountController
from nicegui import app

class ProjectFlowController:
    """整合 AI、DB、使用者流程的控制層"""

    @staticmethod
    async def get_current_user_id():
        """取得目前登入使用者的 user_id"""
        current_user = app.storage.user.get('current_user_account')
        if not current_user:
            return None
        user = await UserAccountController.select_user_account(account=current_user)
        return user.id if user else None

    @staticmethod
    async def generate_project_data(project_name: str):
        """AI 生成並寫入資料庫"""
        user_id = await ProjectFlowController.get_current_user_id()
        result = await ProjectAgent.generate_project_json(project_name)
        rows = ProjectFlowController._to_grid_rows(result)

        if user_id and result:
            await ProjectController.add_project(
                name=result.get("project_name", project_name),
                description=result.get("description", ""),
                architecture=result.get("architecture", ""),
                frontend_language=result.get("frontend", {}).get("language", ""),
                frontend_platform=result.get("frontend", {}).get("platform", ""),
                frontend_library=result.get("frontend", {}).get("library", ""),
                backend_language=result.get("backend", {}).get("language", ""),
                backend_platform=result.get("backend", {}).get("platform", ""),
                backend_library=result.get("backend", {}).get("library", ""),
                user_id=user_id,
            )

        return rows

    @staticmethod
    async def regenerate_selected_fields(project_name: str, selected_fields: list[str]):
        """重新生成勾選欄位並更新資料庫"""
        user_id = await ProjectFlowController.get_current_user_id()
        regenerated = await ProjectAgent.regenerate_fields(project_name, selected_fields)
        rows = ProjectFlowController._to_grid_rows(regenerated)

        if user_id and regenerated:
            await ProjectController.update_project_by_name(
                name=project_name,
                description=regenerated.get("description"),
                architecture=regenerated.get("architecture"),
                frontend_language=regenerated.get("frontend", {}).get("language"),
                frontend_platform=regenerated.get("frontend", {}).get("platform"),
                frontend_library=regenerated.get("frontend", {}).get("library"),
                backend_language=regenerated.get("backend", {}).get("language"),
                backend_platform=regenerated.get("backend", {}).get("platform"),
                backend_library=regenerated.get("backend", {}).get("library"),
            )

        return rows

    @staticmethod
    def _to_grid_rows(result: dict):
        """AI JSON → 表格格式"""
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
