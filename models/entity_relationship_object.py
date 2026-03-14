# models/entity_relationship_object.py
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from init_db import Base


class EntityRelationshipObject(Base):
    """
    ER 圖上的節點（實體或關聯），連接 ERDiagram 與 Object
    """
    __tablename__ = 'entity_relationship_objects'

    id = Column(Integer, primary_key=True, autoincrement=True)

    er_diagram_id = Column(Integer, ForeignKey('entity_relationship_diagrams.id'), nullable=False)
    object_id = Column(Integer, ForeignKey('objects.id'), nullable=False)

    # 回到 ER 圖
    er_diagram = relationship(
        'EntityRelationshipDiagram',
        back_populates='entity_relationship_object',
        lazy='selectin',
    )

    # 回到分析後的 Object
    object = relationship(
        'Object',
        back_populates='entity_relationship_object',
        lazy='selectin',
    )

    def __repr__(self) -> str:
        return (
            f"<EntityRelationshipObject(id={self.id}, "
            f"er_diagram_id={self.er_diagram_id}, object_id={self.object_id})>"
        )


from models.entity_relationship_diagram import EntityRelationshipDiagram
from models.object import Object