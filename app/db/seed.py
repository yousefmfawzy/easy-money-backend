import logging
from sqlalchemy import select
from app.db.session import SessionLocal
from app.core.config import get_settings
from app.core.security import hash_password
from app.models.admin import Admin
from app.models.etf import ETF, Trend
from decimal import Decimal

logger = logging.getLogger(__name__)

def seed_db(db=None):
    """Idempotently ensure the single admin and the seven ETF slots exist.

    Accepts an optional session so callers (and tests) can seed inside an
    existing unit of work; a session we did not create is never closed here.
    """
    settings = get_settings()
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        # Seed Admin
        admin_username = settings.ADMIN_USERNAME
        admin_password = settings.ADMIN_PASSWORD
        
        stmt = select(Admin).where(Admin.username == admin_username)
        admin = db.execute(stmt).scalar_one_or_none()
        
        if admin is None:
            new_admin = Admin(
                username=admin_username,
                password_hash=hash_password(admin_password)
            )
            db.add(new_admin)
            logger.info("Created initial admin account.")
        else:
            admin.password_hash = hash_password(admin_password)
            logger.info("Updated admin password hash.")
            
        # Seed ETFs
        for i in range(1, 8):
            etf = db.get(ETF, i)
            if etf is None:
                new_etf = ETF(
                    id=i,
                    name=f"ETF {i}",
                    current_value=Decimal("0"),
                    previous_value=Decimal("0"),
                    last_change_amount=Decimal("0"),
                    last_change_percentage=Decimal("0"),
                    trend=Trend.FLAT,
                    logo_path=None
                )
                db.add(new_etf)
                logger.info(f"Created ETF {i}.")
                
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        if owns_session:
            db.close()
