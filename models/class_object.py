from sqlalchemy import Column, Integer, String, ForeignKey
from init_db import Base
from sqlalchemy.orm import relationship 

class ClassObject(Base):
    __tablename__ = 'class_objects'

    id = Column(Integer, primary_key=True, autoincrement=True)

    class_diagram_id = Column(Integer, ForeignKey('class_diagrams.id'), nullable=False)
    object_id = Column(Integer, ForeignKey('objects.id'), nullable=False)

    class_diagram = relationship('ClassDiagram', back_populates='class_object', lazy='selectin')
    object = relationship('Object', back_populates='class_object', lazy='selectin')

    def __repr__(self):
        return f"<ClassObject(name={self.name}, class_diagram_id={self.class_diagram_id})>"
    
from models.class_diagram import ClassDiagram
from models.object import Object