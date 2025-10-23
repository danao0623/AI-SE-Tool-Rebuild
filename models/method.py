from sqlalchemy import Column, Integer, String, ForeignKey
from init_db import Base
from sqlalchemy.orm import relationship
    
    #Method =方法
class Method(Base):
    __tablename__ = 'methods'
    id             = Column(Integer, primary_key=True, autoincrement=True)
    name           = Column(String(255),comment="方法名稱")
    return_type    = Column(String(100), comment="方法的返回類型")
    visibility     = Column(String(50), comment="方法的可見性，如public、private、protected")
    parameters     = Column(String(255),comment="參數列表，以逗號分隔")
    
    object_id      = Column(Integer, ForeignKey('class_objects.id'), nullable=False)

    object         = relationship('ClassObject', back_populates='method', lazy='selectin')

    def __repr__(self):
        return f"<Method(id={self.id}, name='{self.name}', return_type='{self.return_type}', visibility='{self.visibility}', object_id='{self.object_id}')>"
    
from models.object import ClassObject