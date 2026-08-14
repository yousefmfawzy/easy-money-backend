from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.admin import Admin
from app.core.security import verify_password, create_access_token
from app.core.errors import AppError

def authenticate_admin(db: Session, username: str, password: str) -> str:
    stmt = select(Admin).where(Admin.username == username)
    admin = db.execute(stmt).scalar_one_or_none()
    
    if not admin:
        raise AppError(401, "AUTH_FAILED", "Invalid credentials")
        
    if not verify_password(password, admin.password_hash):
        raise AppError(401, "AUTH_FAILED", "Invalid credentials")
        
    return create_access_token(admin.id)
