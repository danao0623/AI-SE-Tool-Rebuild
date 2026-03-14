# utils/diagram_converters.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import re


class DiagramConverters:
    # ------------------------------
    # helpers
    # ------------------------------
    @staticmethod
    async def _table_exists(db, name: str) -> bool:
        cur = await db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
        )
        row = await cur.fetchone()
        await cur.close()
        return row is not None

    @staticmethod
    def _safe_id(name: str) -> str:
        # Mermaid 對中文/空白不穩，這裡轉成可用 identifier（顯示名稱仍可用原字串）
        s = (name or "").strip()
        if not s:
            return "X"
        s = re.sub(r"\s+", "_", s)
        s = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff]", "_", s)
        return s

    @staticmethod
    def _to_table_name(name: str) -> str:
        # ERD 表名：保守做法，若本來是英文就大寫；中文交給原字串（或你可以自訂翻譯表）
        s = (name or "").strip()
        if not s:
            return "TABLE"
        if re.match(r"^[A-Za-z0-9_]+$", s):
            return s.upper()
        return s  # 中文先保留，至少可渲染

    @staticmethod
    def _guess_type(attr_type: str) -> str:
        t = (attr_type or "").lower()
        if any(k in t for k in ["int", "integer", "id"]):
            return "int"
        if any(k in t for k in ["float", "double", "decimal"]):
            return "float"
        if any(k in t for k in ["bool", "boolean"]):
            return "bool"
        if any(k in t for k in ["date", "time"]):
            return "datetime"
        if any(k in t for k in ["text"]):
            return "text"
        return "string"

    # ------------------------------
    # ERD
    # ------------------------------
    @classmethod
    async def erd_from_db(cls, db, project_id: int) -> str:
        """
        盡量用 entity_relationship_objects（如果你有存）畫關係，
        否則退回 objects + attributes 用 *_id 推 FK。
        """
        # 優先用你 ERD 子表（若存在）
        if await cls._table_exists(db, "entity_relationship_objects"):
            # 典型欄位猜測：id, er_diagram_id, name, columns_json, ...
            # 但你資料模型顯示關聯是 entity_relationship_diagrams -> entity_relationship_object:contentReference[oaicite:1]{index=1}
            # 這裡採「保守」：能抓到 name/fields 就畫表；關聯抓不到就不畫關係線
            try:
                cur = await db.execute(
                    """
                    SELECT erd.id AS erd_id, erd.project_id AS project_id, erd.mermaid_code AS mermaid_code
                    FROM entity_relationship_diagrams erd
                    WHERE erd.project_id = ?
                    ORDER BY erd.id DESC
                    LIMIT 1
                    """,
                    (project_id,),
                )
                row = await cur.fetchone()
                await cur.close()
                # 若 DB 已經有 mermaid_code，converter 直接回它（最穩）
                if row and row[2]:
                    return str(row[2])
            except Exception:
                pass

        # fallback：用 objects + attributes
        entities: List[Dict[str, Any]] = []
        for table_name in ("objects", "project_objects", "uml_objects"):
            if await cls._table_exists(db, table_name):
                # 盡量相容：id, project_id, name, obj_type/type
                rows = await (await db.execute(
                    f"SELECT * FROM {table_name} WHERE project_id = ?",
                    (project_id,),
                )).fetchall()
                for r in rows:
                    d = dict(r)
                    obj_type = (d.get("obj_type") or d.get("type") or d.get("object_type") or "")
                    if str(obj_type).lower() != "entity":
                        continue
                    entities.append(d)
                break

        # 抓 attributes
        entity_attrs: Dict[int, List[Tuple[str, str]]] = {}
        attr_table_candidates = ("attributes", "object_attributes", "uml_attributes")
        attr_table = next((t for t in attr_table_candidates if await cls._table_exists(db, t)), None)
        if attr_table:
            for ent in entities:
                oid = int(ent.get("id") or 0)
                if oid <= 0:
                    continue
                rows = await (await db.execute(
                    f"SELECT * FROM {attr_table} WHERE object_id = ? ORDER BY id ASC",
                    (oid,),
                )).fetchall()
                cols: List[Tuple[str, str]] = []
                for r in rows:
                    d = dict(r)
                    cols.append((str(d.get("name") or ""), str(d.get("type") or "")))
                entity_attrs[oid] = cols

        # 建表
        lines: List[str] = ["erDiagram"]
        name_to_table: Dict[str, str] = {}
        for ent in entities:
            oid = int(ent.get("id") or 0)
            raw_name = str(ent.get("name") or f"Entity_{oid}")
            tname = cls._to_table_name(raw_name)
            name_to_table[raw_name] = tname
            lines.append(f"  {tname} {{")
            cols = entity_attrs.get(oid, [])
            # 如果沒欄位，至少給 id
            if not cols:
                lines.append("    int id PK")
            else:
                for col_name, col_type in cols:
                    cn = (col_name or "").strip() or "field"
                    mt = cls._guess_type(col_type)
                    # PK 推斷
                    if cn.lower() == "id":
                        lines.append(f"    {mt} {cn} PK")
                    elif cn.lower().endswith("_id"):
                        lines.append(f"    {mt} {cn} FK")
                    else:
                        lines.append(f"    {mt} {cn}")
            lines.append("  }")

        # 畫關係（保守：只用 *_id 且對得上另一張表才畫）
        # 例：order.user_id -> USER
        # 這裡用欄位名去掉 _id 比對表名（英文大寫比對）
        table_set = {cls._to_table_name(str(e.get("name") or "")) for e in entities}
        for ent in entities:
            oid = int(ent.get("id") or 0)
            from_table = cls._to_table_name(str(ent.get("name") or f"Entity_{oid}"))
            cols = entity_attrs.get(oid, [])
            for col_name, _ in cols:
                cn = (col_name or "").strip()
                if not cn.lower().endswith("_id"):
                    continue
                base = cn[:-3]  # remove _id
                if not base:
                    continue
                # 嘗試匹配：base / base+s / base upper
                candidates = [
                    base,
                    base.upper(),
                    f"{base}s",
                    f"{base}_s",
                ]
                to_table = None
                for c in candidates:
                    t = cls._to_table_name(c)
                    if t in table_set:
                        to_table = t
                        break
                if to_table:
                    # 先畫常見 1:N（保守）
                    lines.append(f"  {to_table} ||--o{{ {from_table} : has")

        return "\n".join(lines) + "\n"

    # ------------------------------
    # CLASS DIAGRAM
    # ------------------------------
    @classmethod
    async def class_from_db(cls, db, project_id: int) -> str:
        # objects
        obj_table = next(
            (t for t in ("objects", "project_objects", "uml_objects") if await cls._table_exists(db, t)),
            None,
        )
        if not obj_table:
            return "classDiagram\n"

        objs = await (await db.execute(
            f"SELECT * FROM {obj_table} WHERE project_id = ? ORDER BY id ASC",
            (project_id,),
        )).fetchall()

        # attributes
        attr_table = next(
            (t for t in ("attributes", "object_attributes", "uml_attributes") if await cls._table_exists(db, t)),
            None,
        )
        # methods
        method_table = next(
            (t for t in ("methods", "object_methods", "uml_methods") if await cls._table_exists(db, t)),
            None,
        )

        attr_map: Dict[int, List[str]] = {}
        if attr_table:
            for r in objs:
                d = dict(r)
                oid = int(d.get("id") or 0)
                rows = await (await db.execute(
                    f"SELECT * FROM {attr_table} WHERE object_id = ? ORDER BY id ASC",
                    (oid,),
                )).fetchall()
                attr_map[oid] = [
                    f"+{(dict(a).get('name') or '').strip()}"
                    for a in rows
                    if (dict(a).get("name") or "").strip()
                ]

        method_map: Dict[int, List[str]] = {}
        if method_table:
            for r in objs:
                d = dict(r)
                oid = int(d.get("id") or 0)
                rows = await (await db.execute(
                    f"SELECT * FROM {method_table} WHERE object_id = ? ORDER BY id ASC",
                    (oid,),
                )).fetchall()
                method_map[oid] = [
                    f"+{(dict(m).get('name') or '').strip()}()"
                    for m in rows
                    if (dict(m).get("name") or "").strip()
                ]

        lines: List[str] = ["classDiagram"]
        id_to_name: Dict[int, str] = {}

        for r in objs:
            d = dict(r)
            oid = int(d.get("id") or 0)
            name = str(d.get("name") or f"Object_{oid}")
            cname = cls._safe_id(name)
            id_to_name[oid] = cname

            lines.append(f"  class {cname} {{")
            for a in attr_map.get(oid, []):
                lines.append(f"    {a}")
            for m in method_map.get(oid, []):
                lines.append(f"    {m}")
            lines.append("  }")

        # 關聯：若你有 relations table，盡量畫；沒有就略過（避免亂畫）
        rel_table = next(
            (t for t in ("object_relations", "relations", "uml_relations") if await cls._table_exists(db, t)),
            None,
        )
        if rel_table:
            rels = await (await db.execute(
                f"SELECT * FROM {rel_table} WHERE project_id = ?",
                (project_id,),
            )).fetchall()
            for rr in rels:
                rd = dict(rr)
                a = int(rd.get("from_object_id") or rd.get("from_id") or 0)
                b = int(rd.get("to_object_id") or rd.get("to_id") or 0)
                if a in id_to_name and b in id_to_name:
                    lines.append(f"  {id_to_name[a]} --> {id_to_name[b]}")

        return "\n".join(lines) + "\n"

    # ------------------------------
    # SEQUENCE DIAGRAM
    # ------------------------------
    @classmethod
    async def sequence_from_db(cls, db, project_id: int, usecase_id: int) -> str:
        # UseCase 名稱
        uc_name = f"UseCase_{usecase_id}"
        try:
            if await cls._table_exists(db, "use_cases"):
                cur = await db.execute(
                    "SELECT name FROM use_cases WHERE id=? AND project_id=? LIMIT 1",
                    (usecase_id, project_id),
                )
                row = await cur.fetchone()
                await cur.close()
                if row and row[0]:
                    uc_name = str(row[0])
        except Exception:
            pass

        # events：你專案是三段式事件列表（type/description/sequence_no），ObjectAgent 也是這樣收集:contentReference[oaicite:2]{index=2}
        # 這裡嘗試幾種常見表名
        event_table = next(
            (t for t in ("events", "event_items", "usecase_events") if await cls._table_exists(db, t)),
            None,
        )
        if not event_table:
            # 最小可渲染骨架，避免前端卡死
            safe_uc = cls._safe_id(uc_name)
            return (
                "sequenceDiagram\n"
                f"  participant UC as {safe_uc}\n"
                "  UC-->>UC: (no events)\n"
            )

        # 嘗試找到 event_list_id -> use_case_id 的關係
        # 常見：event_lists(id,use_case_id,list_type) + events(event_list_id,...)
        if await cls._table_exists(db, "event_lists"):
            rows = await (await db.execute(
                """
                SELECT e.sequence_no, e.type, e.description
                FROM events e
                JOIN event_lists el ON el.id = e.event_list_id
                WHERE el.use_case_id = ?
                ORDER BY e.sequence_no ASC, e.id ASC
                """,
                (usecase_id,),
            )).fetchall()
        else:
            # 退而求其次：events 可能直接有 use_case_id
            rows = await (await db.execute(
                f"""
                SELECT sequence_no, type, description
                FROM {event_table}
                WHERE use_case_id = ?
                ORDER BY sequence_no ASC, id ASC
                """,
                (usecase_id,),
            )).fetchall()

        # participants：為了穩定，先用「Actor / System」兩個
        # 你若未來想更精準，把事件結構補上 sender/receiver 再擴充即可
        lines: List[str] = ["sequenceDiagram"]
        lines.append("  actor User")
        lines.append("  participant System")

        for r in rows:
            d = dict(r)
            et = str(d.get("type") or "").strip()
            desc = str(d.get("description") or "").strip()
            if not desc:
                continue

            # 粗略映射：Request=User->System, Process=System->System, Response=System-->>User
            if et in ("Request", "request", "REQ", "請求"):
                lines.append(f"  User->>System: {desc}")
            elif et in ("Response", "response", "RES", "回應"):
                lines.append(f"  System-->>User: {desc}")
            else:
                lines.append(f"  System->>System: {desc}")

        if len(lines) <= 3:
            lines.append("  System-->>User: (no events)")

        return "\n".join(lines) + "\n"