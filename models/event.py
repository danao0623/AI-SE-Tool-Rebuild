from sqlalchemy import Column, Integer, String, ForeignKey
from init_db import Base
from sqlalchemy.orm import relationship

class Event(Base):

    __tablename__ = 'events'

    id             = Column(Integer, primary_key=True, autoincrement=True)
    sequence_no     = Column(Integer, nullable=False)           #事件在清單上的順序，1正常對1正常, 2例外對1、2、3例外
    type           = Column(String(255), nullable=False)        #事件類型        
    description    = Column(String(255), nullable=False)   

    event_list_id  = Column(Integer, ForeignKey('event_lists.id'))

    event_list = relationship('EventList', back_populates='event', lazy='selectin')

from models.event_list import EventList