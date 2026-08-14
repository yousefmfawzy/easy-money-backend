from fastapi import APIRouter, Depends, Form, UploadFile, File
from sqlalchemy.orm import Session
from decimal import Decimal

from app.db.session import get_db
from app.schemas.trade_request import TradeRequestResponse
from app.models.trade_request import TradeRequest, RequestType
from app.services.trade_request_service import create_request
from app.core.errors import AppError
from app.core.config import get_settings

router = APIRouter()

def to_trade_request_response(req: TradeRequest, currency: str, etf_name: str) -> TradeRequestResponse:
    requester_image_url = f"/uploads/{req.requester_image_path}"
    return TradeRequestResponse(
        id=req.id,
        requester_name=req.requester_name,
        requester_image_url=requester_image_url,
        etf_id=req.etf_id,
        etf_name=etf_name,
        request_type=req.request_type,
        units=req.units,
        etf_value_snapshot=req.etf_value_snapshot,
        total_value_snapshot=req.total_value_snapshot,
        status=req.status,
        currency=currency,
        created_at=req.created_at,
        processed_at=req.processed_at
    )

@router.post("", response_model=TradeRequestResponse, status_code=201)
async def submit_trade_request(
    requester_name: str = Form(...),
    etf_id: int = Form(...),
    request_type: RequestType = Form(...),
    units: Decimal = Form(...),
    requester_image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not requester_name.strip():
        raise AppError(422, "VALIDATION_ERROR", "requester_name cannot be empty")
        
    if units <= 0:
        raise AppError(422, "VALIDATION_ERROR", "units must be strictly positive")
        
    req = await create_request(
        db=db,
        requester_name=requester_name.strip(),
        etf_id=etf_id,
        request_type=request_type,
        units=units,
        requester_image=requester_image
    )
    
    from app.services.etf_service import get_etf_or_404
    etf = get_etf_or_404(db, etf_id)
    settings = get_settings()
    
    return to_trade_request_response(req, settings.CURRENCY, etf.name)


