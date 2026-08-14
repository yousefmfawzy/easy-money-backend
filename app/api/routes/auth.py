from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.auth import LoginRequest, TokenResponse, AdminResponse
from app.services.auth_service import authenticate_admin
from app.db.session import get_db
from app.models.admin import Admin
from app.api.deps import get_current_admin

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    access_token = authenticate_admin(db, req.username, req.password)
    return TokenResponse(access_token=access_token, expires_in=43200)

@router.get("/me", response_model=AdminResponse)
def get_me(admin: Admin = Depends(get_current_admin)):
    return AdminResponse(id=admin.id, username=admin.username)
