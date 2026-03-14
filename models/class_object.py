# models/class_object.py
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from init_db import Base


class ClassObject(Base):
    """
    類別圖上的類別節點，連接 ClassDiagram 與 Object
    """
    __tablename__ = 'class_objects'

    id = Column(Integer, primary_key=True, autoincrement=True)

    class_diagram_id = Column(Integer, ForeignKey('class_diagrams.id'), nullable=False)
    object_id = Column(Integer, ForeignKey('objects.id'), nullable=False)

    class_diagram = relationship(
        'ClassDiagram',
        back_populates='class_object',
        lazy='selectin',
    )

    object = relationship(
        'Object',
        back_populates='class_object',
        lazy='selectin',
    )

    def __repr__(self) -> str:
        return (
            f"<ClassObject(id={self.id}, "
            f"class_diagram_id={self.class_diagram_id}, object_id={self.object_id})>"
        )


from models.class_diagram import ClassDiagram
from models.object import Object
