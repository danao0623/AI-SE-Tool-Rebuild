from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite


class DiagramFlowController:
    # =========================================================
    # Debug switches
    # =========================================================
    DEBUG = True  # ✅ 想安靜就改 False

    @classmethod
    def _dbg(cls, msg: str) -> None:
        if cls.DEBUG:
            print(msg, flush=True)

    # =========================================================
    # DB Path / Connection
    # =========================================================
    @classmethod
    def _resolve_db_path(cls) -> str:
        env_path = os.environ.get("DB_PATH")
        if env_path:
            resolved = env_path
        elif Path("SQL/base.db").exists():
            resolved = "SQL/base.db"
        else:
            resolved = "base.db"

        # ✅ Debug: confirm same DB always
        cls._dbg(f"[DB] DB_PATH_RESOLVED={resolved}")
        return resolved

    @classmethod
    def _conn(cls) -> aiosqlite.Connection:
        return aiosqlite.connect(cls._resolve_db_path(), timeout=30)

    @staticmethod
    async def _fetchone(
        db: aiosqlite.Connection, sql: str, params: Tuple[Any, ...] = ()
    ) -> Optional[aiosqlite.Row]:
        cur = await db.execute(sql, params)
        row = await cur.fetchone()
        await cur.close()
        return row

    @staticmethod
    async def _fetchall(
        db: aiosqlite.Connection, sql: str, params: Tuple[Any, ...] = ()
    ) -> List[aiosqlite.Row]:
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
        await cur.close()
        return list(rows)

    # =========================================================
    # Mermaid sanitize (critical for Mermaid 11 strict parser)
    # =========================================================
    @staticmethod
    def _sanitize_mermaid(diagram_type: str, text: str) -> str:
        """
        清掉 AI 可能混入的 JSON / code fence / 說明文字，並保證以正確 header 開頭。
        若無法修正為合法 header，回傳空字串（避免把壞資料存進 DB）。
        """
        diagram_type = (diagram_type or "").lower().strip()
        s = (text or "").strip()
        if not s:
            return ""

        # ✅ 防 BOM（有些來源會帶 \ufeff，導致 startswith(header) 失敗）
        s = s.lstrip("\ufeff")

        # Remove code fences
        s = s.replace("```mermaid", "").replace("```json", "").replace("```", "").strip()

        # If it is JSON, try extract mermaid_code
        if s.startswith("{") and s.endswith("}"):
            try:
                obj = json.loads(s)
                s = str(obj.get("mermaid_code") or obj.get("mermaid") or s).strip()
            except Exception:
                pass

        header_map = {
            "erd": "erDiagram",
            "class": "classDiagram",
            "sequence": "sequenceDiagram",
        }
        header = header_map.get(diagram_type)

        # Trim prefix before header
        if header and header in s and not s.startswith(header):
            s = s[s.find(header) :].strip()

        # Normalize newlines
        s = s.replace("\r\n", "\n").replace("\r", "\n").strip()

        # Must start with header
        if header and not s.startswith(header):
            return ""

        # Remove trailing odd JSON braces if any slipped
        if header and "\n{" in s:
            s = s.split("\n{", 1)[0].rstrip()

        return s

    # =========================================================
    # UseCase utilities
    # =========================================================
    @classmethod
    async def list_usecases(cls, project_id: int) -> List[Dict[str, Any]]:
        async with cls._conn() as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys=ON")
            rows = await cls._fetchall(
                db,
                "SELECT id, name FROM use_cases WHERE project_id = ? ORDER BY id ASC",
                (int(project_id),),
            )
            return [{"id": int(r["id"]), "name": r["name"]} for r in rows]

    @classmethod
    async def _first_usecase_id_for_project(
        cls, db: aiosqlite.Connection, project_id: int
    ) -> Optional[int]:
        row = await cls._fetchone(
            db,
            "SELECT id FROM use_cases WHERE project_id = ? ORDER BY id ASC LIMIT 1",
            (int(project_id),),
        )
        return int(row["id"]) if row else None

    # =========================================================
    # Load current mermaid
    # =========================================================
    @classmethod
    async def get_current_mermaid(
        cls,
        diagram_type: str,
        *,
        project_id: int,
        usecase_id: Optional[int] = None,
    ) -> str:
        diagram_type = (diagram_type or "").lower().strip()

        async with cls._conn() as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys=ON")

            if diagram_type == "erd":
                row = await cls._fetchone(
                    db,
                    """
                    SELECT mermaid_code
                    FROM entity_relationship_diagrams
                    WHERE project_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (int(project_id),),
                )
                code = (row["mermaid_code"] if row else "") or ""
                return cls._sanitize_mermaid("erd", code) or ""

            if diagram_type == "class":
                row = await cls._fetchone(
                    db,
                    """
                    SELECT mermaid_code
                    FROM class_diagrams
                    WHERE project_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (int(project_id),),
                )
                code = (row["mermaid_code"] if row else "") or ""
                sanitized = cls._sanitize_mermaid("class", code) or ""
                cls._dbg(
                    f"[LOAD][CLASS] project_id={project_id} row={'Y' if row else 'N'} "
                    f"sanitized_len={len(sanitized)} head={(sanitized[:30] if sanitized else '')!r}"
                )
                return sanitized

            if diagram_type == "sequence":
                if usecase_id is None:
                    usecase_id = await cls._first_usecase_id_for_project(db, project_id)
                    cls._dbg(f"[LOAD][SEQ] usecase_id was None -> auto_pick={usecase_id}")

                if usecase_id is None:
                    return ""

                row = await cls._fetchone(
                    db,
                    """
                    SELECT sd.mermaid_code
                    FROM sequence_diagrams sd
                    WHERE sd.project_id = ? AND sd.use_case_id = ?
                    ORDER BY sd.id DESC
                    LIMIT 1
                    """,
                    (int(project_id), int(usecase_id)),
                )
                code = (row["mermaid_code"] if row else "") or ""
                sanitized = cls._sanitize_mermaid("sequence", code) or ""
                cls._dbg(
                    f"[LOAD][SEQ] project_id={project_id} usecase_id={usecase_id} "
                    f"row={'Y' if row else 'N'} sanitized_len={len(sanitized)}"
                )
                return sanitized

            raise ValueError(f"Unsupported diagram_type: {diagram_type}")

    # =========================================================
    # Save mermaid (with strong debug + verify)
    # =========================================================
    @classmethod
    async def save_mermaid(
        cls,
        diagram_type: str,
        *,
        project_id: int,
        mermaid: str,
        usecase_id: Optional[int] = None,
    ) -> None:
        diagram_type = (diagram_type or "").lower().strip()

        raw = (mermaid or "").strip()
        sanitized = cls._sanitize_mermaid(diagram_type, raw)

        cls._dbg(
            f"[SAVE][IN] type={diagram_type} project_id={project_id} usecase_id={usecase_id} "
            f"raw_len={len(raw)} raw_head={(raw[:30] if raw else '')!r}"
        )
        cls._dbg(
            f"[SAVE][SAN] type={diagram_type} sanitized_len={len(sanitized)} "
            f"san_head={(sanitized[:30] if sanitized else '')!r}"
        )

        if not sanitized:
            cls._dbg(
                f"[SAVE][SKIP] type={diagram_type} project_id={project_id} "
                f"reason='sanitize_empty_or_header_missing'"
            )
            return

        async with cls._conn() as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys=ON")

            # ✅ 1:1：ERD 每個 project 只留一筆
            if diagram_type == "erd":
                await db.execute(
                    "DELETE FROM entity_relationship_diagrams WHERE project_id = ?",
                    (int(project_id),),
                )
                await db.execute(
                    "INSERT INTO entity_relationship_diagrams(project_id, mermaid_code) VALUES(?, ?)",
                    (int(project_id), sanitized),
                )
                await db.commit()

                # ✅ verify read-back
                chk = await cls._fetchone(
                    db,
                    "SELECT LENGTH(mermaid_code) AS n FROM entity_relationship_diagrams WHERE project_id = ? ORDER BY id DESC LIMIT 1",
                    (int(project_id),),
                )
                cls._dbg(f"[SAVE][OK][ERD] project_id={project_id} db_len={(chk['n'] if chk else None)}")
                return

            # ✅ 1:1：Class 每個 project 只留一筆
            if diagram_type == "class":
                await db.execute(
                    "DELETE FROM class_diagrams WHERE project_id = ?",
                    (int(project_id),),
                )
                await db.execute(
                    "INSERT INTO class_diagrams(project_id, mermaid_code) VALUES(?, ?)",
                    (int(project_id), sanitized),
                )
                await db.commit()

                chk = await cls._fetchone(
                    db,
                    "SELECT LENGTH(mermaid_code) AS n FROM class_diagrams WHERE project_id = ? ORDER BY id DESC LIMIT 1",
                    (int(project_id),),
                )
                cls._dbg(f"[SAVE][OK][CLASS] project_id={project_id} db_len={(chk['n'] if chk else None)}")
                return

            # ✅ 1:N：Sequence（每個 usecase 可多筆歷史）
            if diagram_type == "sequence":
                if usecase_id is None:
                    cls._dbg(
                        f"[SAVE][SKIP][SEQ] project_id={project_id} reason='usecase_id_is_None'"
                    )
                    return

                await db.execute(
                    "INSERT INTO sequence_diagrams(project_id, use_case_id, mermaid_code) VALUES(?, ?, ?)",
                    (int(project_id), int(usecase_id), sanitized),
                )
                await db.commit()

                chk = await cls._fetchone(
                    db,
                    """
                    SELECT id, LENGTH(mermaid_code) AS n
                    FROM sequence_diagrams
                    WHERE project_id = ? AND use_case_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (int(project_id), int(usecase_id)),
                )
                cls._dbg(
                    f"[SAVE][OK][SEQ] project_id={project_id} usecase_id={usecase_id} "
                    f"row_id={(chk['id'] if chk else None)} db_len={(chk['n'] if chk else None)}"
                )
                return

            raise ValueError(f"Unsupported diagram_type: {diagram_type}")

    # =========================================================
    # Generate Mermaid (ALL = Agent) + ensure save path is executed
    # =========================================================
    @classmethod
    async def generate_mermaid(
        cls,
        diagram_type: str,
        *,
        project_id: int,
        usecase_id: Optional[int] = None,
        force_regen: bool = False,
    ) -> str:
        diagram_type = (diagram_type or "").lower().strip()

        # ✅ If not forcing regen, prefer DB truth
        if not force_regen:
            existing = await cls.get_current_mermaid(
                diagram_type, project_id=project_id, usecase_id=usecase_id
            )
            if existing:
                cls._dbg(f"[GEN] type={diagram_type} project_id={project_id} -> use DB existing")
                return existing

        async with cls._conn() as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys=ON")

            if diagram_type == "erd":
                from agents.erd_agent_openai import ERDAgent

                mermaid = await ERDAgent.generate_erd_for_current_project(db)
                mermaid = cls._sanitize_mermaid("erd", mermaid) or "erDiagram\n"
                await cls.save_mermaid("erd", project_id=project_id, mermaid=mermaid)

                # ✅ optional: return DB truth (helps debug)
                db_code = await cls.get_current_mermaid("erd", project_id=project_id)
                return db_code or mermaid

            if diagram_type == "class":
                from agents.class_agent_openai import ClassDiagramAgent

                mermaid = await ClassDiagramAgent.generate_class_for_project(project_id=int(project_id), db=db)
                mermaid = cls._sanitize_mermaid("class", mermaid) or "classDiagram\n"
                await cls.save_mermaid("class", project_id=project_id, mermaid=mermaid)

                db_code = await cls.get_current_mermaid("class", project_id=project_id)
                return db_code or mermaid

            if diagram_type == "sequence":
                if usecase_id is None:
                    usecase_id = await cls._first_usecase_id_for_project(db, project_id)
                    cls._dbg(f"[GEN][SEQ] usecase_id was None -> auto_pick={usecase_id}")

                if usecase_id is None:
                    cls._dbg(f"[GEN][SEQ] project_id={project_id} -> no usecase, return ''")
                    return ""

                from agents.sequence_agent_openai import SequenceDiagramAgent

                mermaid = await SequenceDiagramAgent.generate_sequence_for_usecase(
                    db, project_id=int(project_id), usecase_id=int(usecase_id)
                )
                mermaid = cls._sanitize_mermaid("sequence", mermaid) or (
                    "sequenceDiagram\n  actor User\n  participant System\n"
                )

                await cls.save_mermaid(
                    "sequence",
                    project_id=project_id,
                    mermaid=mermaid,
                    usecase_id=int(usecase_id),
                )

                db_code = await cls.get_current_mermaid(
                    "sequence", project_id=project_id, usecase_id=int(usecase_id)
                )
                return db_code or mermaid

        raise ValueError(f"Unsupported diagram_type: {diagram_type}")

    # =========================================================
    # Batch generate all sequences
    # =========================================================
    @classmethod
    async def generate_all_sequences(
        cls, *, project_id: int, force_regen: bool = True
    ) -> int:
        ucs = await cls.list_usecases(project_id=project_id)
        count = 0
        for r in ucs:
            try:
                await cls.generate_mermaid(
                    "sequence",
                    project_id=int(project_id),
                    usecase_id=int(r["id"]),
                    force_regen=force_regen,
                )
                count += 1
            except Exception as e:
                cls._dbg(
                    f"⚠️ generate sequence failed usecase_id={r['id']}: {type(e).__name__}: {e}"
                )
        return count
