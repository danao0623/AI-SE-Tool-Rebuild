from sqlalchemy import Column, Integer,ForeignKey
from init_db import Base
from sqlalchemy.orm import relationship

class UsecaseActor(Base):
    __tablename__ = 'usecase_actors'

    use_case_id        = Column(Integer, ForeignKey('use_cases.id'), primary_key=True)
    actor_id           = Column(Integer, ForeignKey('actors.id'), primary_key=True)

    usecase         = relationship('Usecase', back_populates='usecase_actor', lazy='selectin')
    actor           = relationship('Actor', back_populates='usecase_actor', lazy='selectin')

    def __repr__(self):
        return f"<UsecaseActor(use_case_id={self.use_case_id}, actor_id={self.actor_id})>"
    
from models.usecase import Usecase
from models.actor import Actor