from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AppNoticeModel(Base):
    __tablename__ = "app_notices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    qq_group_number: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    bilibili_text: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    bilibili_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
