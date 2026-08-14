from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List

from app.db.session import get_db
from app.models.etf import ETF
from app.models.etf_history import ETFValueHistory
from app.schemas.etf import ETFResponse
from app.schemas.history import HistoryResponse
from app.core.config import get_settings
from app.services.etf_service import get_etf_or_404
from app.api.routes.admin_etfs import to_etf_response

router = APIRouter()

@router.get("", response_model=List[ETFResponse])
def get_etfs(db: Session = Depends(get_db)):
    etfs = db.scalars(select(ETF).order_by(ETF.id)).all()
    settings = get_settings()
    return [to_etf_response(etf, settings.CURRENCY) for etf in etfs]

@router.get("/{id}", response_model=ETFResponse)
def get_etf(id: int, db: Session = Depends(get_db)):
    etf = get_etf_or_404(db, id)
    settings = get_settings()
    return to_etf_response(etf, settings.CURRENCY)

@router.get("/{id}/history", response_model=List[HistoryResponse])
def get_etf_history(
    id: int, 
    limit: int = Query(200, le=1000), 
    db: Session = Depends(get_db)
):
    get_etf_or_404(db, id)
    history = db.scalars(
        select(ETFValueHistory)
        .where(ETFValueHistory.etf_id == id)
        .order_by(ETFValueHistory.created_at.asc())
        .limit(limit)
    ).all()
    
    return [
        HistoryResponse(
            id=h.id,
            etf_id=h.etf_id,
            old_value=h.old_value,
            new_value=h.new_value,
            change_amount=h.change_amount,
            change_percentage=h.change_percentage,
            change_type=h.change_type.value,
            input_value=h.input_value,
            created_at=h.created_at
        ) for h in history
    ]
