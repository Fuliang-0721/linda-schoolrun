from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class InternalSoftwareNameModel(Base):
    __tablename__ = "internal_software_names"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    submitter_account_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    submitter_username: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    submitter_tester_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    reviewed_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
