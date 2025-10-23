from sqlalchemy import Column, Integer, String, ForeignKey
from init_db import Base
from sqlalchemy.orm import relationship 

class SequenceObject(Base):
    __tablename__ = 'sequence_objects'

    id = Column(Integer, primary_key=True, autoincrement=True)
 
    sequence_diagram_id = Column(Integer, ForeignKey('sequence_diagrams.id'), nullable=False)
    object_id = Column(Integer, ForeignKey('objects.id'), nullable=False)

    sequence_diagram = relationship('SequenceDiagram', back_populates='sequence_objects', lazy='selectin')
    object = relationship('Object', back_populates='sequence_objects', lazy='selectin')

    def __repr__(self):
        return f"<SequenceObject(name={self.name}, sequence_diagram_id={self.sequence_diagram_id})>"

from models.sequence_diagram import SequenceDiagram
from models.object import Object