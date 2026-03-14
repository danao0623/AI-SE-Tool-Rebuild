from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
import asyncio
import aiohttp
import re

from nicegui import app

from api.api_sys_openai import API_URL, HEADERS, MODEL_NAME  # type: ignore
from utils.json_cleaner import clean_json_text  # type: ignore

from controllers.object_controller import ObjectController  # type: ignore
from controllers.attribute_controller import AttributeController  # type: ignore

try:
    from controllers.method_controller import MethodController  # type: ignore
except Exception:
    MethodController = None  # type: ignore

try:
    from controllers.event_controller import EventController  # type: ignore
except Exception:
    EventController = None  # type: ignore

try:
    from controllers.event_list_controller import EventListController  # type: ignore
except Exception:
    EventListController = None  # type: ignore


class ClassDiagramAgent:
    """
    Mermaid v11 安全版 Class Diagram Agent
    - 中文顯示：一律用 alias：class "中文" as EnglishId
    - identifier 一律 [A-Za-z0-9_]
    - class 名稱唯一（自動去重）
    - 關聯端點一致（全域 mapping）
    - ✅ 不依賴 app.storage：Flow 可直接用 project_id 呼叫
    - ✅ 成員語法輸出統一為 Mermaid v11 穩定格式：
        attribute: +name: type
        method:    +method(params): returnType
    """

    DEBUG = True
    _IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    @classmethod
    def _dbg(cls, msg: str) -> None:
        if cls.DEBUG:
            print(msg, flush=True)

    # -----------------------------
    # Project resolution
    # -----------------------------
    @staticmethod
    def _get_current_project_from_storage() -> Optional[Dict[str, Any]]:
        try:
            project = app.storage.user.get("current_project")
            if project and project.get("id"):
                return project
        except Exception:
            return None
        return None

    @classmethod
    async def _load_project_info_from_db(cls, db: Optional[Any], project_id: int) -> Dict[str, str]:
        info = {"name": "", "description": ""}
        if db is None:
            return info
        try:
            cur = await db.execute(
                "SELECT name, description FROM projects WHERE id = ? LIMIT 1",
                (int(project_id),),
            )
            row = await cur.fetchone()
            await cur.close()
            if row:
                info["name"] = (row[0] or "")
                info["description"] = (row[1] or "")
        except Exception:
            pass
        return info

    # -----------------------------
    # Data collection
    # -----------------------------
    @classmethod
    async def _collect_objects(cls, project_id: int) -> List[Dict[str, Any]]:
        try:
            objs = await ObjectController.list(project_id=project_id)
        except Exception as e:
            cls._dbg(f"[CLASS][collect_objects] ObjectController.list failed: {type(e).__name__}: {e}")
            return []

        results: List[Dict[str, Any]] = []
        for o in objs or []:
            oid = int(getattr(o, "id"))
            name = str(getattr(o, "name", "") or "").strip()
            desc = str(getattr(o, "description", "") or "").strip()
            obj_type = str(getattr(o, "obj_type", "") or getattr(o, "type", "") or "").strip()

            try:
                attrs = await AttributeController.list(object_id=oid)
            except Exception:
                attrs = []

            attr_list: List[str] = []
            for a in attrs or []:
                an = str(getattr(a, "name", "") or "").strip()
                at = str(getattr(a, "type", "") or "").strip()
                if an:
                    # ✅ 先用 Mermaid v11 穩定格式（帶冒號）
                    attr_list.append(f"{an}: {at or 'string'}")

            methods_list: List[str] = []
            if MethodController is not None:
                try:
                    ms = await MethodController.list(object_id=oid)  # type: ignore
                    for m in ms or []:
                        mn = str(getattr(m, "name", "") or "").strip()
                        rt = str(getattr(m, "type", "") or "").strip()
                        if mn:
                            # ✅ 先用 Mermaid v11 穩定格式（帶冒號）
                            methods_list.append(f"{mn}(): {rt or 'void'}")
                except Exception:
                    methods_list = []

            results.append(
                {
                    "id": oid,
                    "name": name,
                    "type": obj_type,
                    "description": desc,
                    "attributes": attr_list,
                    "methods": methods_list,
                }
            )

        cls._dbg(f"[CLASS][collect_objects] project_id={project_id} objects={len(results)}")
        return results

    @classmethod
    async def _collect_events_for_project(cls, project_id: int, db: Optional[Any] = None) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []

        if db is not None:
            try:
                sql = """
                SELECT
                  el.use_case_id AS usecase_id,
                  COALESCE(uc.name, '') AS usecase_name,
                  e.sequence_no AS seq,
                  e.type AS type,
                  e.description AS desc
                FROM events e
                JOIN event_lists el ON el.id = e.event_list_id
                JOIN use_cases uc ON uc.id = el.use_case_id
                WHERE uc.project_id = ?
                ORDER BY el.use_case_id ASC, e.sequence_no ASC, e.id ASC
                """
                cur = await db.execute(sql, (int(project_id),))
                rows = await cur.fetchall()
                await cur.close()
                for r in rows or []:
                    desc = (r[4] or "")
                    if not desc:
                        continue
                    events.append(
                        {"usecase_id": r[0], "usecase_name": r[1], "seq": r[2], "type": r[3], "desc": desc}
                    )
                cls._dbg(f"[CLASS][collect_events] project_id={project_id} events={len(events)} (db)")
                return events
            except Exception as e:
                cls._dbg(f"[CLASS][collect_events] db query failed: {type(e).__name__}: {e}")

        if EventController is not None:
            cls._dbg("[CLASS][collect_events] controller fallback skipped: schema has no Event.project_id")

        cls._dbg(f"[CLASS][collect_events] project_id={project_id} events={len(events)} (controller)")
        return events

    # -----------------------------
    # Mermaid normalize
    # -----------------------------
    @staticmethod
    def _has_zh(s: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", s or ""))

    @classmethod
    def _make_unique(cls, base: str, used: set[str]) -> str:
        if base not in used:
            used.add(base)
            return base
        i = 2
        while f"{base}_{i}" in used:
            i += 1
        v = f"{base}_{i}"
        used.add(v)
        return v

    @classmethod
    def _safe_identifier_base(cls, raw: str, fallback_prefix: str = "X") -> str:
        original = (raw or "").strip()
        if not original:
            return f"{fallback_prefix}_unnamed"
        if cls._IDENT_RE.match(original):
            return original

        safe = []
        for ch in original:
            if ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ("0" <= ch <= "9") or ch == "_":
                safe.append(ch)
            else:
                safe.append("_")
        safe_name = re.sub(r"_+", "_", "".join(safe)).strip("_")
        if not safe_name:
            safe_name = f"{fallback_prefix}_name"
        if safe_name[0].isdigit():
            safe_name = f"{fallback_prefix}_{safe_name}"
        if not re.match(r"^[A-Za-z_]", safe_name):
            safe_name = f"{fallback_prefix}_{safe_name}"
        return safe_name

    @classmethod
    def _normalize_type(cls, t: str) -> str:
        s = (t or "").strip()
        if not s:
            return "string"
        s = s.replace("\t", " ").strip()
        s = re.sub(r"\bboolean\b", "bool", s, flags=re.IGNORECASE)
        s = re.sub(r"\bstr\b", "string", s, flags=re.IGNORECASE)
        s = re.sub(r"\binteger\b", "int", s, flags=re.IGNORECASE)
        if "<" in s or ">" in s:
            s = re.sub(r"[<>]", "_", s)
            s = re.sub(r"_+", "_", s).strip("_")
        return s or "string"

    @classmethod
    def _normalize_mermaid_classdiagram(cls, mermaid: str) -> str:
        """
        Normalize AI output into Mermaid classDiagram syntax that Mermaid 10.x/11.x can parse.

        Critical fix for your current error:
        - If AI outputs '{' on its own line after a class declaration, Mermaid often raises
          'Syntax error in text'. We attach '{' to the previous class declaration line:
              class X
              {
          becomes:
              class X {
        """
        if not mermaid:
            return "classDiagram\n"

        text = (mermaid or "").strip()
        text = text.replace("```mermaid", "").replace("```json", "").replace("```", "").strip()

        if "classDiagram" in text and not text.startswith("classDiagram"):
            text = text[text.find("classDiagram") :].strip()
        if not text.startswith("classDiagram"):
            return "classDiagram\n"

        lines = text.splitlines()

        used_ids: set[str] = set()
        token_to_id: Dict[str, str] = {}
        id_to_label: Dict[str, str] = {}

        def get_id(token: str, fallback_prefix: str = "C") -> str:
            tk = (token or "").strip()
            if tk in token_to_id:
                return token_to_id[tk]
            base = cls._safe_identifier_base(tk, fallback_prefix=fallback_prefix)
            uid = cls._make_unique(base, used_ids)
            token_to_id[tk] = uid
            if cls._has_zh(tk) or not cls._IDENT_RE.match(tk):
                id_to_label[uid] = tk
            return uid

        alias_decl_re = re.compile(
            r'^\s*class\s+"([^"]+)"\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\s*(\{)?\s*(%%.*)?$'
        )
        class_decl_re = re.compile(r"^\s*class\s+(.+?)\s*(\{)?\s*(%%.*)?$")
        rel_re = re.compile(r"^\s*([^\s]+)\s+([<.\-|o*]+)\s+([^\s:]+)(.*)$")
        member_line_re = re.compile(r"^\s*([+#\-~])\s*(.+?)(\s*%%.*)?$")

        out: List[str] = ["classDiagram"]
        extra_decls: List[str] = []
        declared_ids: set[str] = set()
        in_class = False

        def emit_alias_stub(uid: str) -> None:
            if uid in declared_ids:
                return
            label = id_to_label.get(uid)
            if label:
                extra_decls.append(f'class "{label}" as {uid}')
            else:
                extra_decls.append(f"class {uid}")
            declared_ids.add(uid)

        def normalize_member_line(line_in: str) -> Optional[str]:
            """
            ✅ 輸出 Mermaid v11 穩定語法：
              attribute: +name: type
              method:    +method(params): returnType
            同時移除參數型別（a: int -> a），避免 parser 問題。
            """
            mm = member_line_re.match(line_in)
            if not mm:
                return None

            vis = mm.group(1)
            body = (mm.group(2) or "").strip()
            body = re.sub(r"\s*%%.*$", "", body).strip()
            if not body:
                return None

            # method
            if "(" in body and ")" in body and body.find("(") < body.rfind(")"):
                name_part = body[: body.find("(")].strip()
                params_part = body[body.find("(") + 1 : body.rfind(")")]
                after = body[body.rfind(")") + 1 :].strip()

                params_clean: List[str] = []
                for p in [x.strip() for x in params_part.split(",") if x.strip()]:
                    p = re.sub(r":\s*.+$", "", p).strip()
                    if p:
                        params_clean.append(p)
                params_out = ", ".join(params_clean)

                ret_type = after[1:].strip() if after.startswith(":") else after.strip()
                ret_norm = cls._normalize_type(ret_type) if ret_type else "void"

                method_safe = cls._safe_identifier_base(name_part, fallback_prefix="m")
                return f"    {vis}{method_safe}({params_out}): {ret_norm}"

            # attribute
            attr_name = body
            attr_type = "string"

            if ":" in body:
                left, right = body.split(":", 1)
                attr_name = left.strip()
                attr_type = right.strip()
            else:
                parts = body.split()
                if len(parts) >= 2:
                    attr_name = parts[0].strip()
                    attr_type = " ".join(parts[1:]).strip()

            attr_safe = cls._safe_identifier_base(attr_name, fallback_prefix="a")
            attr_norm = cls._normalize_type(attr_type)
            return f"    {vis}{attr_safe}: {attr_norm}"

        for raw in lines[1:]:
            line = raw.rstrip()
            if not line.strip():
                continue

            # ✅ FIX: if AI puts "{" on its own line, attach it to the previous class decl
            if line.strip() == "{":
                if out and out[-1].lstrip().startswith("class ") and not out[-1].rstrip().endswith("{"):
                    out[-1] = out[-1].rstrip() + " {"
                    in_class = True
                else:
                    # orphan brace; keeping it breaks Mermaid -> drop it
                    out.append("%% dropped_orphan_brace")
                continue

            if line.strip().startswith("}"):
                out.append("}")
                in_class = False
                continue

            m = alias_decl_re.match(line)
            if m:
                label = (m.group(1) or "").strip()
                uid_raw = (m.group(2) or "").strip()
                has_brace = bool(m.group(3))

                uid_base = cls._safe_identifier_base(uid_raw, fallback_prefix="C")
                uid = cls._make_unique(uid_base, used_ids)

                token_to_id[label] = uid
                token_to_id[uid_raw] = uid
                id_to_label[uid] = label
                declared_ids.add(uid)

                if has_brace:
                    out.append(f'class "{label}" as {uid} {{')
                    in_class = True
                else:
                    out.append(f'class "{label}" as {uid}')
                continue

            mc = class_decl_re.match(line)
            if mc and line.lstrip().startswith("class "):
                name_part = (mc.group(1) or "").strip()
                has_brace = bool(mc.group(2))

                name_part = re.sub(r"\s*%%.*$", "", name_part).strip()
                uid = get_id(name_part, fallback_prefix="C")
                declared_ids.add(uid)

                label = id_to_label.get(uid)
                if has_brace:
                    if label:
                        out.append(f'class "{label}" as {uid} {{')
                    else:
                        out.append(f"class {uid} {{")
                    in_class = True
                else:
                    if label:
                        out.append(f'class "{label}" as {uid}')
                    else:
                        out.append(f"class {uid}")
                continue

            if in_class:
                nm = normalize_member_line(line)
                if nm is not None:
                    out.append(nm)
                    continue

                if cls._has_zh(line):
                    out.append(f"    %% dropped_invalid: {line.strip()}")
                else:
                    out.append(line)
                continue

            mr = rel_re.match(line)
            if mr:
                left_raw = (mr.group(1) or "").strip()
                arrow = (mr.group(2) or "").strip()
                right_raw = (mr.group(3) or "").strip()
                tail = mr.group(4) or ""

                left_id = get_id(left_raw, fallback_prefix="C")
                right_id = get_id(right_raw, fallback_prefix="C")

                tail = re.sub(r'\s*:\s*""\s*$', "", tail)
                tail = re.sub(r"\s*:\s*''\s*$", "", tail)

                if arrow == "<..":
                    left_id, right_id = right_id, left_id
                    arrow = "..>"

                if left_id == right_id:
                    out.append(f"%% dropped_self_relation: {left_id}")
                    continue

                emit_alias_stub(left_id)
                emit_alias_stub(right_id)

                rebuilt = f"{left_id} {arrow} {right_id}{tail}"
                if left_raw != left_id or right_raw != right_id:
                    rebuilt += f"  %% map L:{left_raw} R:{right_raw}"
                out.append(rebuilt.rstrip())
                continue

            if cls._has_zh(line):
                out.append(f"%% dropped_line: {line.strip()}")
            else:
                out.append(line)

        if extra_decls:
            seen = set()
            uniq: List[str] = []
            for d in extra_decls:
                if d not in seen:
                    uniq.append(d)
                    seen.add(d)
            out = [out[0]] + uniq + out[1:]

        normalized = "\n".join(out).strip()
        if not normalized.startswith("classDiagram"):
            return "classDiagram\n"
        return normalized + "\n"


    # -----------------------------
    # OpenAI call
    # -----------------------------
    @staticmethod
    async def _call_openai(
        project_name: str, project_desc: str, objects: List[Dict[str, Any]], events: List[Dict[str, Any]]
    ) -> str:
        prompt = f"""
你是 Mermaid classDiagram 產生器。請根據「BCE 物件 + 三段式事件列表」輸出「可被 Mermaid v11 解析」的 classDiagram。
專案：{project_name}
說明：{project_desc}

【BCE 物件】
{json.dumps(objects, ensure_ascii=False, indent=2)}

【三段式事件列表（全專案）】
{json.dumps(events, ensure_ascii=False, indent=2)}

硬性規則（務必遵守）：
1) 只輸出 JSON：{{"mermaid_code":"..."}}
2) mermaid_code 第一行必須是 classDiagram
3) identifier 只能 [A-Za-z0-9_]
4) 中文要保留在圖上顯示：必須用 alias：class "中文" as EnglishId
5) class identifier 必須唯一
6) 關聯端點只能用 EnglishId（不可中文端點）
7) 型別用保守：string/int/float/bool/void 或 Type[]
8) ✅ class 內部成員語法一律使用冒號：
   - 屬性：+name: type
   - 方法：+method(params): returnType
""".strip()

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": "只輸出 JSON（json_object）。mermaid_code 必須是 Mermaid classDiagram 且 Mermaid v11 可解析。"},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 4096,
        }

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(API_URL, headers=HEADERS, json=payload, timeout=120) as resp:
                        if resp.status != 200:
                            await asyncio.sleep(1.5)
                            continue
                        data = await resp.json()

                text = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                if "```" in text:
                    text = text.replace("```json", "").replace("```", "").strip()
                if "{" in text and "}" in text:
                    text = text[text.find("{") : text.rfind("}") + 1]

                obj = json.loads(clean_json_text(text))
                mermaid = (obj.get("mermaid_code") or "").strip()
                if "classDiagram" in mermaid and not mermaid.startswith("classDiagram"):
                    mermaid = mermaid[mermaid.find("classDiagram") :].strip()
                return mermaid
            except Exception:
                await asyncio.sleep(1.5)

        return ""

    # -----------------------------
    # Public APIs
    # -----------------------------
    @classmethod
    async def generate_class_for_project(cls, project_id: int, db: Optional[Any] = None) -> str:
        objects = await cls._collect_objects(project_id)
        if not objects:
            cls._dbg(f"[CLASS] project_id={project_id} -> objects EMPTY => return header only")
            return "classDiagram\n"

        events = await cls._collect_events_for_project(project_id, db=db)

        project_name = ""
        project_desc = ""
        p = cls._get_current_project_from_storage()
        if p and int(p.get("id")) == int(project_id):
            project_name = str(p.get("name") or "")
            project_desc = str(p.get("description") or "")
        else:
            info = await cls._load_project_info_from_db(db, project_id)
            project_name = info["name"]
            project_desc = info["description"]

        mermaid = await cls._call_openai(project_name, project_desc, objects, events)
        cls._dbg(f"[CLASS] openai_return_len={len(mermaid or '')}")

        # ✅ 關鍵：不管模型吐什麼，最後都會被 normalize 成 Mermaid v11 友善語法
        return cls._normalize_mermaid_classdiagram(mermaid or "classDiagram\n")

    @classmethod
    async def generate_class_for_current_project(cls, db: Optional[Any] = None) -> str:
        p = cls._get_current_project_from_storage()
        if not p:
            cls._dbg("[CLASS] no current_project in storage -> return header only")
            return "classDiagram\n"
        return await cls.generate_class_for_project(int(p["id"]), db=db)