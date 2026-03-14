# models/entity_relationship_diagram.py
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, ForeignKey, Text, JSON, DateTime
from sqlalchemy.orm import relationship

from init_db import Base


class EntityRelationshipDiagram(Base):
    """ERD：專案級（每個 Project 一張）"""
    __tablename__ = "entity_relationship_diagrams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String(255), nullable=True, comment="ER 圖描述")

    mermaid_code = Column(Text, nullable=True, comment="Mermaid 語法內容")
    diagram_json = Column(JSON, nullable=True, comment="結構化 JSON 內容")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment="建立時間")
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="更新時間",
    )

    # ✅ 專案級歸屬：必填
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    project = relationship("Project", back_populates="entity_relationship_diagram", lazy="selectin")

    entity_relationship_object = relationship(
        "EntityRelationshipObject",
        back_populates="er_diagram",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<EntityRelationshipDiagram(id={self.id}, project_id={self.project_id})>"


from models.project import Project