from sqlalchemy import Column, Integer, String
from init_db import Base
from sqlalchemy.orm import relationship

class UserAccount(Base):
    
    __tablename__ = 'user_accounts'

    id               = Column(Integer, primary_key=True, autoincrement=True, index=True)
    account          = Column(String(255), nullable=False, unique=True, index=True, comment="使用者帳號")
    password         = Column(String(255), nullable=False, comment="使用者密碼")


    # 🟢 一對多關聯：一個使用者有多個專案
    project = relationship("Project", back_populates="user", lazy="selectin")

    def __repr__(self):
        return f"<UserAccount(id={self.id}, account='{self.account}')>"

from models.project import Project  