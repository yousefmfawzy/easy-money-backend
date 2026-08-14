from pydantic import BaseModel, PlainSerializer
from decimal import Decimal
from typing import Annotated
from datetime import datetime
from app.schemas.common import DecimalStr, UtcDatetime

class HistoryResponse(BaseModel):
    id: int
    etf_id: int
    old_value: DecimalStr
    new_value: DecimalStr
    change_amount: DecimalStr
    change_percentage: DecimalStr
    change_type: str
    input_value: DecimalStr
    created_at: UtcDatetime
