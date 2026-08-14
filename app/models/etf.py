import enum
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Numeric, Enum, DateTime
from app.db.base import Base

class Trend(str, enum.Enum):
    UP = "UP"
    DOWN = "DOWN"
    FLAT = "FLAT"

class ETF(Base):
    __tablename__ = "etf"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    logo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_value: Mapped[Decimal] = mapped_column(Numeric(18, 2, asdecimal=True), default=Decimal("0"), nullable=False)
    previous_value: Mapped[Decimal] = mapped_column(Numeric(18, 2, asdecimal=True), default=Decimal("0"), nullable=False)
    last_change_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2, asdecimal=True), default=Decimal("0"), nullable=False)
    last_change_percentage: Mapped[Decimal] = mapped_column(Numeric(9, 2, asdecimal=True), default=Decimal("0"), nullable=False)
    trend: Mapped[Trend] = mapped_column(Enum(Trend), default=Trend.FLAT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
