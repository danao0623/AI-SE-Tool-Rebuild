from sqlalchemy import Column, Integer, String, Text, ForeignKey
from init_db import Base
from sqlalchemy.orm import relationship

class Project(Base):
    
    __tablename__ = 'projects'

    id                = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name              = Column(String(255), nullable=False, index=True, comment="專案名稱")
    description       = Column(Text, comment="專案描述")
    architecture      = Column(String(255), comment="系統架構")
    frontend_language = Column(String(255), nullable=False, comment="前端語言")
    frontend_platform = Column(String(255), comment="前端平台")
    frontend_library  = Column(String(255), comment="前端框架/函式庫")
    backend_language  = Column(String(255), nullable=False, comment="後端語言")
    backend_platform  = Column(String(255), comment="後端平台")
    backend_library   = Column(String(255), comment="後端框架/函式庫")
    
    # 🟢 外鍵欄位：連到使用者
    user_id           = Column(Integer, ForeignKey("user_accounts.id"), nullable=False)

    # 🟢 多對一關聯：每個專案都有一位使用者
    user = relationship("UserAccount", back_populates="project", lazy="selectin")
    # 🟢 一對多關聯：每個專案可以有多個使用案例
    usecase = relationship("Usecase", back_populates="project", lazy="selectin")

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', description='{self.description}', user_id={self.user_id})>"

# ✅ 延後匯入，避免循環依賴
from models.usecase import Usecase