from pydantic import BaseModel, Field, field_validator, PlainSerializer
from decimal import Decimal
from typing import Annotated
from datetime import datetime
from app.schemas.common import DecimalStr, UtcDatetime

class ETFResponse(BaseModel):
    id: int
    name: str
    logo_url: str | None
    current_value: DecimalStr
    previous_value: DecimalStr
    last_change_amount: DecimalStr
    last_change_percentage: DecimalStr
    trend: str
    updated_at: UtcDatetime
    currency: str

class ETFMetadataUpdate(BaseModel):
    name: str

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: str):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

class ETFValueUpdate(BaseModel):
    value: Decimal = Field(ge=0)

class ETFAdjustUpdate(BaseModel):
    percentage: Decimal
