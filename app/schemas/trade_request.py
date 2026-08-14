from pydantic import BaseModel, Field, field_validator, PlainSerializer
from decimal import Decimal
from typing import Annotated
from datetime import datetime
from app.models.trade_request import RequestType, RequestStatus
from app.schemas.common import DecimalStr, UtcDatetime, OptionalUtcDatetime

class TradeRequestResponse(BaseModel):
    id: int
    requester_name: str
    requester_image_url: str
    etf_id: int
    etf_name: str
    request_type: RequestType
    units: DecimalStr
    etf_value_snapshot: DecimalStr
    total_value_snapshot: DecimalStr
    status: RequestStatus
    currency: str
    created_at: UtcDatetime
    processed_at: OptionalUtcDatetime

class TradeRequestStatusUpdate(BaseModel):
    status: RequestStatus
