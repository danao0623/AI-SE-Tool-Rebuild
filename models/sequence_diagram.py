from sqlalchemy import Column, Integer, String, ForeignKey, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from init_db import Base


class SequenceDiagram(Base):
    __tablename__ = 'sequence_diagrams'

    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String(255), nullable=True, comment="循序圖描述")

    mermaid_code = Column(Text, nullable=True, comment="Mermaid 語法內容")
    diagram_json = Column(JSON, nullable=True, comment="結構化 JSON 內容")

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        comment="建立時間",
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="更新時間",
    )

    # ✅ 原本就有（保留）
    use_case_id = Column(
        Integer,
        ForeignKey('use_cases.id'),
        nullable=False,
        comment="所屬 UseCase",
    )

    # ✅ 新增：專案關聯（關鍵）
    project_id = Column(
        Integer,
        ForeignKey('projects.id'),
        nullable=False,
        index=True,
        comment="所屬專案（查詢用）",
    )

    # -------------------------
    # relationships
    # -------------------------
    usecase = relationship(
        'Usecase',
        back_populates='sequence_diagram',
        lazy='selectin',
    )

    # ✅ 新增：Project 反向關聯
    project = relationship(
        'Project',
        back_populates='sequence_diagrams',
        lazy='selectin',
    )

    sequence_objects = relationship(
        'SequenceObject',
        back_populates='sequence_diagram',
        lazy='selectin',
        cascade='all, delete-orphan',
    )

    def __repr__(self) -> str:
        return f"<SequenceDiagram(id={self.id}, project_id={self.project_id}, use_case_id={self.use_case_id})>"
