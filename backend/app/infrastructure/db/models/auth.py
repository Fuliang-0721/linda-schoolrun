from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


class AuthAccountModel(Base):
    __tablename__ = "auth_accounts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    display_username: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    client_variant: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    remark: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    tester_type: Mapped[str] = mapped_column(String(32), nullable=False, default="ordinary")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    ban_reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    ban_detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    banned_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    bound_device_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    bound_device_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    failed_device_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_login_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    login_attempts: Mapped[list["AuthLoginAttemptModel"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    alerts: Mapped[list["AuthAlertModel"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    tips: Mapped[list["UsageTipModel"]] = relationship(back_populates="author")


class AuthLoginAttemptModel(Base):
    __tablename__ = "auth_login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("auth_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    device_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    app_variant: Mapped[str] = mapped_column(String(32), nullable=False, default="internal")
    success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    account: Mapped[AuthAccountModel | None] = relationship(back_populates="login_attempts")


class AuthDeviceModel(Base):
    __tablename__ = "auth_devices"

    device_id: Mapped[str] = mapped_column(String(384), primary_key=True)
    raw_device_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    client_variant: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    device_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    ban_reason: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    ban_detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    banned_until: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    wrong_password_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wrong_password_window_started_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    wrong_password_ban_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wrong_device_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    last_attempt_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class AuthAlertModel(Base):
    __tablename__ = "auth_alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("auth_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    device_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    account: Mapped[AuthAccountModel] = relationship(back_populates="alerts")
