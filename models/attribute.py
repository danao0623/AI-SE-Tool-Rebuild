from sqlalchemy import Column, Integer, String, ForeignKey
from init_db import Base
from sqlalchemy.orm import relationship

    #Attribute =屬性
class Attribute(Base):     
    __tablename__ = 'attributes'

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(255), nullable=False, comment="屬性名稱")
    data_type   = Column(String(100), nullable=False, comment="資料類型")
    visibility  = Column(String(50), nullable=False, comment="可見性")

    object_id   = Column(Integer, ForeignKey('class_objects.id'), nullable=False, comment="所屬類別物件ID")

    object      = relationship('ClassObject', back_populates='attribute', lazy='selectin')

    def __repr__(self):
        return f"<Attribute(id={self.id}, name='{self.name}', data_type='{self.data_type}', visibility='{self.visibility}', object_id='{self.object_id}')>"

from models.class_object import ClassObject