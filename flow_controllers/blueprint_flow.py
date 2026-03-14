# flow_controllers/blueprint_flow.py
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Object, Attribute, BlueprintState


@dataclass
class BlueprintFlow:
    session: AsyncSession

    # -----------------------------
    # list data for UI (GROUP MODE)
    # -----------------------------
    async def list_boundary_groups(self, project_id: int) -> List[dict]:
        """
        以 canvas_group_key 分組列出 Boundary（下拉只顯示一筆）
        回傳：
          - group_key
          - name
          - count
        """
        stmt = (
            select(Object)
            .where(Object.project_id == project_id)
            .where(Object.type == "Boundary")
            .order_by(Object.id.asc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()

        groups: Dict[str, List[Object]] = {}
        for o in rows:
            key = (getattr(o, "canvas_group_key", None) or o.name or "").strip()
            if not key:
                key = f"BoundaryGroup_{o.id}"
            groups.setdefault(key, []).append(o)

        out: List[dict] = []
        for key, items in groups.items():
            out.append(
                {
                    "group_key": key,
                    "name": items[0].name,
                    "count": len(items),
                }
            )
        return out

    async def list_entities_for_group(self, project_id: int, group_key: str) -> List[dict]:
        """
        GROUP 版 entities：
        - 先用 group_key 找 canonical boundary（最小 id）
        - 用 canonical boundary 的 usecase_id 過濾 entities（維持你原本行為語意）
        """
        _, canonical_id, _ = await self._resolve_group(project_id, group_key)

        b_stmt = (
            select(Object)
            .where(Object.project_id == project_id)
            .where(Object.id == canonical_id)
            .where(Object.type == "Boundary")
            .limit(1)
        )
        boundary = (await self.session.execute(b_stmt)).scalars().first()
        if not boundary:
            return []

        usecase_id = getattr(boundary, "usecase_id", None)

        e_stmt = (
            select(Object)
            .where(Object.project_id == project_id)
            .where(Object.type == "Entity")
        )
        if usecase_id is not None:
            e_stmt = e_stmt.where(Object.usecase_id == usecase_id)

        e_stmt = e_stmt.order_by(Object.id.asc())
        entities = (await self.session.execute(e_stmt)).scalars().all()
        if not entities:
            return []

        entity_ids = [e.id for e in entities]
        a_stmt = (
            select(Attribute)
            .where(Attribute.object_id.in_(entity_ids))
            .order_by(Attribute.id.asc())
        )
        attrs = (await self.session.execute(a_stmt)).scalars().all()

        by_obj: Dict[int, List[str]] = {}
        for a in attrs:
            by_obj.setdefault(a.object_id, []).append(a.name)

        return [{"id": e.id, "name": e.name, "fields": by_obj.get(e.id, [])} for e in entities]

    # -----------------------------
    # DB (single table) - GROUP MODE
    # -----------------------------
    async def load_blueprint(self, project_id: int, group_key: str) -> Dict[str, Any]:
        """
        以 group_key 載入：
        - 找出群組內所有 boundary_id
        - 取群組內 updated_at 最新的 blueprint_state 當 canonical payload
        - 若都沒有存過，回傳空畫布（以 canonical boundary_id 建 screen_id）
        """
        boundary_ids, canonical_id, canonical_name = await self._resolve_group(project_id, group_key)

        stmt = (
            select(BlueprintState)
            .where(BlueprintState.project_id == project_id)
            .where(BlueprintState.boundary_id.in_(boundary_ids))
            .order_by(BlueprintState.updated_at.desc())
        )
        row = (await self.session.execute(stmt)).scalars().first()

        if row and (row.payload_json or "").strip():
            try:
                data = json.loads(row.payload_json)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"BlueprintState payload_json 解析失敗：{e}")

            screen = self._extract_screen_from_payload(data, canonical_id)
            if screen is None:
                return self._empty_payload(project_id, canonical_id, canonical_name)

            screen = self._ensure_screen_fields(screen, canonical_id, canonical_name)
            return {"project": str(project_id), "boundary_id": canonical_id, "screen": screen}

        return self._empty_payload(project_id, canonical_id, canonical_name)

    async def save_blueprint(
        self,
        project_id: int,
        group_key: str,
        payload: Dict[str, Any],
        canvas_jpg_base64: str = "",
    ) -> Dict[str, Any]:
        """
        以 group_key 儲存：
        - 找出群組內所有 boundary_id
        - 將同一份 payload_json / canvas_jpg 批次 upsert 到每個 boundary 的 blueprint_state
        """
        boundary_ids, canonical_id, canonical_name = await self._resolve_group(project_id, group_key)

        # 1) normalize payload -> screen
        screen = self._extract_screen_from_payload(payload, canonical_id) or {"components": []}
        screen = self._ensure_screen_fields(screen, canonical_id, canonical_name)

        normalized = {"project": str(project_id), "boundary_id": canonical_id, "screen": screen}
        payload_json = json.dumps(normalized, ensure_ascii=False)

        # 2) decode jpg (optional)
        jpg_bytes: Optional[bytes] = None
        if (canvas_jpg_base64 or "").strip():
            s = canvas_jpg_base64.strip()
            if "base64," in s:
                s = s.split("base64,", 1)[1].strip()
            try:
                jpg_bytes = base64.b64decode(s, validate=False)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"canvas_jpg_base64 解析失敗：{e}")

        # 3) batch upsert (1 query to fetch existing)
        stmt = (
            select(BlueprintState)
            .where(BlueprintState.project_id == project_id)
            .where(BlueprintState.boundary_id.in_(boundary_ids))
        )
        existing = (await self.session.execute(stmt)).scalars().all()
        by_bid: Dict[int, BlueprintState] = {r.boundary_id: r for r in existing}

        screen_name = str(screen.get("name") or canonical_name or "")

        for bid in boundary_ids:
            row = by_bid.get(bid)
            if row:
                row.screen_name = screen_name
                row.payload_json = payload_json
                if jpg_bytes is not None:
                    row.canvas_jpg = jpg_bytes
            else:
                row = BlueprintState(
                    project_id=project_id,
                    boundary_id=bid,
                    screen_name=screen_name,
                    payload_json=payload_json,
                    canvas_jpg=jpg_bytes,
                )
                self.session.add(row)

        await self.session.commit()

        ref = f"db:blueprint_group(p={project_id},k={group_key})"
        return {
            "project_id": project_id,
            "group_key": group_key,
            "canonical_boundary_id": canonical_id,
            "ref": ref,
            "file_path": ref,
        }

    async def get_canvas_jpg_bytes(self, project_id: int, group_key: str) -> Optional[bytes]:
        """
        群組版 jpg：取群組內 updated_at 最新那筆的 canvas_jpg
        """
        boundary_ids, _, _ = await self._resolve_group(project_id, group_key)

        stmt = (
            select(BlueprintState)
            .where(BlueprintState.project_id == project_id)
            .where(BlueprintState.boundary_id.in_(boundary_ids))
            .order_by(BlueprintState.updated_at.desc())
        )
        row = (await self.session.execute(stmt)).scalars().first()
        return row.canvas_jpg if (row and row.canvas_jpg) else None

    # -----------------------------
    # helpers
    # -----------------------------
    async def _resolve_group(self, project_id: int, group_key: str) -> Tuple[List[int], int, str]:
        """
        找出群組內所有 Boundary，回傳：
        - boundary_ids: 群組內 boundary.id 清單
        - canonical_id: 群組代表（最小 id）
        - canonical_name: canonical 的 name

        查找順序：
        1) Object.canvas_group_key == group_key
        2) fallback：Object.name == group_key（容錯）
        """
        gk = (group_key or "").strip()
        if not gk:
            raise HTTPException(status_code=400, detail="group_key is required")

        # 1) canvas_group_key
        stmt = (
            select(Object)
            .where(Object.project_id == project_id)
            .where(Object.type == "Boundary")
            .where(Object.canvas_group_key == gk)
            .order_by(Object.id.asc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()

        # 2) fallback name
        if not rows:
            stmt2 = (
                select(Object)
                .where(Object.project_id == project_id)
                .where(Object.type == "Boundary")
                .where(Object.name == gk)
                .order_by(Object.id.asc())
            )
            rows = (await self.session.execute(stmt2)).scalars().all()

        if not rows:
            raise HTTPException(status_code=404, detail=f"Boundary group not found: {gk}")

        boundary_ids = [o.id for o in rows]
        canonical = rows[0]
        canonical_id = canonical.id
        canonical_name = canonical.name or f"Boundary_{canonical_id}"
        return boundary_ids, canonical_id, canonical_name

    @staticmethod
    def _screen_id(boundary_id: int) -> str:
        return f"b_{boundary_id}"

    @classmethod
    def _empty_payload(cls, project_id: int, boundary_id: int, boundary_name: str) -> Dict[str, Any]:
        return {
            "project": str(project_id),
            "boundary_id": boundary_id,
            "screen": {
                "id": cls._screen_id(boundary_id),
                "name": boundary_name or f"Boundary_{boundary_id}",
                "boundary_ref": f"Boundary:{boundary_name or f'Boundary_{boundary_id}'}",
                "boundary_id": boundary_id,
                "components": [],
            },
        }

    @classmethod
    def _ensure_screen_fields(cls, screen: Dict[str, Any], boundary_id: int, boundary_name: str) -> Dict[str, Any]:
        screen = dict(screen)
        screen.setdefault("id", cls._screen_id(boundary_id))
        screen.setdefault("boundary_id", boundary_id)
        screen.setdefault("name", boundary_name or f"Boundary_{boundary_id}")
        screen.setdefault("boundary_ref", f"Boundary:{boundary_name or f'Boundary_{boundary_id}'}")
        comps = screen.get("components")
        if not isinstance(comps, list):
            screen["components"] = []
        return screen

    @classmethod
    def _extract_screen_from_payload(cls, payload: Any, boundary_id: int) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None

        if isinstance(payload.get("screen"), dict):
            return payload["screen"]

        if isinstance(payload.get("screens"), list) and payload["screens"]:
            for s in payload["screens"]:
                if isinstance(s, dict) and int(s.get("boundary_id", -1)) == int(boundary_id):
                    return s
            if isinstance(payload["screens"][0], dict):
                return payload["screens"][0]

        if isinstance(payload.get("components"), list):
            return {"components": payload["components"]}

        return None
