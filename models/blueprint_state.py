# models/blueprint_state.py
from datetime import datetime

from sqlalchemy import Column, Integer, Text, DateTime, String, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.sqlite import BLOB  # SQLite BLOB
from init_db import Base


class BlueprintState(Base):
    __tablename__ = "blueprint_state"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Project FK
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    project = relationship("Project", backref="blueprint_states")

    # Boundary(Object) FK
    boundary_id = Column(Integer, ForeignKey("objects.id", ondelete="CASCADE"), nullable=False, index=True)
    boundary = relationship("Object", foreign_keys=[boundary_id])

    screen_name = Column(String(255), nullable=False, default="")

    # ✅ CLOB：詳細資料（JSON 字串）
    payload_json = Column(Text, nullable=False, default="{}")

    # ✅ BLOB：畫面 JPG（給 code_agent 當參照）
    canvas_jpg = Column(BLOB, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # ✅ 一個畫面一筆（最新狀態）
        UniqueConstraint("project_id", "boundary_id", name="uq_blueprint_state_project_boundary"),
        Index("ix_blueprint_state_project_boundary", "project_id", "boundary_id"),
    )
