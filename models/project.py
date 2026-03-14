from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from init_db import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255), nullable=False, index=True, comment="專案名稱")
    description = Column(Text, comment="專案描述")
    architecture = Column(String(255), comment="系統架構")
    frontend_language = Column(String(255), nullable=False, comment="前端語言")
    frontend_platform = Column(String(255), comment="前端平台")
    frontend_library = Column(String(255), comment="前端框架/函式庫")
    backend_language = Column(String(255), nullable=False, comment="後端語言")
    backend_platform = Column(String(255), comment="後端平台")
    backend_library = Column(String(255), comment="後端框架/函式庫")

    user_id = Column(Integer, ForeignKey("user_accounts.id"), nullable=False)

    user = relationship("UserAccount", back_populates="project", lazy="selectin")
    usecase = relationship("Usecase", back_populates="project", lazy="selectin")
    actors = relationship("Actor", back_populates="project", lazy="selectin")
    code_snapshots = relationship(
        "CodeSnapshot",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


    
        # ✅ 新增：專案級 ERD / Class（每專案一張）
    class_diagram = relationship(
        "ClassDiagram",
        back_populates="project",
        lazy="selectin",
        uselist=False,
        cascade="all, delete-orphan",
    )
    entity_relationship_diagram = relationship(
        "EntityRelationshipDiagram",
        back_populates="project",
        lazy="selectin",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # ✅ 新增：專案底下所有循序圖（1:N）
    sequence_diagrams = relationship("SequenceDiagram",
        back_populates="project",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', user_id={self.user_id})>"


from models.usecase import Usecase
from models.class_diagram import ClassDiagram
from models.entity_relationship_diagram import EntityRelationshipDiagram