from sqlalchemy import BigInteger, Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class SharedSimulationConfigModel(Base):
    __tablename__ = "shared_simulation_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="speed")
    speed: Mapped[float] = mapped_column(Float(asdecimal=False), nullable=False, default=0.0)
    cadence: Mapped[float] = mapped_column(Float(asdecimal=False), nullable=False, default=0.0)
    loop_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    dynamic_intensity_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    intensity_variation_range: Mapped[float] = mapped_column(Float(asdecimal=False), nullable=False, default=0.0)
    intensity_variation_frequency: Mapped[float] = mapped_column(Float(asdecimal=False), nullable=False, default=0.0)
    natural_path_variation_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    path_variation_amplitude: Mapped[float] = mapped_column(Float(asdecimal=False), nullable=False, default=0.0)
    natural_altitude_variation_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    altitude_base_meters: Mapped[float] = mapped_column(Float(asdecimal=False), nullable=False, default=55.0)
    altitude_variation_range: Mapped[float] = mapped_column(Float(asdecimal=False), nullable=False, default=0.0)
    altitude_variation_height_centimeters: Mapped[float] = mapped_column(Float(asdecimal=False), nullable=False, default=0.0)
    altitude_variation_probability: Mapped[float] = mapped_column(Float(asdecimal=False), nullable=False, default=0.0)
    link_ratio_numerator: Mapped[float] = mapped_column(Float(asdecimal=False), nullable=False, default=1.0)
    steps_per_meter: Mapped[float] = mapped_column(Float(asdecimal=False), nullable=False, default=1.0)
    author_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    uploader_tester: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
