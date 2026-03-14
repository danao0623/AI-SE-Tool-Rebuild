# models/project_file.py
from __future__ import annotations
from datetime import datetime,timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from init_db import Base

class ProjectFile(Base):
    __tablename__ = "project_files"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    project_id  = Column(Integer, ForeignKey("projects.id"), nullable=False)

    # 檔案種類：md / pdf / code / image ...
    file_type   = Column(String(50), nullable=False)

    # 顯示給使用者看的檔名
    file_name   = Column(String(255), nullable=False)

    # 真正的實體檔案位置（例如 /files/1/event_summary_xxx.pdf）
    file_path   = Column(String(500), nullable=False)

    # 描述（可選）
    description = Column(String(255))

    from datetime import datetime

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                    onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    