from sqlalchemy import Column, Integer, String, ForeignKey, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from init_db import Base

class EntityRelationshipDiagram(Base):
    __tablename__ = 'entity_relationship_diagrams'

    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String(255), nullable=True, comment="erd圖描述")
    # 🟩 這兩個欄位是重點
    mermaid_code = Column(Text, nullable=True, comment="Mermaid 語法內容")
    diagram_json = Column(JSON, nullable=True, comment="結構化 JSON 內容")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),comment="建立時間")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc),comment="更新時間")

    use_case_id = Column(Integer, ForeignKey('use_cases.id'), nullable=False)

    usecase = relationship('Usecase', back_populates='entity_relationship_diagram', lazy='selectin')

    def __repr__(self):
        return f"<EntityRelationshipDiagram(name={self.name}, use_case_id={self.use_case_id})>"
    
from models.usecase import Usecase
