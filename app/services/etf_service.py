from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, timezone

from app.models.etf import ETF, Trend
from app.models.etf_history import ETFValueHistory, ChangeType
from app.core.money import pct_change, apply_percentage, trend_for
from app.core.errors import AppError

def get_etf_or_404(db: Session, id: int) -> ETF:
    etf = db.get(ETF, id)
    if not etf:
        raise AppError(404, "ETF_NOT_FOUND", f"ETF {id} does not exist")
    return etf

def update_metadata(db: Session, etf: ETF, name: str | None = None, logo_path: str | None = None) -> ETF:
    if name is not None:
        etf.name = name
    if logo_path is not None:
        etf.logo_path = logo_path
    
    db.commit()
    db.refresh(etf)
    return etf

def set_absolute_value(db: Session, etf: ETF, new_value: Decimal) -> ETF:
    old_value = etf.current_value
    
    etf.previous_value = old_value
    etf.current_value = new_value
    etf.last_change_amount = new_value - old_value
    etf.last_change_percentage = pct_change(old_value, new_value)
    
    # trend_for returns string, Trend is an enum
    etf.trend = Trend(trend_for(old_value, new_value))
    
    history = ETFValueHistory(
        etf_id=etf.id,
        old_value=old_value,
        new_value=new_value,
        change_amount=etf.last_change_amount,
        change_percentage=etf.last_change_percentage,
        change_type=ChangeType.ABSOLUTE,
        input_value=new_value
    )
    db.add(history)
    db.commit()
    db.refresh(etf)
    return etf

def adjust_by_percentage(db: Session, etf: ETF, pct: Decimal) -> ETF:
    if etf.current_value == Decimal("0"):
        raise AppError(400, "ZERO_VALUE_PERCENTAGE", "Cannot apply percentage to a zero-valued ETF")
        
    old_value = etf.current_value
    new_value = apply_percentage(old_value, pct)
    
    etf.previous_value = old_value
    etf.current_value = new_value
    etf.last_change_amount = new_value - old_value
    etf.last_change_percentage = pct_change(old_value, new_value)
    
    etf.trend = Trend(trend_for(old_value, new_value))
    
    history = ETFValueHistory(
        etf_id=etf.id,
        old_value=old_value,
        new_value=new_value,
        change_amount=etf.last_change_amount,
        change_percentage=etf.last_change_percentage,
        change_type=ChangeType.PERCENTAGE,
        input_value=pct
    )
    db.add(history)
    db.commit()
    db.refresh(etf)
    return etf
