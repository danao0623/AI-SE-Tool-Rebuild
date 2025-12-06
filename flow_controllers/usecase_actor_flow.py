# flow_controllers/usecase_actor_flow.py

from flow_controllers.project_flow import ProjectFlowController
from agents.usecase_actor_agent import UsecaseActorAgent


class UsecaseActorFlowController:
    """
    使用案例 / 角色流程控制層

    負責：
    - 取得目前專案資訊
    - 呼叫 AI Agent 產生 Actor + Use Case JSON
    - 轉換成 View 端 AgGrid 能直接吃的列資料
    """

    # --- 主要給 View 呼叫的入口 ---
    @staticmethod
    async def generate_for_current_project() -> dict:
        """
        針對「目前專案」生成 Actors 與 Use Cases。

        回傳格式：
        {
          "ok": True / False,
          "reason": "no_project" | "empty_response" | ...,
          "actors_rows": [...],
          "usecases_rows": [...],
          "raw": {...}   # 原始 JSON，可選擇要不要用
        }
        """
        project = ProjectFlowController.get_current_project_context()
        if not project:
            return {"ok": False, "reason": "no_project"}

        project_info = {
            "name": project.get("name", ""),
            "description": project.get("description", ""),
            "architecture": project.get("architecture", ""),
        }

        json_data = await UsecaseActorAgent.generate_actor_usecase_json(project_info)
        if not json_data:
            return {"ok": False, "reason": "empty_response"}

        actors_rows = UsecaseActorFlowController._to_actor_rows(json_data)
        usecases_rows = UsecaseActorFlowController._to_usecase_rows(json_data)

        return {
            "ok": True,
            "actors_rows": actors_rows,
            "usecases_rows": usecases_rows,
            "raw": json_data,
        }

    # --- 轉換：Actors → AgGrid 列 ---
    @staticmethod
    def _to_actor_rows(data: dict) -> list[dict]:
        rows: list[dict] = []
        for a in data.get("actors", []) or []:
            rows.append(
                {
                    "名稱": a.get("name", ""),
                    "說明": a.get("description", ""),
                }
            )
        return rows

    # --- 轉換：Use Cases → AgGrid 列 ---
    @staticmethod
    def _to_usecase_rows(data: dict) -> list[dict]:
        rows: list[dict] = []
        for u in data.get("use_cases", []) or []:
            others = u.get("other_actors") or []
            if isinstance(others, list):
                others_str = ", ".join(others)
            else:
                others_str = str(others)

            rows.append(
                {
                    "使用案例名稱": u.get("name", ""),
                    "概述": u.get("summary", ""),
                    "主要角色": u.get("primary_actor", ""),
                    "其他角色": others_str,
                }
            )
        return rows