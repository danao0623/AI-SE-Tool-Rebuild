from sqlalchemy import Column, Integer, String, ForeignKey, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from init_db import Base

class ClassDiagram(Base):
    __tablename__ = 'class_diagrams'

    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String(255), nullable=True, comment="類別圖描述")
    # 🟩 這兩個欄位一樣重要
    mermaid_code = Column(Text, nullable=True, comment="Mermaid 語法內容")
    diagram_json = Column(JSON, nullable=True, comment="結構化 JSON 內容")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    usecase_id = Column(Integer, ForeignKey('use_cases.id'))
    usecase = relationship('Usecase', back_populates='class_diagram', lazy='selectin')

from models.usecase import Usecase