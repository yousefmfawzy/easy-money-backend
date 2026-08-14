from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.api.deps import get_current_admin
from app.models.admin import Admin
from app.models.trade_request import RequestStatus, RequestType
from app.schemas.trade_request import TradeRequestResponse, TradeRequestStatusUpdate
from app.services.trade_request_service import list_requests, get_request_or_404, update_status
from app.services.etf_service import get_etf_or_404
from app.core.config import get_settings
from app.api.routes.requests_public import to_trade_request_response
from app.models.etf import ETF

router = APIRouter()

@router.get("", response_model=List[TradeRequestResponse])
def get_admin_requests(
    status: RequestStatus | None = None,
    request_type: RequestType | None = None,
    etf_id: int | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    reqs = list_requests(db, status=status, request_type=request_type, etf_id=etf_id, limit=limit, offset=offset)
    settings = get_settings()
    
    etf_dict = {e.id: e.name for e in db.query(ETF).all()}
    
    return [to_trade_request_response(req, settings.CURRENCY, etf_dict[req.etf_id]) for req in reqs]

@router.get("/{id}", response_model=TradeRequestResponse)
def get_admin_request(
    id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    req = get_request_or_404(db, id)
    etf = get_etf_or_404(db, req.etf_id)
    settings = get_settings()
    return to_trade_request_response(req, settings.CURRENCY, etf.name)

@router.patch("/{id}/status", response_model=TradeRequestResponse)
def update_admin_request_status(
    id: int,
    status_update: TradeRequestStatusUpdate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin)
):
    req = get_request_or_404(db, id)
    req = update_status(db, req, status_update.status)
    etf = get_etf_or_404(db, req.etf_id)
    settings = get_settings()
    return to_trade_request_response(req, settings.CURRENCY, etf.name)
