# flow_controllers/object_flow.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from nicegui import app

from controllers.object_controller import ObjectController  # type: ignore
from controllers.attribute_controller import AttributeController  # type: ignore
from controllers.method_controller import MethodController  # type: ignore
from agents.object_agent_openai import ObjectAgent  # type: ignore


class ObjectFlowController:
    @staticmethod
    def _get_current_project() -> Dict[str, Any]:
        project = app.storage.user.get("current_project")
        if not project:
            raise RuntimeError("no_project")
        if not project.get("id"):
            raise RuntimeError("no_project_id")
        return project

    @classmethod
    def _get_current_project_id(cls) -> int:
        return int(cls._get_current_project()["id"])

    @staticmethod
    def _normalize_type(t: str) -> str:
        key = (t or "").strip()
        if key in ("Boundary", "Control", "Entity"):
            return key
        up = key.upper()
        if up in ("BOUNDARY", "CONTROL", "ENTITY"):
            return key.capitalize()
        return "Other"

    @classmethod
    async def list_usecases_for_current_project(cls) -> List[Dict[str, Any]]:
        pid = cls._get_current_project_id()

        UseCaseCtl = None
        try:
            from controllers.usecase_controller import UsecaseController as UseCaseCtl  # type: ignore
        except Exception:
            try:
                from controllers.usecase_controller import UseCaseController as UseCaseCtl  # type: ignore
            except Exception:
                UseCaseCtl = None

        if UseCaseCtl is None:
            return []

        try:
            usecases = await UseCaseCtl.list(project_id=pid)
        except Exception:
            return []

        result: List[Dict[str, Any]] = []
        for u in usecases or []:
            uid = getattr(u, "id", None)
            name = getattr(u, "name", "") or ""
            if uid is None:
                continue
            result.append({"id": int(uid), "name": name})
        return result

    @staticmethod
    def _extract_usecase_info(obj: Any) -> Tuple[Optional[int], str]:
        uid = getattr(obj, "usecase_id", None)
        if uid is None:
            uid = getattr(obj, "use_case_id", None)

        u_name = ""
        rel = getattr(obj, "usecase", None)
        if rel is None:
            rel = getattr(obj, "use_case", None)
        if rel is not None:
            u_name = getattr(rel, "name", "") or ""

        try:
            uid_int = int(uid) if uid is not None else None
        except Exception:
            uid_int = None
        return uid_int, u_name

    @classmethod
    async def list_objects_grouped_by_type(cls, usecase_id: Optional[int] = None) -> Dict[str, List[Dict[str, Any]]]:
        pid = cls._get_current_project_id()

        objects = await ObjectController.list(project_id=pid)

        grouped: Dict[str, List[Dict[str, Any]]] = {"Boundary": [], "Control": [], "Entity": [], "Other": []}

        for obj in objects or []:
            obj_id = getattr(obj, "id", None)
            if obj_id is None:
                continue
            obj_id = int(obj_id)

            uc_id, uc_name = cls._extract_usecase_info(obj)

            # ✅ 嚴格用 usecase_id 篩：不相等、或 NULL，一律不顯示
            if usecase_id is not None:
                if uc_id is None or int(uc_id) != int(usecase_id):
                    continue

            name = getattr(obj, "name", "") or ""
            obj_type = str(getattr(obj, "type", "") or "")
            description = getattr(obj, "description", "") or ""

            attrs = await AttributeController.list(object_id=obj_id)
            meths = await MethodController.list(object_id=obj_id)

            attrs_str = ", ".join(
                (f"{getattr(a, 'visibility', '')} {getattr(a, 'name', '')}: {getattr(a, 'type', '')}").strip()
                for a in attrs
                if (getattr(a, "name", "") or "").strip()
            )

            def _method_sig(m) -> str:
                n = (getattr(m, "name", "") or "").strip()
                p = getattr(m, "parameters", "") or ""
                r = getattr(m, "return_type", "") or ""
                v = getattr(m, "visibility", "") or ""
                sig = f"{n}({p})" if p else f"{n}()"
                if r:
                    sig += f": {r}"
                if v:
                    sig = f"{v} {sig}"
                return sig.strip()

            methods_str = ", ".join(_method_sig(m) for m in meths if (getattr(m, "name", "") or "").strip())

            row = {
                "id": obj_id,
                "name": name,
                "type": obj_type,
                "description": description,
                "usecase_id": uc_id,
                "usecase_name": uc_name,
                "attributes": attrs_str,
                "methods": methods_str,
            }
            grouped[cls._normalize_type(obj_type)].append(row)

        return grouped

    @classmethod
    async def get_object_detail(cls, object_id: int) -> Dict[str, Any]:
        obj = await ObjectController.get(object_id)
        if not obj:
            return {"object": None, "attributes": [], "methods": []}

        obj_type = str(getattr(obj, "type", "") or "")
        attrs = await AttributeController.list(object_id=object_id)
        meths = await MethodController.list(object_id=object_id)
        uc_id, uc_name = cls._extract_usecase_info(obj)

        return {
            "object": {
                "id": getattr(obj, "id", None),
                "name": getattr(obj, "name", "") or "",
                "type": obj_type,
                "description": getattr(obj, "description", "") or "",
                "usecase_id": uc_id,
                "usecase_name": uc_name,
            },
            "attributes": [
                {
                    "id": getattr(a, "id", None),
                    "name": getattr(a, "name", "") or "",
                    "type": getattr(a, "type", "") or "",
                    "visibility": getattr(a, "visibility", "") or "",
                    "default": getattr(a, "default", "") or "",
                }
                for a in attrs
            ],
            "methods": [
                {
                    "id": getattr(m, "id", None),
                    "name": getattr(m, "name", "") or "",
                    "parameters": getattr(m, "parameters", "") or "",
                    "return_type": getattr(m, "return_type", "") or "",
                    "visibility": getattr(m, "visibility", "") or "",
                }
                for m in meths
            ],
        }

    @classmethod
    async def generate_objects_for_current_project(
        cls,
        usecase_id: Optional[int] = None,
        usecase_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        三種模式：
        1) usecase_id 有值 -> 只生成該 usecase
        2) usecase_ids 有值 -> 生成指定清單
        3) 兩者皆 None -> ✅ 自動抓本專案所有 usecase，一次生成全部
        """
        if usecase_ids is None:
            if usecase_id is not None:
                usecase_ids = [int(usecase_id)]
            else:
                # ✅ 生成全部 usecase
                all_usecases = await cls.list_usecases_for_current_project()
                usecase_ids = [int(u["id"]) for u in all_usecases if u.get("id") is not None]
        else:
            usecase_ids = [int(x) for x in (usecase_ids or [])]

        try:
            result = await ObjectAgent.generate_for_current_project(usecase_ids=usecase_ids)
        except Exception as e:
            return {"ok": False, "reason": f"agent_error: {e}", "created": 0, "deleted": 0}

        return {
            "ok": bool(result.get("ok", False)),
            "reason": result.get("reason", ""),
            "created": int(result.get("created", 0) or 0),
            "deleted": int(result.get("deleted", 0) or 0),
            "debug": result.get("debug", ""),
        }