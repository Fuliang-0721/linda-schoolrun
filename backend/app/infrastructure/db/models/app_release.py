from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AppReleaseModel(Base):
    """客户端版本发布记录（自动更新用）。

    status: draft（草稿，不下发）/ published（已发布，可下发）/ revoked（已撤销，停止下发）
    """

    __tablename__ = "app_releases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    package_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="stable", index=True)
    version_code: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    min_supported_version_code: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    force_update: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rollout_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    download_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    # JSON 数组字符串，例如 ["https://gitee.com/.../a.apk"]
    mirror_urls: Mapped[str] = mapped_column(Text, nullable=False, default="")
    changelog: Mapped[str] = mapped_column(Text, nullable=False, default="")
    release_notes_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    abi: Mapped[str] = mapped_column(String(32), nullable=False, default="arm64-v8a")
    # 定向发布白名单（JSON 数组字符串）：非空时只对这些 installId 下发，且忽略渠道限制
    target_install_ids: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    published_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
