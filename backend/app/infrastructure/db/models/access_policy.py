from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AccessPolicyModel(Base):
    """全局服务开关（单行，id=1）。

    客户端每次启动都必须向服务端确认；service_enabled=False 时一律不得使用。
    scope='public_only' 时只影响公开渠道（内部渠道仍可用），便于维护者自己保留入口。
    """
    __tablename__ = "access_policy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    service_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    message: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="all")
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
