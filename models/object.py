from sqlalchemy import Column, Integer, String, ForeignKey
from init_db import Base
from sqlalchemy.orm import relationship

    #Object =物件
class Object(Base):
    
    __tablename__ = 'objects'

    id          = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name        = Column(String(255), nullable=False, index=True, comment="物件名稱")
    type        = Column(String(100), nullable=False, comment="物件類型")

    sequence_object = relationship('SequenceObject', back_populates='object', lazy='selectin', cascade='all, delete-orphan')
    class_object = relationship('ClassObject', back_populates='object', lazy='selectin', cascade='all, delete-orphan')
    entity_relationship_object = relationship('EntityRelationshipObject', back_populates='object', lazy='selectin', cascade='all, delete-orphan')
    method     = relationship('Method', back_populates='object', lazy='selectin', cascade='all, delete-orphan')
    attribute  = relationship('Attribute', back_populates='object', lazy='selectin', cascade='all, delete-orphan')


    def __repr__(self):
        return f"<Object(id={self.id}, name='{self.name}', type='{self.type}')>"

from models.sequence_object import SequenceObject
from models.class_object import ClassObject
from models.entity_relationship_object import EntityRelationshipObject
from models.method import Method
from models.attribute import Attribute