# models/code_snapshot.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,Column,DateTime,ForeignKey,Index,Integer,String,Text,
)
from sqlalchemy.orm import relationship

from init_db import Base


class CodeSnapshot(Base):
    __tablename__ = "code_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # ✅ 對齊 Project.__tablename__ = "projects"
    # ✅ 加上 ondelete="CASCADE"：刪除專案時，DB 端可級聯刪除 snapshots
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所屬專案 ID",
    )

    package_name = Column(
        String(100),
        nullable=False,
        default="generated_app",
        comment="輸出程式包/專案名稱",
    )

    # cover=完整覆蓋輸出；patch=增量/差分輸出（你後續要做也方便）
    mode = Column(
        String(20),
        nullable=False,
        default="cover",
        comment="輸出模式：cover/patch",
    )

    # ✅ 最新版本旗標：同一個 project 只能有一筆 True（由 partial unique index 保證）
    is_latest = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否為該專案最新版本",
    )

    # JSON 字串：建議格式 {"files":[{"path":"...","content":"..."}]}
    files_json = Column(
        Text,
        nullable=False,
        comment="程式碼檔案清單 JSON 字串（含路徑與內容）",
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="建立時間（UTC）",
    )

    # relationships
    project = relationship(
        "Project",
        back_populates="code_snapshots",
        lazy="selectin",
    )

    __table_args__ = (
        # ✅ SQLite partial unique index：同 project 只能有一筆 is_latest = 1
        Index(
            "uq_code_snapshots_project_latest",
            "project_id",
            unique=True,
            sqlite_where=(is_latest == True),  # noqa: E712
        ),
        # ✅ 常用查詢：某 project 的歷史版本依時間排序
        Index("ix_code_snapshots_project_created_at", "project_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<CodeSnapshot(id={self.id}, project_id={self.project_id}, "
            f"is_latest={self.is_latest}, mode='{self.mode}', created_at={self.created_at})>"
        )
