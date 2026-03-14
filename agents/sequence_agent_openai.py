from __future__ import annotations

from typing import Any, Dict, List, Tuple
import json
import asyncio
import aiohttp
import re

from nicegui import app

from api.api_sys_openai import API_URL, HEADERS, MODEL_NAME  # type: ignore
from utils.json_cleaner import clean_json_text  # type: ignore

from controllers.attribute_controller import AttributeController  # type: ignore

try:
    from controllers.method_controller import MethodController  # type: ignore
except Exception:
    MethodController = None  # type: ignore


class SequenceDiagramAgent:
    # ----------------------------
    # DB helpers (aiosqlite style)
    # ----------------------------
    @staticmethod
    async def _table_exists(db, name: str) -> bool:
        cur = await db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,))
        row = await cur.fetchone()
        await cur.close()
        return row is not None

    @classmethod
    async def _load_usecase_name(cls, db, usecase_id: int) -> str:
        try:
            cur = await db.execute("SELECT name FROM use_cases WHERE id=? LIMIT 1", (usecase_id,))
            row = await cur.fetchone()
            await cur.close()
            if row and row[0]:
                return str(row[0])
        except Exception:
            pass
        return f"UseCase_{usecase_id}"

    @classmethod
    async def _load_events_for_usecase(cls, db, usecase_id: int) -> List[Dict[str, Any]]:
        if await cls._table_exists(db, "event_lists") and await cls._table_exists(db, "events"):
            sql = """
            SELECT e.sequence_no AS seq, e.type AS type, e.description AS desc
            FROM events e
            JOIN event_lists el ON el.id = e.event_list_id
            WHERE el.use_case_id = ?
            ORDER BY e.sequence_no ASC, e.id ASC
            """
            cur = await db.execute(sql, (usecase_id,))
            rows = await cur.fetchall()
            await cur.close()
            return [{"seq": r[0], "type": r[1], "desc": r[2]} for r in rows if r and (r[2] or "")]

        if await cls._table_exists(db, "events"):
            try:
                sql = """
                SELECT sequence_no AS seq, type AS type, description AS desc
                FROM events
                WHERE use_case_id = ?
                ORDER BY sequence_no ASC, id ASC
                """
                cur = await db.execute(sql, (usecase_id,))
                rows = await cur.fetchall()
                await cur.close()
                return [{"seq": r[0], "type": r[1], "desc": r[2]} for r in rows if r and (r[2] or "")]
            except Exception:
                return []
        return []

    # ----------------------------
    # Text + Mermaid sanitation
    # ----------------------------
    @staticmethod
    def _sanitize_text(s: str) -> str:
        s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
        s = s.replace("\n", " ")
        s = s.replace('"', "'")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def _sanitize_mermaid(mermaid: str) -> str:
        s = (mermaid or "").strip()
        if not s:
            return ""
        s = s.replace("```mermaid", "").replace("```json", "").replace("```", "").strip()
        if "sequenceDiagram" in s and not s.startswith("sequenceDiagram"):
            s = s[s.find("sequenceDiagram") :].strip()
        s = s.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not s.startswith("sequenceDiagram"):
            return ""
        return s

    @staticmethod
    def _to_ident(name: str, default: str = "Component") -> str:
        raw = (name or "").strip()
        token = re.sub(r"[^A-Za-z0-9_]+", "_", raw).strip("_")
        if not token:
            token = default
        if not re.match(r"^[A-Za-z]", token):
            token = f"{default}_{token}"
        return token

    # ----------------------------
    # BCE objects (USECASE-scoped)
    # ----------------------------
    @classmethod
    async def _collect_bce_objects_for_usecase(cls, db, project_id: int, usecase_id: int) -> List[Dict[str, Any]]:
        if not await cls._table_exists(db, "objects"):
            return []

        sql = """
        SELECT id, name, type, COALESCE(description, '') AS description, project_id, usecase_id
        FROM objects
        WHERE project_id = ? AND usecase_id = ?
        ORDER BY id ASC
        """
        cur = await db.execute(sql, (project_id, usecase_id))
        rows = await cur.fetchall()
        await cur.close()

        results: List[Dict[str, Any]] = []
        for r in rows or []:
            oid = int(r[0])
            name = str(r[1] or "").strip()
            obj_type = str(r[2] or "").strip()
            desc = str(r[3] or "").strip()

            attr_list: List[str] = []
            try:
                attrs = await AttributeController.list(object_id=oid)  # type: ignore
                for a in attrs or []:
                    an = str(getattr(a, "name", "") or "").strip()
                    at = str(getattr(a, "type", "") or "").strip()
                    if an:
                        attr_list.append(f"{an}: {at or 'string'}")
            except Exception:
                attr_list = []

            methods_list: List[str] = []
            if MethodController is not None:
                try:
                    ms = await MethodController.list(object_id=oid)  # type: ignore
                    for m in ms or []:
                        mn = str(getattr(m, "name", "") or "").strip()
                        rt = str(getattr(m, "type", "") or "").strip()
                        if mn:
                            methods_list.append(f"{mn}(): {rt or 'void'}")
                except Exception:
                    methods_list = []

            ident = cls._to_ident(name, default="Component")

            results.append(
                {
                    "id": oid,
                    "name": name,
                    "ident": ident,
                    "type": obj_type,
                    "description": desc,
                    "attributes": attr_list,
                    "methods": methods_list,
                }
            )
        return results

    # ----------------------------
    # Better event labeling (avoid step_XX)
    # ----------------------------
    @staticmethod
    def _extract_action_from_desc(desc: str) -> str:
        """
        Try to extract an action/method-like token from description.
        Examples:
          - "verifyStudentCredentials(account,password)" -> verifyStudentCredentials
          - "inputLoginInfo(account,password)" -> inputLoginInfo
          - "顯示課程清單 displayCourseList(courses)" -> displayCourseList
        """
        d = (desc or "").strip()
        if not d:
            return ""

        # 1) method(...) pattern
        m = re.search(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", d)
        if m:
            return m.group(1)

        # 2) common verb-like token with underscores/camelcase
        m2 = re.search(r"\b([A-Za-z][A-Za-z0-9_]{3,})\b", d)
        if m2:
            tok = m2.group(1)
            # avoid generic words
            if tok.lower() not in {"user", "system", "success", "fail", "error", "data", "result"}:
                return tok

        return ""

    @classmethod
    def _event_label(cls, ev: Dict[str, Any], idx: int) -> str:
        desc = str(ev.get("desc") or "")
        desc_l = desc.lower()

        # A) Extract method/action first (strongest)
        action = cls._extract_action_from_desc(desc)
        if action:
            return cls._to_ident(action, default=f"Action{idx}")

        # B) Keyword mapping
        rules: List[Tuple[List[str], str]] = [
            (["login", "log in", "sign in", "authenticate", "credential", "登入", "帳號"], "login"),
            (["select course", "course selection", "enroll", "registration", "選課", "加選"], "selectCourse"),
            (["drop course", "withdraw", "退選"], "dropCourse"),
            (["course list", "fetch courses", "available courses", "課程清單"], "getCourseList"),
            (["check eligibility", "eligibility", "資格"], "checkEligibility"),
            (["confirm", "submit", "確認", "送出"], "confirm"),
            (["validate", "check", "verify", "檢查", "驗證"], "validate"),
            (["display", "show", "呈現", "顯示"], "display"),
        ]
        for keys, label in rules:
            for k in keys:
                if k in desc_l:
                    return label

        # C) Short summary fallback (still better than step_XX)
        # Take first 2~4 words of cleaned English-ish tokens
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]*", desc)
        if tokens:
            short = "_".join(tokens[:3])
            return cls._to_ident(short, default=f"Action{idx}")

        # D) Last resort
        return f"Action{idx}"

    @staticmethod
    def _pick_ui_for_label(objects: List[Dict[str, Any]], default_ui_ident: str, label: str) -> str:
        label_l = (label or "").lower()
        boundaries = [o for o in objects if str(o.get("type", "")).lower().startswith("bound")]
        if not boundaries:
            return default_ui_ident

        # Try name-based routing
        for o in boundaries:
            nm = str(o.get("name") or "").lower()
            if label_l.startswith("login") and "login" in nm:
                return str(o.get("ident") or default_ui_ident)
            if ("course" in label_l or "enroll" in label_l or "select" in label_l) and ("course" in nm or "selection" in nm):
                return str(o.get("ident") or default_ui_ident)

        return default_ui_ident

    # ----------------------------
    # Mermaid normalization + validation
    # ----------------------------
    @staticmethod
    def _normalize_and_force_participants(mermaid: str, expected_idents: List[str]) -> str:
        s = (mermaid or "").strip().replace("\r\n", "\n").replace("\r", "\n")
        if not s.startswith("sequenceDiagram"):
            return ""

        lines = [ln.rstrip() for ln in s.splitlines() if ln.strip()]
        if not lines or lines[0].strip() != "sequenceDiagram":
            return ""

        participants: List[str] = []
        body: List[str] = []
        saw_message = False

        for ln in lines[1:]:
            t = ln.strip()

            if t == "actor User":
                continue

            if t.startswith("participant "):
                if " as " in t or '"' in t:
                    body.append(ln)
                    continue
                if saw_message:
                    body.append(ln)
                    continue
                token = t[len("participant ") :].strip()
                if token:
                    participants.append(token)
                continue

            msg = re.match(r"^([A-Za-z][A-Za-z0-9_]*)\s*[-]{1,2}>>\s*([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.+)$", t)
            if msg:
                saw_message = True
                body.append(ln)
                continue

            body.append(ln)

        # Dedup + force expected
        seen: set[str] = set()
        dedup: List[str] = []
        for p in participants:
            if p not in seen:
                seen.add(p)
                dedup.append(p)

        expected_norm = [p for p in expected_idents if p]
        expected_norm = list(dict.fromkeys(expected_norm))
        for p in expected_norm:
            if p not in seen:
                seen.add(p)
                dedup.append(p)

        out: List[str] = ["sequenceDiagram", "  actor User"]
        for p in dedup:
            out.append(f"  participant {p}")
        out.extend(body)
        return "\n".join(out).strip()

    @staticmethod
    def _is_valid_mermaid_sequence(mermaid: str, expected_idents: List[str]) -> bool:
        s = (mermaid or "").strip().replace("\r\n", "\n").replace("\r", "\n")
        if not s.startswith("sequenceDiagram"):
            return False

        ident_re = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
        declared_set: set[str] = set()
        saw_message = False
        actor_user_seen = False

        for line in s.splitlines():
            t = line.strip()
            if not t:
                continue

            if t.startswith("actor "):
                if t != "actor User":
                    return False
                actor_user_seen = True
                continue

            if t.startswith("participant "):
                if saw_message:
                    return False
                if " as " in t or '"' in t:
                    return False
                token = t[len("participant ") :].strip()
                if token == "User" or not ident_re.match(token):
                    return False
                if token in declared_set:
                    return False
                declared_set.add(token)
                continue

            msg = re.match(r"^([A-Za-z][A-Za-z0-9_]*)\s*[-]{1,2}>>\s*([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.+)$", t)
            if msg:
                saw_message = True
                a, b = msg.group(1), msg.group(2)
                if a != "User" and a not in declared_set:
                    return False
                if b != "User" and b not in declared_set:
                    return False
                continue

            if t.startswith(("alt ", "else", "end", "loop ", "opt ", "par ", "and", "rect ", "note ")):
                continue

            return False

        if not actor_user_seen:
            return False

        for p in expected_idents:
            if p and p not in declared_set:
                return False

        return True

    # ----------------------------
    # Rule-based builder (semantic labels)
    # ----------------------------
    @classmethod
    def _build_rule_based_sequence(
        cls,
        usecase_objects: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        usecase_ident: str,
        note: str = "",
    ) -> str:
        boundaries = [o for o in usecase_objects if str(o.get("type", "")).lower().startswith("bound")]
        controls = [o for o in usecase_objects if str(o.get("type", "")).lower().startswith("cont")]
        entities = [o for o in usecase_objects if str(o.get("type", "")).lower().startswith("ent")]

        ui_default = (boundaries[0]["ident"] if boundaries else usecase_objects[0]["ident"])
        ctrl = (controls[0]["ident"] if controls else (usecase_objects[1]["ident"] if len(usecase_objects) > 1 else ui_default))

        lines: List[str] = ["sequenceDiagram", "  actor User"]
        for o in usecase_objects:
            lines.append(f"  participant {o['ident']}")

        if note:
            safe_note = re.sub(r"[\r\n]+", " ", note).strip()
            lines.append(f"  note over User,{ui_default}: {safe_note}")

        # Start
        lines.append(f"  User->>{ui_default}: start_{usecase_ident}")

        for idx, ev in enumerate(events, start=1):
            label = cls._event_label(ev, idx)
            ui = cls._pick_ui_for_label(usecase_objects, ui_default, label)

            # Always use semantic labels (never step_XX)
            lines.append(f"  User->>{ui}: input_{label}")
            lines.append(f"  {ui}->>{ctrl}: handle_{label}")

            if entities:
                e1 = entities[(idx - 1) % len(entities)]["ident"]
                lines.append(f"  {ctrl}->>{e1}: query_{label}")
                lines.append(f"  {e1}-->>{ctrl}: data")

                if len(entities) >= 2:
                    e2 = entities[idx % len(entities)]["ident"]
                    if e2 != e1:
                        lines.append(f"  {ctrl}->>{e2}: validate_{label}")
                        lines.append(f"  {e2}-->>{ctrl}: ok")

            lines.append(f"  {ctrl}-->>{ui}: result_{label}")
            lines.append(f"  {ui}-->>User: display_{label}")

        lines.append(f"  {ui_default}-->>User: done")
        return "\n".join(lines).strip()

    # ----------------------------
    # OpenAI call
    # ----------------------------
    @staticmethod
    async def _call_openai(
        project_name: str,
        project_description: str,
        usecase_id: int,
        usecase_name: str,
        events: List[Dict[str, Any]],
        usecase_objects: List[Dict[str, Any]],
    ) -> str:
        prompt = f"""
You are a senior software architect. Generate a Mermaid `sequenceDiagram` for the DESIGN LEVEL (MVC/BCE).

Project: {project_name}
Description: {project_description}
UseCase: {usecase_name} (id={usecase_id})

[USECASE BCE OBJECTS]
You MUST declare ALL objects as participants (exactly once) using `ident`.
{json.dumps(usecase_objects, ensure_ascii=False, indent=2)}

[3-STEP EVENT LIST]
{json.dumps(events, ensure_ascii=False, indent=2)}

STRICT RULES:
1) Use exactly: `actor User`
2) For EACH usecase object, declare:
   participant <ident>
   - all participants BEFORE any messages
   - no quotes, no alias `as`, no P1/P2 tokens
3) Message endpoints must be User or declared participants only.
4) Use English message labels; prefer action/method style (e.g., verifyStudentCredentials, getCourseList, selectCourse).
5) Reflect the event list; do not output placeholder names like step_1.

Output ONLY JSON:
{{"mermaid_code":"sequenceDiagram\\n...\\n"}}
""".strip()

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": "只輸出 JSON，欄位 mermaid_code 必須是 Mermaid sequenceDiagram。"},
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
                            await asyncio.sleep(1.2)
                            continue
                        data = await resp.json()

                text = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                if "```" in text:
                    text = text.replace("```json", "").replace("```", "").strip()
                if "{" in text and "}" in text:
                    text = text[text.find("{") : text.rfind("}") + 1]

                obj = json.loads(clean_json_text(text))
                mermaid = (obj.get("mermaid_code") or "").strip()
                return mermaid
            except Exception:
                await asyncio.sleep(1.2)

        return ""

    # ----------------------------
    # Public API
    # ----------------------------
    @classmethod
    async def generate_sequence_for_usecase(cls, db, *, project_id: int, usecase_id: int) -> str:
        project = app.storage.user.get("current_project") or {}
        project_name = str(project.get("name", "") or "")
        project_desc = str(project.get("description", "") or "")

        usecase_name = await cls._load_usecase_name(db, usecase_id)
        usecase_name_clean = cls._sanitize_text(usecase_name)
        usecase_ident = cls._to_ident(usecase_name_clean, default="UseCase")

        raw_events = await cls._load_events_for_usecase(db, usecase_id)
        events: List[Dict[str, Any]] = []
        for e in raw_events or []:
            et = cls._sanitize_text(str(e.get("type") or ""))
            desc = cls._sanitize_text(str(e.get("desc") or e.get("description") or ""))
            if not desc:
                continue
            events.append({"seq": e.get("seq"), "type": et, "desc": desc})

        usecase_objects = await cls._collect_bce_objects_for_usecase(db, project_id, usecase_id)
        expected_idents = [o.get("ident") for o in usecase_objects if o.get("ident")]

        if not usecase_objects:
            dummy_objs = [
                {"ident": "LoginInterface", "type": "Boundary", "name": "LoginInterface"},
                {"ident": "CourseSelectionController", "type": "Control", "name": "CourseSelectionController"},
                {"ident": "Student", "type": "Entity", "name": "Student"},
            ]
            return cls._build_rule_based_sequence(dummy_objs, events, usecase_ident, note="no BCE objects found")

        if not events:
            return cls._build_rule_based_sequence(usecase_objects, events, usecase_ident, note="no events found")

        # Try model first
        mermaid = await cls._call_openai(project_name, project_desc, usecase_id, usecase_name_clean, events, usecase_objects)
        mermaid = cls._sanitize_mermaid(mermaid)

        if mermaid:
            mermaid = cls._normalize_and_force_participants(mermaid, expected_idents)
            if cls._is_valid_mermaid_sequence(mermaid, expected_idents):
                return mermaid

        # If model invalid, rule-based with semantic labels (avoids step_XX)
        return cls._build_rule_based_sequence(usecase_objects, events, usecase_ident, note="rule-based (model invalid)")