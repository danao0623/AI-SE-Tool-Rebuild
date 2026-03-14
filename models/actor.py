from sqlalchemy import Column, Integer,String, ForeignKey
from init_db import Base
from sqlalchemy.orm import relationship

class Actor(Base):
    __tablename__ = 'actors'

    id             = Column(Integer, primary_key=True, autoincrement=True)
    name           = Column(String(255), nullable=False)
    description = Column(String)
    
    project_id           = Column(Integer, ForeignKey("projects.id"), nullable=False)
    usecase_actor = relationship('UsecaseActor', back_populates='actor', lazy='selectin')

    project         = relationship('Project',     back_populates='actors', lazy='selectin')
    
    def __repr__(self):
        return f"<Actor(id={self.id}, name='{self.name}')>"
    
from models.usecase_actor import UsecaseActor