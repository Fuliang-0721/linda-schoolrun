from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base

# MySQL 用 LONGTEXT；其它方言（本地开发用 SQLite）退化为 TEXT，
# 避免 SQLite 编译器无法渲染 LONGTEXT 导致建表失败。
LONG_TEXT = Text().with_variant(LONGTEXT, "mysql")


class UsageTipModel(Base):
    __tablename__ = "usage_tips"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    html_content: Mapped[str] = mapped_column(LONG_TEXT, nullable=False, default="")
    plain_text: Mapped[str] = mapped_column(LONG_TEXT, nullable=False, default="")
    contributor_qq: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    author_account_id: Mapped[str] = mapped_column(
        ForeignKey("auth_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_username: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    author: Mapped["AuthAccountModel"] = relationship(back_populates="tips")
