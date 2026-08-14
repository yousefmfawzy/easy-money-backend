import enum
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Numeric, Enum, DateTime, ForeignKey, Index
from app.db.base import Base

class ChangeType(str, enum.Enum):
    ABSOLUTE = "ABSOLUTE"
    PERCENTAGE = "PERCENTAGE"

class ETFValueHistory(Base):
    __tablename__ = "etfvaluehistory"

    id: Mapped[int] = mapped_column(primary_key=True)
    etf_id: Mapped[int] = mapped_column(ForeignKey("etf.id", ondelete="CASCADE"), nullable=False, index=True)
    old_value: Mapped[Decimal] = mapped_column(Numeric(18, 2, asdecimal=True), nullable=False)
    new_value: Mapped[Decimal] = mapped_column(Numeric(18, 2, asdecimal=True), nullable=False)
    change_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2, asdecimal=True), nullable=False)
    change_percentage: Mapped[Decimal] = mapped_column(Numeric(9, 2, asdecimal=True), nullable=False)
    change_type: Mapped[ChangeType] = mapped_column(Enum(ChangeType), nullable=False)
    input_value: Mapped[Decimal] = mapped_column(Numeric(18, 2, asdecimal=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ix_etfvaluehistory_etf_id_created_at", "etf_id", "created_at"),
    )
