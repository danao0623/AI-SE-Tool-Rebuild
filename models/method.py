# models/method.py
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from init_db import Base


class Method(Base):
    """
    掛在 Object 底下的方法
    """
    __tablename__ = 'methods'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="方法名稱")
    return_type = Column(String(100), nullable=True, comment="方法的返回類型")
    visibility = Column(String(50), nullable=True, comment="方法的可見性，如 public、private、protected")
    parameters = Column(String(255), nullable=True, comment="參數列表，以逗號分隔")

    # 關聯回 Object
    object_id = Column(Integer, ForeignKey('objects.id'), nullable=False)
    object = relationship('Object', back_populates='method', lazy='selectin')

    def __repr__(self) -> str:
        return (
            f"<Method(id={self.id}, name='{self.name}', "
            f"return_type='{self.return_type}', visibility='{self.visibility}', "
            f"object_id={self.object_id})>"
        )