# models/object.py
from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from init_db import Base


class Object(Base):
    __tablename__ = 'objects'

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # 物件名稱（例如 課程查詢介面、學生、課程）
    name = Column(String(255), nullable=False, index=True)

    # 物件類型：Boundary / Control / Entity
    type = Column(String(100), nullable=False)

    # ★ 新增：物件說明文字（對應 Agent 的 description）
    description = Column(Text, nullable=True, comment="物件用途說明")

    canvas_group_key = Column(String(255),nullable=True,index=True, comment="同一畫面物件群組識別，格式：Boundary:{name} / Control:{name} / Entity:{name}")

    # 每個物件一定屬於某個專案
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship('Project', lazy='selectin')  # 單向即可，避免多餘 back_populates

    usecase_id = Column(Integer, ForeignKey("use_cases.id"), nullable=True, index=True)
    usecase = relationship("Usecase", back_populates="objects", lazy="selectin")

    # 1 對多：SequenceDiagram 上的生命線
    sequence_object = relationship(
        'SequenceObject',
        back_populates='object',
        lazy='selectin',
        cascade='all, delete-orphan',
    )

    # 1 對多：ClassDiagram 裡對應的類別
    class_object = relationship(
        'ClassObject',
        back_populates='object',
        lazy='selectin',
        cascade='all, delete-orphan',
    )

    # 1 對多：ERD 裡對應的實體
    entity_relationship_object = relationship(
        'EntityRelationshipObject',
        back_populates='object',
        lazy='selectin',
        cascade='all, delete-orphan',
    )

    # 1 對多：掛在物件上的方法 / 屬性
    method = relationship(
        'Method',
        back_populates='object',
        lazy='selectin',
        cascade='all, delete-orphan',
    )
    attributes = relationship(
        'Attribute',
        back_populates='object',
        lazy='selectin',
        cascade='all, delete-orphan',
    )

    def __repr__(self) -> str:
        return (
            f"<Object id={self.id} name={self.name} "
            f"type={self.type} project_id={self.project_id}>"
        )