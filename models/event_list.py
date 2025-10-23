from sqlalchemy import Column, Integer, String, ForeignKey
from init_db import Base
from sqlalchemy.orm import relationship

class EventList(Base):
    __tablename__ = 'event_lists'
    id             = Column(Integer, primary_key=True, autoincrement=True)
    type           = Column(String(255), comment="事件列表類型")
    
    use_case_id    = Column(Integer, ForeignKey('use_cases.id'))

    event = relationship('Event', back_populates='event_list', lazy='selectin', cascade="all, delete-orphan")
    usecase = relationship('Usecase', back_populates='event_list', lazy='selectin')

    def __repr__(self):
        return f"<EventList(id={self.id}, type='{self.type}')>"
    
from models.usecase import Usecase
from models.event import Event