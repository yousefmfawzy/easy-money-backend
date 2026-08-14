from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.etf import ETF
from app.models.admin import Admin
from app.schemas.etf import ETFResponse, ETFMetadataUpdate, ETFValueUpdate, ETFAdjustUpdate
from app.services.etf_service import update_metadata, set_absolute_value, adjust_by_percentage, get_etf_or_404
from app.services.upload_service import save_upload
from app.api.deps import get_current_admin
from app.core.config import get_settings

router = APIRouter()

def to_etf_response(etf: ETF, currency: str) -> ETFResponse:
    logo_url = f"/uploads/{etf.logo_path}" if etf.logo_path else None
    return ETFResponse(
        id=etf.id,
        name=etf.name,
        logo_url=logo_url,
        current_value=etf.current_value,
        previous_value=etf.previous_value,
        last_change_amount=etf.last_change_amount,
        last_change_percentage=etf.last_change_percentage,
        trend=etf.trend.value,
        updated_at=etf.updated_at,
        currency=currency
    )

@router.patch("/{id}", response_model=ETFResponse)
def update_etf_metadata(
    id: int, 
    req: ETFMetadataUpdate, 
    db: Session = Depends(get_db), 
    admin: Admin = Depends(get_current_admin)
):
    etf = get_etf_or_404(db, id)
    etf = update_metadata(db, etf, name=req.name)
    settings = get_settings()
    return to_etf_response(etf, settings.CURRENCY)

@router.post("/{id}/value", response_model=ETFResponse)
def update_etf_value(
    id: int, 
    req: ETFValueUpdate, 
    db: Session = Depends(get_db), 
    admin: Admin = Depends(get_current_admin)
):
    etf = get_etf_or_404(db, id)
    etf = set_absolute_value(db, etf, req.value)
    settings = get_settings()
    return to_etf_response(etf, settings.CURRENCY)

@router.post("/{id}/adjust", response_model=ETFResponse)
def adjust_etf_value(
    id: int, 
    req: ETFAdjustUpdate, 
    db: Session = Depends(get_db), 
    admin: Admin = Depends(get_current_admin)
):
    etf = get_etf_or_404(db, id)
    etf = adjust_by_percentage(db, etf, req.percentage)
    settings = get_settings()
    return to_etf_response(etf, settings.CURRENCY)

@router.post("/{id}/logo", response_model=ETFResponse)
async def upload_etf_logo(
    id: int, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db), 
    admin: Admin = Depends(get_current_admin)
):
    etf = get_etf_or_404(db, id)
    rel_path = await save_upload(file, "etfs")
    etf = update_metadata(db, etf, logo_path=rel_path)
    settings = get_settings()
    return to_etf_response(etf, settings.CURRENCY)
