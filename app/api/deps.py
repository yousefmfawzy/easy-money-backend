from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.admin import Admin
from app.core.security import decode_access_token
from app.core.errors import AppError

security = HTTPBearer(auto_error=False)

def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db)
) -> Admin:
    if not credentials:
        raise AppError(401, "UNAUTHORIZED", "Missing or invalid token")
        
    token = credentials.credentials
    admin_id_str = decode_access_token(token)
    if not admin_id_str:
        raise AppError(401, "UNAUTHORIZED", "Invalid or expired token")
        
    try:
        admin_id = int(admin_id_str)
    except ValueError:
        raise AppError(401, "UNAUTHORIZED", "Invalid token subject")
        
    admin = db.execute(select(Admin).where(Admin.id == admin_id)).scalar_one_or_none()
    if not admin:
        raise AppError(401, "UNAUTHORIZED", "Admin not found")
        
    return admin
