from nicegui import app
from agents.project_agent import ProjectAgent
from controllers.project_controller import ProjectController
from controllers.user_account_controller import UserAccountController


class ProjectFlowController:
    """整合 AI、資料庫、流程控制（目前僅處理 Project 模組）"""

    # === 登入使用者 ===
    @staticmethod
    async def get_current_user_id():
        """取得目前登入使用者的 id，失敗回傳 None"""
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
        """呼叫 AI 產生專案設定，並轉成給表格用的列資料"""
        result = await ProjectAgent.generate_project_json(project_name)
        return ProjectFlowController._to_grid_rows(result)

    # === 再生（完整重生，但只覆蓋選取欄位）===
    @staticmethod
    async def regenerate_selected_fields(project_name: str, fields: list[str], old_data: dict):
        """
        再呼叫一次 AI 產生完整設定，但只把有選取的欄位覆蓋回去，
        其它欄位沿用 old_data。
        """
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

    # === 儲存專案（僅 Project 階段）===
    @staticmethod
    async def save_project(data: dict):
        """
        儲存 / 更新專案基本資料。
        回傳格式：
        - {"ok": False}                    → 尚未登入
        - {"ok": True, "action": "created"}                → 新增
        - {"ok": True, "action": "updated"}                → 更新（核心欄位無變）
        - {"ok": True, "action": "updated_pending_purge"}  → 更新（核心欄位有變）
        """
        uid = await ProjectFlowController.get_current_user_id()
        if not uid:
            return {"ok": False}

        data = {k: (v or "").strip() if isinstance(v, str) else v for k, v in data.items()}
        data["user_id"] = uid

        existing = await ProjectController.get_single(name=data["name"])
        if not existing:
            await ProjectController.add(**data)
            return {"ok": True, "action": "created"}

        # 比對核心欄位（目前只記錄，尚未觸發 purge）
        core_changed = ProjectFlowController._has_core_changes(existing, data)
        if core_changed:
            await ProjectController.update(existing.id, **data)
            print("⚠️ [提醒] 核心欄位變更，但目前僅更新 Project，未清理後續階段。")
            return {"ok": True, "action": "updated_pending_purge"}

        await ProjectController.update(existing.id, **data)
        return {"ok": True, "action": "updated"}

    # === 專案清單 ===
    @staticmethod
    async def list_user_projects():
        """列出目前登入使用者所有專案（給下方 AgGrid 處理）"""
        uid = await ProjectFlowController.get_current_user_id()
        if not uid:
            return []
        projects = await ProjectController.list(user_id=uid)
        return [
            {
                "id": p.id,
                "專案名稱": p.name,
                "專案描述": p.description or "",
                "系統架構": p.architecture or "",
            }
            for p in projects
        ]

    # === 刪除專案 ===
    @staticmethod
    async def delete_project(project_id: int):
        """目前僅刪除專案本身（後續階段資料之後可在這裡一起清掉）"""
        return await ProjectController.delete(project_id)

    # === 取得專案詳細 ===
    @staticmethod
    async def get_project_detail(project_id: int):
        """取得單一專案完整欄位內容，給「開啟專案」與欄位回填使用"""
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

    # === 當前專案上下文（給「使用案例管理」等下一頁用）===

    @staticmethod
    def set_current_project_context(project: dict | int, project_name: str | None = None) -> None:
        """
        設定目前選擇的專案：

        - View 這邊通常會直接把 AgGrid 的整列 dict 丟進來：
            ProjectFlowController.set_current_project_context(row)
          此時會從 row['id']、row['專案名稱'] 等欄位取出需要的值。

        - 也相容舊版的：
            set_current_project_context(project_id, project_name)
        """
        # 兩種呼叫方式都支援
        if isinstance(project, dict):
            project_id = project.get("id")
            name = project.get("專案名稱") or project.get("name") or ""
            description = project.get("專案描述") or project.get("description") or ""
            architecture = project.get("系統架構") or project.get("architecture") or ""
        else:
            project_id = project
            name = project_name or ""
            description = ""
            architecture = ""

        if project_id is None:
            # 清空 context
            app.storage.user.pop("current_project", None)
            return

        app.storage.user["current_project"] = {
            "id": project_id,
            "name": name,
            "description": description,
            "architecture": architecture,
        }

    @staticmethod
    def get_current_project_context() -> dict | None:
        """
        取得目前選擇的專案（沒有就回傳 None）

        回傳格式範例：
        {
            "id": 1,
            "name": "AI 智慧選股系統",
            "description": "...",
            "architecture": "..."
        }
        """
        return app.storage.user.get("current_project")

    # === 內部共用：把 AI 回傳 dict 轉成表格列 ===
    @staticmethod
    def _to_grid_rows(result: dict | None):
        if not result:
            return []

        rows = []
        rows.append({"項目": "專案描述", "內容": result.get("description", "")})
        rows.append({"項目": "系統架構", "內容": result.get("architecture", "")})

        frontend = result.get("frontend", {}) or {}
        backend = result.get("backend", {}) or {}

        rows.append({"項目": "前端語言", "內容": frontend.get("language", "")})
        rows.append({"項目": "前端平台", "內容": frontend.get("platform", "")})
        rows.append({"項目": "前端函式庫", "內容": frontend.get("library", "")})
        rows.append({"項目": "後端語言", "內容": backend.get("language", "")})
        rows.append({"項目": "後端平台", "內容": backend.get("platform", "")})
        rows.append({"項目": "後端函式庫", "內容": backend.get("library", "")})

        return rows

    # === 內部共用：判斷核心欄位是否變更 ===
    @staticmethod
    def _has_core_changes(existing, new_data: dict) -> bool:
        # 專案名稱
        if existing.name != new_data.get("name"):
            return True
        # 描述
        if (existing.description or "").strip() != (new_data.get("description") or "").strip():
            return True
        # 架構
        if (existing.architecture or "").strip() != (new_data.get("architecture") or "").strip():
            return True

        # 前後端欄位
        fields = [
            ("frontend_language", "frontend_language"),
            ("frontend_platform", "frontend_platform"),
            ("frontend_library", "frontend_library"),
            ("backend_language", "backend_language"),
            ("backend_platform", "backend_platform"),
            ("backend_library", "backend_library"),
        ]
        for attr, key in fields:
            old = getattr(existing, attr, "") or ""
            new = new_data.get(key) or ""
            if old.strip() != new.strip():
                return True

        return False