import os
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import UploadFile

from app.models.trade_request import TradeRequest, RequestStatus, RequestType
from app.services.etf_service import get_etf_or_404
from app.core.money import quantize_money
from app.core.errors import AppError
from app.services.upload_service import save_upload
from app.core.config import get_settings

settings = get_settings()

async def create_request(
    db: Session,
    requester_name: str,
    etf_id: int,
    request_type: RequestType,
    units: Decimal,
    requester_image: UploadFile
) -> TradeRequest:
    etf = get_etf_or_404(db, etf_id)
    
    etf_value_snapshot = etf.current_value
    total_value_snapshot = quantize_money(units * etf_value_snapshot)
    
    image_path = await save_upload(requester_image, "requests")
        
    now = datetime.now(timezone.utc)
    request = TradeRequest(
        requester_name=requester_name,
        requester_image_path=image_path,
        etf_id=etf_id,
        request_type=request_type,
        units=units,
        etf_value_snapshot=etf_value_snapshot,
        total_value_snapshot=total_value_snapshot,
        status=RequestStatus.PENDING,
        created_at=now
    )
    
    try:
        db.add(request)
        db.commit()
        db.refresh(request)
    except Exception as e:
        db.rollback()
        base_dir = os.path.abspath(settings.UPLOAD_DIR)
        full_path = os.path.join(base_dir, image_path)
        if os.path.exists(full_path):
            os.remove(full_path)
        raise AppError(500, "INTERNAL_ERROR", "Failed to create trade request") from e
        
    return request

def get_request_or_404(db: Session, id: int) -> TradeRequest:
    req = db.get(TradeRequest, id)
    if not req:
        raise AppError(404, "REQUEST_NOT_FOUND", f"TradeRequest {id} does not exist")
    return req

def list_requests(
    db: Session,
    status: RequestStatus | None = None,
    request_type: RequestType | None = None,
    etf_id: int | None = None,
    limit: int = 100,
    offset: int = 0
):
    query = db.query(TradeRequest)
    if status is not None:
        query = query.filter(TradeRequest.status == status)
    if request_type is not None:
        query = query.filter(TradeRequest.request_type == request_type)
    if etf_id is not None:
        query = query.filter(TradeRequest.etf_id == etf_id)
        
    return query.order_by(TradeRequest.created_at.desc(), TradeRequest.id.desc()).offset(offset).limit(limit).all()

def update_status(db: Session, req: TradeRequest, status: RequestStatus) -> TradeRequest:
    req.status = status
    if status in (RequestStatus.APPROVED, RequestStatus.REJECTED):
        req.processed_at = datetime.now(timezone.utc)
    else:
        req.processed_at = None
        
    db.commit()
    db.refresh(req)
    return req
