from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from init_db import Base


class Attribute(Base):
    """
    掛在 Object 底下的屬性
    """
    __tablename__ = 'attributes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="屬性名稱")
    type = Column(String(100), nullable=True, comment="屬性資料型態，如 int、string")
    visibility = Column(String(50), nullable=True, comment="屬性可見性，如 public、private、protected")
    default = Column(String(255), nullable=True, comment="預設值")

    object_id = Column(Integer, ForeignKey('objects.id'), nullable=False)
    object = relationship('Object', back_populates='attributes', lazy='selectin')

    def __repr__(self) -> str:
        return (
            f"<Attribute(id={self.id}, name='{self.name}', type='{self.type}', "
            f"visibility='{self.visibility}', default='{self.default}', "
            f"object_id={self.object_id})>"
        )