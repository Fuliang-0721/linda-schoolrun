from sqlalchemy import BigInteger, Double, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class ClientTelemetryModel(Base):
    """One current snapshot per consenting installation; never a location history."""
    __tablename__ = "client_telemetry"

    install_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    version_name: Mapped[str] = mapped_column(String(32), nullable=False)
    version_code: Mapped[int] = mapped_column(Integer, nullable=False)
    device_model: Mapped[str] = mapped_column(String(96), nullable=False)
    android_sdk: Mapped[int] = mapped_column(Integer, nullable=False)
    launches: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    simulation_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    simulation_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    first_seen: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_seen: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    latitude: Mapped[float | None] = mapped_column(Double, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Double, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    location_status: Mapped[str] = mapped_column(String(32), nullable=False, default="disabled")
