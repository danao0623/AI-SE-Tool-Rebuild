from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from init_db import Base


class Usecase(Base):
    __tablename__ = "use_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="使用案例名稱")
    description = Column(Text, comment="使用案例描述")
    normal_process = Column(String(255), comment="正常流程")
    exception_process = Column(String(255), comment="例外流程")
    pre_condition = Column(String(255), comment="前置條件")
    post_condition = Column(String(255), comment="後置條件")
    trigger_condition = Column(String(255))

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    project = relationship("Project", back_populates="usecase", lazy="selectin")
    usecase_actor = relationship("UsecaseActor", back_populates="usecase", lazy="selectin", cascade="all, delete-orphan")
    event_list = relationship("EventList", back_populates="usecase", lazy="selectin", cascade="all, delete-orphan")
    objects = relationship("Object",back_populates="usecase",lazy="selectin",cascade="all, delete-orphan",)


    # ✅ 循序圖：Usecase 級（維持原設計）
    sequence_diagram = relationship("SequenceDiagram", back_populates="usecase", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UseCase(id={self.id}, name='{self.name}')>"


from models.project import Project
from models.usecase_actor import UsecaseActor
from models.event_list import EventList
from models.sequence_diagram import SequenceDiagram
from models.object import Object