from app.models.etf import ETF
from app.models.admin import Admin
from sqlalchemy import select
from decimal import Decimal
from app.db.seed import seed_db

def test_seed_creates_exactly_7_etfs(seeded_db):
    etfs = seeded_db.scalars(select(ETF)).all()
    assert len(etfs) == 7
    for i, etf in enumerate(etfs, 1):
        assert etf.id == i
        assert etf.name == f"ETF {i}"
        assert etf.current_value == Decimal("0")
        assert etf.previous_value == Decimal("0")
        assert etf.last_change_amount == Decimal("0")
        assert etf.last_change_percentage == Decimal("0")
        assert etf.trend == "FLAT"

def test_seed_idempotency(seeded_db):
    # Re-run seed against the same session
    seed_db(seeded_db)
    
    etfs = seeded_db.scalars(select(ETF)).all()
    assert len(etfs) == 7
    
    admins = seeded_db.scalars(select(Admin)).all()
    assert len(admins) == 1

def test_seed_preserves_admin_changes(seeded_db):
    # Change an ETF
    etf = seeded_db.get(ETF, 1)
    etf.name = "Custom ETF"
    etf.current_value = Decimal("1500")
    seeded_db.commit()
    
    # Re-run seed against the same session
    seed_db(seeded_db)
    
    etf_after = seeded_db.get(ETF, 1)
    assert etf_after.name == "Custom ETF"
    assert etf_after.current_value == Decimal("1500")

def test_seed_updates_admin_password(seeded_db):
    admin = seeded_db.scalars(select(Admin)).first()
    old_hash = admin.password_hash
    
    # Run seed again with a "new" settings mock if we wanted, 
    # but even with same settings, it regenerates the hash due to bcrypt salt
    
    seed_db(seeded_db)
    
    seeded_db.refresh(admin)
    new_hash = admin.password_hash
    assert old_hash != new_hash # bcrypt generates different hashes for same password
