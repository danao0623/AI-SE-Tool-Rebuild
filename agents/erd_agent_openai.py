from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import json
import asyncio
import aiohttp
import re
import os

from nicegui import app

from api.api_sys_openai import API_URL, HEADERS, MODEL_NAME  # type: ignore
from utils.json_cleaner import clean_json_text  # type: ignore

from controllers.object_controller import ObjectController  # type: ignore
from controllers.attribute_controller import AttributeController  # type: ignore

# 可選：如果你專案有事件 controller（沒有也沒關係）
try:
    from controllers.event_controller import EventController  # type: ignore
except Exception:
    EventController = None  # type: ignore


class ERDAgent:
    """
    目標：讓 Mermaid 11.x（含 11.0.2）不再因 LLM 回傳不嚴謹而炸 Syntax error

    兩層防護：
      1) Prompt 強約束（降低違規）
      2) 輸出後 Validator/Auto-fix（即使違規也修到可解析）

    Debug 使用方式：
      - 設定環境變數 ERD_DEBUG=1 會印出收集資料與 prompt 長度等資訊
      - 建議呼叫端傳入 db（aio-sqlite connection）以確保抓到 event_lists/events
    """

    # Mermaid 11 相容型別（最穩集合）
    MERMAID_TYPES = {"string", "int", "float", "boolean", "date"}

    # ----------------------------
    # Debug
    # ----------------------------
    @staticmethod
    def _debug_enabled() -> bool:
        return str(os.getenv("ERD_DEBUG", "0")).strip() in {"1", "true", "True", "YES", "yes"}

    @classmethod
    def _debug_print(cls, msg: str) -> None:
        if cls._debug_enabled():
            print(msg)

    @classmethod
    def _debug_input_summary(
        cls,
        project_id: int,
        entities: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        prompt_len: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not cls._debug_enabled():
            return

        cls._debug_print(f"[ERD][INPUT] project_id={project_id} entities={len(entities)} events={len(events)}")
        if prompt_len is not None:
            cls._debug_print(f"[ERD][PROMPT] chars={prompt_len}")
        if extra:
            cls._debug_print(f"[ERD][EXTRA] {extra}")

        for i, ent in enumerate((entities or [])[:5], start=1):
            tname = ent.get("table_name")
            oname = ent.get("object_name")
            cols = ent.get("attributes") or []
            cls._debug_print(f"[ERD][ENTITY#{i}] object='{oname}' table='{tname}' cols={len(cols)}")
            for c in cols[:5]:
                cls._debug_print(f"  - col={c.get('col')} type={c.get('type')} (src='{c.get('name')}')")

        for i, ev in enumerate((events or [])[:8], start=1):
            desc = str(ev.get("desc") or "")
            desc = (desc[:60] + "...") if len(desc) > 60 else desc
            cls._debug_print(
                f"[ERD][EVENT#{i}] uc_id={ev.get('usecase_id')} seq={ev.get('seq')} "
                f"type={ev.get('type')} desc='{desc}'"
            )

        if len(entities) == 0:
            cls._debug_print("[ERD][WARN] entities=0：代表 BCE 的 Entity 沒抓到（project_id 或 Object/Attribute 資料可能有問題）")
        if len(events) == 0:
            cls._debug_print("[ERD][WARN] events=0：三段式事件列表沒抓到（常見原因：呼叫端未傳 db、或 DB 內 event_lists/events 為空/或欄位過濾條件不匹配）")

    # ----------------------------
    # Helpers
    # ----------------------------
    @staticmethod
    def _get_current_project() -> Dict[str, Any]:
        project = app.storage.user.get("current_project")
        if not project or not project.get("id"):
            raise RuntimeError("no_current_project")
        return project

    @staticmethod
    def _sanitize_text(s: str) -> str:
        s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
        s = s.replace("\n", " ")
        s = s.replace('"', "'")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def _to_table_name(raw: str) -> str:
        s = (raw or "").strip()
        if not s:
            return "T_UNKNOWN"
        s = re.sub(r"[^A-Za-z0-9]+", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        if not s:
            s = "T_UNKNOWN"
        if s[0].isdigit():
            s = f"T_{s}"
        return s.upper()

    @staticmethod
    def _to_col_name(raw: str) -> str:
        s = (raw or "").strip()
        if not s:
            return "col"
        s = re.sub(r"[^A-Za-z0-9]+", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        if not s:
            s = "col"
        if s[0].isdigit():
            s = f"c_{s}"
        return s.lower()

    @classmethod
    def _normalize_mermaid_type(cls, raw: str) -> str:
        """
        將任意型別 -> Mermaid 11 最穩定白名單：string/int/float/boolean/date
        """
        t = (raw or "").strip().lower()
        if not t:
            return "string"

        if any(k in t for k in ["int", "integer", "long", "short"]):
            return "int"
        if any(k in t for k in ["float", "double", "decimal", "number"]):
            return "float"
        if any(k in t for k in ["bool", "boolean"]):
            return "boolean"
        if any(k in t for k in ["date", "time", "datetime", "timestamp"]):
            # Mermaid 11 對 datetime 不穩，統一 date（你也可改 string）
            return "date"
        if any(k in t for k in ["text", "json", "xml", "clob", "blob"]):
            return "string"

        return "string"

    @classmethod
    def _normalize_sql_type(cls, raw: str) -> str:
        # 直接改成 Mermaid 白名單型別，避免把 datetime/bool/text 送進 prompt 造成誘導
        return cls._normalize_mermaid_type(raw)

    @staticmethod
    async def _table_exists(db, name: str) -> bool:
        cur = await db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,))
        row = await cur.fetchone()
        await cur.close()
        return row is not None

    @staticmethod
    async def _table_has_column(db, table: str, col: str) -> bool:
        try:
            cur = await db.execute(f"PRAGMA table_info({table})")
            rows = await cur.fetchall()
            await cur.close()
            for r in rows or []:
                if str(r[1]).strip().lower() == col.strip().lower():
                    return True
        except Exception:
            return False
        return False

    # ----------------------------
    # Entity merge / hint derivation
    # ----------------------------
    @classmethod
    def _merge_entities_by_table(cls, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}

        def attr_key(a: Dict[str, Any]) -> Tuple[str, str]:
            return (str(a.get("col") or "").strip().lower(), str(a.get("type") or "").strip().lower())

        for ent in entities or []:
            t = str(ent.get("table_name") or "").strip().upper()
            if not t:
                continue

            if t not in merged:
                merged[t] = {
                    "object_name": ent.get("object_name") or t,
                    "table_name": t,
                    "description": ent.get("description") or "",
                    "attributes": [],
                }

            base = merged[t]

            d0 = str(base.get("description") or "")
            d1 = str(ent.get("description") or "")
            if len(d1) > len(d0):
                base["description"] = d1

            seen = {attr_key(a) for a in (base.get("attributes") or [])}
            for a in ent.get("attributes") or []:
                if not a.get("col"):
                    continue
                a["type"] = cls._normalize_mermaid_type(str(a.get("type") or "string"))
                k = attr_key(a)
                if k in seen:
                    continue
                seen.add(k)
                base["attributes"].append(a)

        return list(merged.values())

    @classmethod
    def _derive_schema_hints(cls, project: Dict[str, Any], entities: List[Dict[str, Any]], events: List[Dict[str, Any]]) -> Dict[str, Any]:
        text = " ".join([str(e.get("desc") or "") for e in (events or [])]).lower()
        name = str(project.get("name") or "").lower()
        desc = str(project.get("description") or "").lower()
        all_text = f"{name} {desc} {text}"

        def has_any(keys: List[str]) -> bool:
            return any(k.lower() in all_text for k in keys)

        is_course_system = has_any(["選課", "修課", "course", "enroll", "enrollment"])
        is_attendance = has_any(["點名", "出席", "缺席", "attendance", "check-in", "check in"])

        existing_tables = {str(e.get("table_name") or "").upper() for e in (entities or [])}

        return {
            "is_course_system": is_course_system,
            "is_attendance": is_attendance,
            "existing_tables": sorted(list(existing_tables)),
            "force_enrollment_table": bool(is_course_system and "ENROLLMENT" not in existing_tables),
            "force_attendance_tables": bool(
                is_attendance and ("ATTENDANCE_SESSION" not in existing_tables and "ATTENDANCE_RECORD" not in existing_tables)
            ),
        }

    # ----------------------------
    # Data collection
    # ----------------------------
    @classmethod
    async def _collect_entities_from_bce(cls, project_id: int) -> List[Dict[str, Any]]:
        objs = await ObjectController.list(project_id=project_id)
        entities: List[Dict[str, Any]] = []

        for o in objs or []:
            obj_type = str(getattr(o, "obj_type", "") or getattr(o, "type", "") or "").strip().lower()
            if obj_type != "entity":
                continue

            oid = int(getattr(o, "id"))
            obj_name = str(getattr(o, "name", "") or "").strip()
            desc = str(getattr(o, "description", "") or "").strip()

            attrs = await AttributeController.list(object_id=oid)
            cols: List[Dict[str, str]] = []
            for a in attrs or []:
                an = str(getattr(a, "name", "") or "").strip()
                at = str(getattr(a, "type", "") or "").strip()
                if not an:
                    continue
                cols.append({"name": an, "col": cls._to_col_name(an), "type": cls._normalize_sql_type(at)})

            entities.append(
                {
                    "object_name": obj_name,
                    "table_name": cls._to_table_name(obj_name),
                    "description": desc,
                    "attributes": cols,
                }
            )

        return cls._merge_entities_by_table(entities)

    @classmethod
    async def _collect_events_for_project(cls, project_id: int, db: Optional[Any] = None) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []

        # 1) db 模式（最穩）
        if db is not None:
            try:
                has_el = await cls._table_exists(db, "event_lists")
                has_e = await cls._table_exists(db, "events")
                has_uc = await cls._table_exists(db, "use_cases")

                if has_el and has_e:
                    use_uc_project = False
                    use_el_project = False

                    if has_uc:
                        use_uc_project = await cls._table_has_column(db, "use_cases", "project_id")
                    use_el_project = await cls._table_has_column(db, "event_lists", "project_id")

                    if has_uc and use_uc_project:
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
                        cur = await db.execute(sql, (project_id,))
                    elif use_el_project:
                        sql = """
                        SELECT
                          el.use_case_id AS usecase_id,
                          '' AS usecase_name,
                          e.sequence_no AS seq,
                          e.type AS type,
                          e.description AS desc
                        FROM events e
                        JOIN event_lists el ON el.id = e.event_list_id
                        WHERE el.project_id = ?
                        ORDER BY el.use_case_id ASC, e.sequence_no ASC, e.id ASC
                        """
                        cur = await db.execute(sql, (project_id,))
                    else:
                        sql = """
                        SELECT
                          el.use_case_id AS usecase_id,
                          '' AS usecase_name,
                          e.sequence_no AS seq,
                          e.type AS type,
                          e.description AS desc
                        FROM events e
                        JOIN event_lists el ON el.id = e.event_list_id
                        ORDER BY el.use_case_id ASC, e.sequence_no ASC, e.id ASC
                        """
                        cur = await db.execute(sql)

                    rows = await cur.fetchall()
                    await cur.close()

                    for r in rows or []:
                        if not r:
                            continue
                        desc = str(r[4] or "").strip()
                        if not desc:
                            continue
                        events.append(
                            {
                                "usecase_id": r[0],
                                "usecase_name": r[1],
                                "seq": r[2],
                                "type": r[3],
                                "desc": cls._sanitize_text(desc),
                            }
                        )
                    return events
            except Exception as e:
                cls._debug_print(f"[ERD][WARN] db event query failed: {type(e).__name__}: {e}")

        # 2) controller 模式（若你專案有 EventController）
        if EventController is not None:
            try:
                es = await EventController.list(project_id=project_id)  # type: ignore
                for e in es or []:
                    desc = str(getattr(e, "description", "") or "").strip()
                    if not desc:
                        continue
                    events.append(
                        {
                            "usecase_id": getattr(e, "use_case_id", None),
                            "usecase_name": "",
                            "seq": getattr(e, "sequence_no", None),
                            "type": getattr(e, "type", None),
                            "desc": cls._sanitize_text(desc),
                        }
                    )
            except Exception as e:
                cls._debug_print(f"[ERD][WARN] controller event list failed: {type(e).__name__}: {e}")
                return []

        return events

    # ----------------------------
    # Mermaid sanitize / validate / auto-fix
    # ----------------------------
    @staticmethod
    def _sanitize_mermaid(mermaid: str) -> str:
        """
        只做最基本清理：去 code fence、截到 erDiagram 開頭。
        真正防炸靠 _validate_and_fix_mermaid_erd()
        """
        s = (mermaid or "").strip()
        if not s:
            return ""
        s = s.replace("```mermaid", "").replace("```json", "").replace("```", "").strip()
        if "erDiagram" in s and not s.startswith("erDiagram"):
            s = s[s.find("erDiagram") :].strip()
        s = s.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not s.startswith("erDiagram"):
            return ""
        return s

    @classmethod
    def _sanitize_table_name_strict(cls, name: str) -> str:
        name = (name or "").strip()
        name = re.sub(r"[^A-Za-z0-9_]", "_", name)
        name = re.sub(r"_+", "_", name).strip("_")
        if not name:
            name = "T_UNKNOWN"
        if name[0].isdigit():
            name = "T_" + name
        return name.upper()

    @classmethod
    def _sanitize_col_name_strict(cls, name: str) -> str:
        name = (name or "").strip()
        name = re.sub(r"[^A-Za-z0-9_]", "_", name)
        name = re.sub(r"_+", "_", name).strip("_")
        if not name:
            name = "col"
        if name[0].isdigit():
            name = "c_" + name
        return name.lower()

    @classmethod
    def _fix_relationship_line(cls, line: str) -> Optional[str]:
        """
        只允許標準 relationship line，否則回 None 丟棄：
          A ||--o{ B : label
        """
        s = (line or "").strip()
        if not s:
            return None

        # 常見雷：o{{、引號
        s = s.replace("o{{", "o{").replace('"', "").replace("'", "")
        s = re.sub(r"\s+", " ", s).strip()

        # 允許的箭頭集合（可視需要擴充）
        # 這裡只保留你目前最常用的 ||--o{
        # 若你需要其他如 }o--|| 也能在這裡加入
        m = re.match(r"^([A-Za-z0-9_]+)\s*\|\|--o\{\s*([A-Za-z0-9_]+)\s*:\s*([A-Za-z0-9_ ]+)$", s)
        if not m:
            return None

        a = cls._sanitize_table_name_strict(m.group(1))
        b = cls._sanitize_table_name_strict(m.group(2))
        label = m.group(3).strip()
        label = re.sub(r"[^A-Za-z0-9_ ]", "", label)
        label = re.sub(r"\s+", " ", label).strip()
        if not label:
            label = "rel"

        return f"{a} ||--o{{ {b} : {label}"

    @classmethod
    def _validate_and_fix_mermaid_erd(cls, code: str) -> str:
        """
        Mermaid 11 防炸核心：
          - 丟棄不合法行，只保留：erDiagram + table blocks + relationship lines
          - 修正關係符號、型別、命名、欄位格式
          - 每表最多 1 個 PK；無 PK 自動補 surrogate key：int <table>_id PK
        """
        if not code or not code.strip():
            return "erDiagram\n"

        src = code.replace("\r\n", "\n").replace("\r", "\n")
        lines = src.split("\n")

        out: List[str] = ["erDiagram"]
        out.append("")

        in_table = False
        current_table: Optional[str] = None
        current_cols: List[str] = []
        pk_seen = 0

        def flush_table() -> None:
            nonlocal in_table, current_table, current_cols, pk_seen, out
            if not in_table or not current_table:
                return

            # 若沒有 PK，補 surrogate key
            if pk_seen == 0:
                current_cols.insert(0, f"  int {current_table.lower()}_id PK")
                pk_seen = 1

            out.append(f"  {current_table} {{")
            out.extend(current_cols)
            out.append("  }")
            out.append("")

            in_table = False
            current_table = None
            current_cols = []
            pk_seen = 0

        for raw in lines:
            line = raw.strip()
            if not line:
                continue

            if line == "erDiagram":
                continue

            # table header
            mh = re.match(r"^([A-Za-z0-9_]+)\s*\{\s*$", line)
            if mh:
                flush_table()
                in_table = True
                current_table = cls._sanitize_table_name_strict(mh.group(1))
                current_cols = []
                pk_seen = 0
                continue

            # table end
            if in_table and line == "}":
                flush_table()
                continue

            # inside table: field line
            if in_table and current_table:
                # 清掉可能炸的符號（欄位行不該有 : , ( ) [ ] ; 等）
                cleaned = re.sub(r"[,\(\)\[\]:;]", " ", line)
                cleaned = re.sub(r"\s+", " ", cleaned).strip()
                parts = cleaned.split(" ")

                if len(parts) < 2:
                    # 不完整欄位行：丟棄
                    continue

                col_type = cls._normalize_mermaid_type(parts[0])
                col_name = cls._sanitize_col_name_strict(parts[1])

                mods = {p.upper() for p in parts[2:]}
                out_mods: List[str] = []

                # PK：每表最多 1 個
                if "PK" in mods and pk_seen == 0:
                    out_mods.append("PK")
                    pk_seen += 1

                # FK：可多個
                if "FK" in mods:
                    out_mods.append("FK")

                current_cols.append("  " + " ".join([col_type, col_name] + out_mods))
                continue

            # not in table: relationship line
            rel = cls._fix_relationship_line(line)
            if rel:
                out.append(rel)
                continue

            # 其他雜訊：全部丟棄（避免 Mermaid 解析炸）
            continue

        # 收尾：若 table 沒閉合也 flush（容錯）
        if in_table:
            flush_table()

        # 保底
        result = "\n".join(out).strip() + "\n"
        if result.strip() == "erDiagram":
            return "erDiagram\n"
        return result

    # ----------------------------
    # Prompt rules
    # ----------------------------
    @classmethod
    def _build_prompt_rules(cls, hints: Dict[str, Any]) -> str:
        rules: List[str] = []

        # A) 建模（正規化）
        rules.append("以資料庫正規化建模：不要用清單字串欄位表示多對多（例如 enrolled_courses）。")
        rules.append("能推導多對多就建立中介表（join table），包含兩端 FK。")
        rules.append("避免冗餘欄位（可由 FK join 得到的不要重複存），除非事件明確要求快照。")
        rules.append("每張表使用單一代理鍵 PK（例如 int xxx_id PK）。避免複合主鍵（Mermaid 相容性差）。")

        # B) Mermaid 語法（硬約束）
        rules.append("只允許輸出 Mermaid ERD（erDiagram）。")
        rules.append("表名：全大寫底線（A-Z0-9_）。欄位名：小寫底線（a-z0-9_）。")
        rules.append("欄位行格式必須是：`<type> <column> [PK] [FK]`，修飾詞只能用空白分隔，禁止逗號。")
        rules.append("欄位型別只允許：string/int/float/boolean/date（禁止 datetime/bool/text）。")
        rules.append("欄位行禁止出現：逗號、括號、冒號、分號等符號。")
        rules.append("關係行使用：`A ||--o{ B : label`，label 不要加引號。禁止 `o{{`。")

        # C) 情境強化
        if hints.get("force_enrollment_table"):
            rules.append(
                "若事件有選課/修課/enroll，必須建立 ENROLLMENT："
                "ENROLLMENT { int enrollment_id PK string student_id FK string course_id FK date enrolled_at }，"
                "並建立 STUDENT ||--o{ ENROLLMENT 與 COURSE ||--o{ ENROLLMENT。"
            )

        if hints.get("force_attendance_tables"):
            rules.append(
                "若事件有點名/出席/attendance，必須建立："
                "ATTENDANCE_SESSION { int session_id PK string course_id FK date session_time }"
                "與 ATTENDANCE_RECORD { int record_id PK int session_id FK string student_id FK string status }，"
                "並建立 COURSE ||--o{ ATTENDANCE_SESSION、ATTENDANCE_SESSION ||--o{ ATTENDANCE_RECORD、STUDENT ||--o{ ATTENDANCE_RECORD。"
            )

        return "\n".join([f"- {r}" for r in rules])

    # ----------------------------
    # OpenAI call
    # ----------------------------
    @classmethod
    async def _call_openai(cls, project: Dict[str, Any], entities: List[Dict[str, Any]], events: List[Dict[str, Any]]) -> str:
        hints = cls._derive_schema_hints(project, entities, events)
        rule_text = cls._build_prompt_rules(hints)

        prompt = f"""
你是一位資深系統分析師與資料庫設計師。請根據「BCE 的 Entity 物件 + 三段式事件列表」產生 Mermaid ERD（erDiagram）。
重點：關係盡量從事件描述推導；不確定就保守處理，但必須符合資料庫建模規範。

專案：{project.get("name","")}
說明：{project.get("description","")}

【硬性規則（必須逐條遵守）】
{rule_text}

【Entity 物件（BCE Entity，已合併去重）】
{json.dumps(entities, ensure_ascii=False, indent=2)}

【三段式事件列表（全專案）】
{json.dumps(events, ensure_ascii=False, indent=2)}

輸出規範（非常重要）：
1) 只輸出 JSON（禁止 Markdown、禁止解釋）
2) JSON 結構固定：{{"mermaid_code":"erDiagram\\n  ...\\n"}}
3) mermaid_code 必須以 erDiagram 開頭
4) 只能輸出表 blocks 與關係行，不要輸出任何其他文字
5) 欄位型別只允許：string/int/float/boolean/date
6) 每張表只允許 1 個 PK（使用代理鍵），避免複合 PK
""".strip()

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": "只輸出 JSON，欄位 mermaid_code 必須是 Mermaid erDiagram。"},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 4096,
        }

        if cls._debug_enabled():
            cls._debug_print(f"[ERD][PROMPT] chars={len(prompt)}")
            cls._debug_print(f"[ERD][HINTS] {hints}")

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(API_URL, headers=HEADERS, json=payload, timeout=120) as resp:
                        if resp.status != 200:
                            try:
                                print(f"❌ ERD API {resp.status}: {await resp.text()}")
                            except Exception:
                                print(f"❌ ERD API {resp.status}")
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
                return mermaid

            except Exception as e:
                print(f"⚠️ ERD attempt {attempt+1} failed: {type(e).__name__}: {e}")
                await asyncio.sleep(1.5)

        return ""

    # ----------------------------
    # Public API
    # ----------------------------
    @classmethod
    async def generate_erd_for_current_project(cls, db: Optional[Any] = None) -> str:
        project = cls._get_current_project()
        project_id = int(project["id"])

        entities = await cls._collect_entities_from_bce(project_id)
        events = await cls._collect_events_for_project(project_id, db=db)

        cls._debug_input_summary(
            project_id,
            entities,
            events,
            extra={
                "entity_tables": [e.get("table_name") for e in entities[:10]],
                "event_sample": (events[0].get("desc") if events else None),
            },
        )

        if not entities:
            return "erDiagram\n"

        mermaid = await cls._call_openai(project, entities, events)
        mermaid = cls._sanitize_mermaid(mermaid)
        mermaid = cls._validate_and_fix_mermaid_erd(mermaid)

        return mermaid or "erDiagram\n"