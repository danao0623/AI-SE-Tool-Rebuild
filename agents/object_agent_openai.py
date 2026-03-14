from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple
import json
import re
import aiohttp

from nicegui import app

from api.api_sys_openai import API_URL, HEADERS, MODEL_NAME  # type: ignore
from utils.json_cleaner import clean_json_text  # type: ignore

from controllers.usecase_controller import UsecaseController  # type: ignore
from controllers.event_list_controller import EventListController  # type: ignore
from controllers.event_controller import EventController  # type: ignore

from controllers.object_controller import ObjectController  # type: ignore
from controllers.attribute_controller import AttributeController  # type: ignore
from controllers.method_controller import MethodController  # type: ignore


class ObjectAgent:
    @staticmethod
    def _get_current_project() -> Dict[str, Any]:
        project = app.storage.user.get("current_project")
        if not project or not project.get("id"):
            raise RuntimeError("no_project")
        return project

    @staticmethod
    def _normalize_event_list_type(list_type: str) -> str:
        s = (list_type or "").strip()
        if not s:
            return ""
        if s in ("正常程序", "正常流程", "正常", "一般", "主流程"):
            return "normal"
        if s in ("例外程序", "例外流程", "例外", "異常", "替代流程"):
            return "exception"
        low = s.lower()
        if low in ("normal", "main", "basic"):
            return "normal"
        if low in ("exception", "alternate", "alt", "error", "abnormal"):
            return "exception"
        return ""

    @classmethod
    async def _format_event_lines(cls, usecase_id: int) -> List[str]:
        lines: List[str] = []
        try:
            event_lists = await EventListController.list_by_usecase(usecase_id=int(usecase_id))
        except TypeError:
            event_lists = await EventListController.list_by_usecase(use_case_id=int(usecase_id))
        except Exception:
            event_lists = []

        normal: List[str] = []
        exception: List[str] = []

        for el in event_lists or []:
            raw_type = (getattr(el, "type", None) or getattr(el, "list_type", "") or "").strip()
            norm = cls._normalize_event_list_type(raw_type)

            try:
                events = await EventController.list_by_event_list(event_list_id=int(getattr(el, "id")))
            except Exception:
                events = []

            rows: List[Tuple[int, str]] = []
            for ev in events or []:
                seq = int(getattr(ev, "sequence_no", 0) or 0)
                desc = (getattr(ev, "description", "") or "").strip()
                if desc:
                    rows.append((seq, desc))
            rows.sort(key=lambda x: x[0])

            if norm == "normal":
                normal.extend([d for _, d in rows])
            elif norm == "exception":
                exception.extend([d for _, d in rows])

        for i, d in enumerate(normal, 1):
            lines.append(f"正常程序{i}: {d}")
        for i, d in enumerate(exception, 1):
            lines.append(f"例外程序{i}: {d}")

        return lines

    @staticmethod
    def _extract_content(raw_text: str) -> str:
        t = raw_text.strip()
        if not t:
            return ""
        try:
            obj = json.loads(t)
            if isinstance(obj, dict) and "choices" in obj:
                choices = obj.get("choices") or []
                if choices and isinstance(choices[0], dict):
                    msg = choices[0].get("message") or {}
                    if isinstance(msg, dict):
                        return (msg.get("content") or "").strip()
            return t
        except Exception:
            return t

    @classmethod
    async def _ask_objects_text(cls, usecase_name: str, usecase_desc: str, event_lines: List[str]) -> Tuple[bool, str, str]:
        prompt_lines = [
            "你是一位經驗豐富的系統分析師，你正在分析一個資訊系統，請根據下列資訊設計相關物件：",
            f"【使用案例名稱】：{usecase_name}",
            f"【使用案例描述】：{usecase_desc}",
            "我也將提供該使用案例的正常程序與例外程序事件列表。",
            "請你從這些語法結構中生成邊界物件、控制物件、實體物件的詳細描述。",
            "邊界物件經常出現在 (Request) 及 (Response) 敘述中的受詞，代表系統的輸入或輸出。",
            "控制物件的成員函數經常出現在 (Process) 敘述中的動詞，也就是每一個動詞可能是控制物件的一項操作或方法。",
            "實體物件會出現在 (Process) 敘述中的受詞，且該敘述的動詞屬於新增/更新/刪除/查詢/其他資料操作。",
            "每一個物件描述必須包含：物件名稱、物件的屬性、物件的方法。",
            "物件屬性格式：屬性名稱:資料類型",
            "物件方法格式：方法名稱(參數名稱: 資料類型, ...): 回傳值資料類型",
            "",
            "【命名與一致性規則（必須遵守，不可省略）】：",
            "1) 物件名稱必須使用英文命名，採用 PascalCase（例：LoginInterface, CourseController, SystemAdminPage）。禁止使用中文物件名稱。",
            "2) 屬性名稱、方法名稱也必須使用英文（camelCase 或 snake_case 擇一即可），禁止中文。",
            "3) 同一 Use Case 內避免同名/近似同義物件重複；若語意相同請合併為同一物件。",
            "4) 物件名稱請具體可讀：避免過度通用名稱（如 Object1、Data、System、Info），請用貼近領域的英文名稱。",
            "5) <<類型>> 僅能使用 Boundary / Control / Entity（大小寫需一致）。",
            "",
            "【輸出格式（務必完全一致，否則無法解析）】：",
            "A) 每個物件固定三行，且必須使用以下關鍵字：『物件名稱』『屬性』『方法』。",
            "B) 物件名稱行格式：物件名稱: xxx <<類型>>",
            "C) 屬性行格式：屬性: a: int, b: str（使用半形逗號 , 分隔；屬性用半形冒號 : ）",
            "D) 方法行格式：方法: foo(a: int): bool, bar(): void（使用半形逗號 , 分隔；方法回傳型別用 : ）",
            "",
            "【事件清單】：",
        ]
        if event_lines:
            prompt_lines.extend(event_lines)
        else:
            prompt_lines.append("（目前沒有事件清單，請根據使用案例名稱/描述合理推導。）")

        prompt_lines.extend(
            [
                "請根據上述資訊，歸納並輸出下列三種類型的 UML 物件：",
                "邊界物件（<<Boundary>>）",
                "控制物件（<<Control>>）",
                "實體物件（<<Entity>>）",
                "每個物件請依照以下格式列出（純文字）：",
                "- 物件名稱: xxx <<類型>>",
                "- 屬性: 屬性名稱: 型別, 屬性名稱: 型別",
                "- 方法: 方法名稱(參數: 型別): 回傳型別, 方法名稱(): 回傳型別",
                "重要：至少要產出 1 個 Boundary、1 個 Control、1 個 Entity。",
                "⚠️ 僅以純文字格式回覆，禁止使用 Markdown 或 JSON，不需額外說明或前後文。",
            ]
        )

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": "You are a senior system analyst. Reply in plain text only."},
                {"role": "user", "content": "\n".join(prompt_lines).strip()},
            ],
            "temperature": 0.2,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, headers=HEADERS, json=payload) as resp:
                raw = await resp.text()
                status = resp.status

        if status != 200:
            return False, "", f"openai_http_{status}: {raw[:800]}"

        content = cls._extract_content(raw)

        if not content or len(content) < 20:
            try:
                content2 = clean_json_text(raw)
                if content2 and len(content2) > len(content):
                    content = content2
            except Exception:
                pass

        return True, content, ""

    @staticmethod
    def parse_ai_response_to_objects(ai_text: str) -> List[Dict[str, Any]]:
        objects: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None

        for raw_line in (ai_text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue

            m_obj = re.match(r"-?\s*物件名稱[:：]?\s*(.+?)\s*<<(\w+)>>", line)
            if m_obj:
                if current:
                    objects.append(current)
                current = {"type": m_obj.group(2), "name": m_obj.group(1).strip(), "attributes": [], "methods": []}
                continue

            m_attr = re.match(r"-?\s*屬性[:：]?\s*(.+)", line)
            if m_attr and current:
                raw = m_attr.group(1)
                for p in [s.strip() for s in raw.split(",")]:
                    if ":" in p:
                        current["attributes"].append(p)
                continue

            m_meth = re.match(r"-?\s*方法[:：]?\s*(.+)", line)
            if m_meth and current:
                raw = m_meth.group(1)
                for p in [s.strip() for s in raw.split(",")]:
                    if "(" in p and ")" in p:
                        current["methods"].append(p)
                continue

        if current:
            objects.append(current)

        return objects

    @staticmethod
    def _normalize_obj_type(t: str) -> str:
        s = (t or "").strip()
        if s.lower() == "boundary":
            return "Boundary"
        if s.lower() == "control":
            return "Control"
        if s.lower() == "entity":
            return "Entity"
        if "邊界" in s or "介面" in s:
            return "Boundary"
        if "控制" in s:
            return "Control"
        if "實體" in s or "資料" in s:
            return "Entity"
        return "Other"

    # ✅ 寫入 Object：新版（一定帶 usecase_id）
    @staticmethod
    async def _create_object_row(project_id: int, usecase_id: int, name: str, obj_type: str, description: str = ""):
        return await ObjectController.add_object(
            name=name,
            obj_type=obj_type,
            project_id=project_id,
            usecase_id=usecase_id,   # ✅ 關鍵：寫入 DB
            description=description,
        )

    @staticmethod
    async def _add_attribute(object_id: int, attr_text: str) -> None:
        if ":" not in attr_text:
            return
        name, typ = [x.strip() for x in attr_text.split(":", 1)]
        if not name:
            return

        await AttributeController.add_attribute(
            object_id=object_id,
            name=name,
            type=typ,
            visibility="public",
        )

    @staticmethod
    async def _add_method(object_id: int, method_text: str) -> None:
        name = (method_text or "").strip()
        if not name:
            return

        await MethodController.add_method(
            object_id=object_id,
            name=name,
            parameters=None,
            return_type=None,
            visibility="public",
        )

    @classmethod
    async def _clear_objects_for_usecase(cls, project_id: int, usecase_id: int) -> int:
        deleted = 0
        # ✅ 先刪該 usecase 的物件（usecase_id 存入後，這段才會真正生效）
        try:
            objs = await ObjectController.list(project_id=project_id, usecase_id=int(usecase_id))
        except Exception:
            objs = await ObjectController.list(project_id=project_id)

        for obj in objs or []:
            uc = getattr(obj, "usecase_id", None)
            if uc is not None and int(uc) != int(usecase_id):
                continue

            oid = getattr(obj, "id", None)
            if oid is None:
                continue
            oid = int(oid)

            try:
                attrs = await AttributeController.list(object_id=oid)
                for a in attrs or []:
                    aid = getattr(a, "id", None)
                    if aid is not None:
                        await AttributeController.delete(int(aid))
            except Exception:
                pass

            try:
                meths = await MethodController.list(object_id=oid)
                for m in meths or []:
                    mid = getattr(m, "id", None)
                    if mid is not None:
                        await MethodController.delete(int(mid))
            except Exception:
                pass

            await ObjectController.delete(oid)
            deleted += 1

        return deleted

    @classmethod
    async def generate_for_current_project(cls, usecase_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        project = cls._get_current_project()
        project_id = int(project["id"])

        # ✅ 僅生成指定的 usecase_ids（Flow 會在「生成全部」時把全部 ids 傳進來）
        if not usecase_ids:
            return {"ok": False, "reason": "no_usecase_selected", "created": 0, "deleted": 0}

        total_created = 0
        total_deleted = 0

        # ✅ 逐一生成每個 usecase
        for uc_id in [int(x) for x in usecase_ids]:
            # 1) 先清掉該 usecase 舊資料
            total_deleted += await cls._clear_objects_for_usecase(project_id, uc_id)

            # 2) 取 usecase 資料
            uc = await UsecaseController.get(int(uc_id))
            if not uc:
                continue

            uc_name = getattr(uc, "name", "") or ""
            uc_desc = getattr(uc, "description", "") or ""

            # 3) 拉事件清單 + 向 OpenAI 詢問物件
            event_lines = await cls._format_event_lines(uc_id)
            ok, content, reason = await cls._ask_objects_text(uc_name, uc_desc, event_lines)
            if not ok:
                return {
                    "ok": False,
                    "reason": reason,
                    "created": total_created,
                    "deleted": total_deleted,
                }

            objects = cls.parse_ai_response_to_objects(content)
            if not objects:
                continue

            # 4) 寫入 DB（一定帶 usecase_id）
            for obj in objects:
                name = (obj.get("name") or "").strip()
                typ = cls._normalize_obj_type(obj.get("type") or "")
                if not name or typ == "Other":
                    continue

                db_obj = await cls._create_object_row(
                    project_id=project_id,
                    usecase_id=uc_id,
                    name=name,
                    obj_type=typ,
                    description="",
                )

                oid = int(getattr(db_obj, "id", 0) or 0)
                if not oid:
                    continue

                for a in obj.get("attributes") or []:
                    await cls._add_attribute(oid, str(a))

                for m in obj.get("methods") or []:
                    await cls._add_method(oid, str(m))

                total_created += 1

        return {"ok": True, "reason": "", "created": total_created, "deleted": total_deleted}