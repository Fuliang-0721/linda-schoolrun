from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base

# SQLite（本地开发）用 TEXT，MySQL 用 LONGTEXT
LOG_TEXT = Text().with_variant(LONGTEXT, "mysql")


class DeviceLogModel(Base):
    """客户端上报的运行日志（崩溃现场 / 手动反馈），供后台看板排查。"""

    __tablename__ = "device_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    install_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    app_version_name: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    app_version_code: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    device_model: Mapped[str] = mapped_column(String(96), nullable=False, default="")
    android_sdk: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", index=True)
    log_text: Mapped[str] = mapped_column(LOG_TEXT, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
