import enum
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Numeric, Enum, DateTime, ForeignKey
from app.db.base import Base

class RequestType(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"

class RequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class TradeRequest(Base):
    __tablename__ = "traderequest"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_name: Mapped[str] = mapped_column(String(120), nullable=False)
    requester_image_path: Mapped[str] = mapped_column(String(255), nullable=False)
    etf_id: Mapped[int] = mapped_column(ForeignKey("etf.id"), nullable=False, index=True)
    request_type: Mapped[RequestType] = mapped_column(Enum(RequestType), nullable=False)
    units: Mapped[Decimal] = mapped_column(Numeric(18, 2, asdecimal=True), nullable=False)
    etf_value_snapshot: Mapped[Decimal] = mapped_column(Numeric(18, 2, asdecimal=True), nullable=False)
    total_value_snapshot: Mapped[Decimal] = mapped_column(Numeric(18, 2, asdecimal=True), nullable=False)
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus), default=RequestStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
