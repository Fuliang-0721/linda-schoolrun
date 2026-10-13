from sqlalchemy import BigInteger, Boolean, Double, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


class SharedRouteModel(Base):
    __tablename__ = "shared_routes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    privacy_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    point_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    points: Mapped[list["SharedRoutePointModel"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="SharedRoutePointModel.sort_order",
    )


class SharedRoutePointModel(Base):
    __tablename__ = "shared_route_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("shared_routes.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    bd_longitude: Mapped[float] = mapped_column(Double(asdecimal=False), nullable=False)
    bd_latitude: Mapped[float] = mapped_column(Double(asdecimal=False), nullable=False)
    wgs_longitude: Mapped[float] = mapped_column(Double(asdecimal=False), nullable=False)
    wgs_latitude: Mapped[float] = mapped_column(Double(asdecimal=False), nullable=False)
    altitude: Mapped[float] = mapped_column(Float(asdecimal=False), nullable=False, default=55.0)

    route: Mapped[SharedRouteModel] = relationship(back_populates="points")
