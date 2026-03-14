# models/sequence_object.py

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from init_db import Base


class SequenceObject(Base):
    """
    循序圖上的生命線 / 參與物件
    """
    __tablename__ = 'sequence_objects'

    id = Column(Integer, primary_key=True, autoincrement=True)

    sequence_diagram_id = Column(
        Integer,
        ForeignKey('sequence_diagrams.id'),
        nullable=False,
    )
    object_id = Column(
        Integer,
        ForeignKey('objects.id'),
        nullable=False,
    )

    # 回到 SequenceDiagram
    sequence_diagram = relationship(
        'SequenceDiagram',
        back_populates='sequence_objects',
        lazy='selectin',
    )

    # 回到分析後的 Object
    object = relationship(
        'Object',
        back_populates='sequence_object',  # 注意：這裡是 sequence_object（單數），要跟 Object 對得起來
        lazy='selectin',
    )

    def __repr__(self) -> str:
        return (
            f"<SequenceObject(id={self.id}, "
            f"sequence_diagram_id={self.sequence_diagram_id}, "
            f"object_id={self.object_id})>"
        )