# flow_controllers/blueprint_api.py
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from init_db import get_async_session
from flow_controllers.blueprint_flow import BlueprintFlow


# -----------------------------
# schemas (GROUP MODE)
# -----------------------------
class BoundaryGroupOut(BaseModel):
    group_key: str
    name: str
    count: int


class EntityOut(BaseModel):
    id: int
    name: str
    fields: List[str] = Field(default_factory=list)


class LoadBlueprintOut(BaseModel):
    ok: bool = True
    project_id: int
    group_key: str
    canonical_boundary_id: int
    payload: Dict[str, Any]


class SaveBlueprintIn(BaseModel):
    project_id: int
    group_key: str
    payload: Dict[str, Any]
    canvas_jpg_base64: str = ""  # 可空


class SaveBlueprintOut(BaseModel):
    ok: bool = True
    project_id: int
    group_key: str
    canonical_boundary_id: int
    ref: str
    file_path: str = ""


# -----------------------------
# router
# -----------------------------
router = APIRouter(prefix="/api/blueprint", tags=["blueprint"])


@router.get("/boundary_groups", response_model=List[BoundaryGroupOut])
async def api_list_boundary_groups(project_id: int, session: AsyncSession = Depends(get_async_session)):
    rows = await BlueprintFlow(session).list_boundary_groups(project_id)
    return [BoundaryGroupOut(**r) for r in rows]


@router.get("/entities", response_model=List[EntityOut])
async def api_list_entities(project_id: int, group_key: str, session: AsyncSession = Depends(get_async_session)):
    rows = await BlueprintFlow(session).list_entities_for_group(project_id, group_key)
    return [EntityOut(**r) for r in rows]


@router.get("/load", response_model=LoadBlueprintOut)
async def api_load_blueprint(project_id: int, group_key: str, session: AsyncSession = Depends(get_async_session)):
    payload = await BlueprintFlow(session).load_blueprint(project_id, group_key)
    canonical_boundary_id = int(payload.get("boundary_id") or 0)
    return LoadBlueprintOut(
        project_id=project_id,
        group_key=group_key,
        canonical_boundary_id=canonical_boundary_id,
        payload=payload,
    )


@router.post("/save", response_model=SaveBlueprintOut)
async def api_save_blueprint(body: SaveBlueprintIn, session: AsyncSession = Depends(get_async_session)):
    out = await BlueprintFlow(session).save_blueprint(
        body.project_id,
        body.group_key,
        body.payload,
        canvas_jpg_base64=body.canvas_jpg_base64,
    )
    return SaveBlueprintOut(
        project_id=out["project_id"],
        group_key=out["group_key"],
        canonical_boundary_id=out["canonical_boundary_id"],
        ref=out["ref"],
        file_path=out.get("file_path", ""),
    )


@router.get("/canvas.jpg")
async def api_get_canvas_jpg(project_id: int, group_key: str, session: AsyncSession = Depends(get_async_session)):
    jpg = await BlueprintFlow(session).get_canvas_jpg_bytes(project_id, group_key)
    if not jpg:
        raise HTTPException(status_code=404, detail="No canvas jpg")
    return Response(content=jpg, media_type="image/jpeg")
