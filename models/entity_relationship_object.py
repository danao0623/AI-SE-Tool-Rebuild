from sqlalchemy import Column, Integer, String, ForeignKey
from init_db import Base
from sqlalchemy.orm import relationship 

class EntityRelationshipObject(Base):
    __tablename__ = 'entity_relationship_objects'

    id = Column(Integer, primary_key=True, autoincrement=True)

    object_id = Column(Integer, ForeignKey('objects.id'), nullable=False)
    class_diagram_id = Column(Integer, ForeignKey('class_diagrams.id'), nullable=False)

    class_diagram = relationship('ClassDiagram', back_populates='entity_relationship_object', lazy='selectin')
    object = relationship('Object', back_populates='entity_relationship_object', lazy='selectin')

    def __repr__(self):
        return f"<EntityRelationshipObject(class_diagram_id={self.class_diagram_id})>"

from models.entity_relationship_diagram import EntityRelationshipDiagram
from models.object import Object