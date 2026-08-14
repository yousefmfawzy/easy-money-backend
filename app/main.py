from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.db.seed import seed_db

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create upload directories
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "etfs"), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "requests"), exist_ok=True)
    
    # Run seeding
    seed_db()
    
    yield
    # Cleanup if necessary

app = FastAPI(
    title="Easy Money Backend",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

# Imports removed
from app.api.routes import health, auth, admin_etfs, etfs_public, requests_public, admin_requests
app.include_router(health.router)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(etfs_public.router, prefix="/api/etfs", tags=["etfs"])
app.include_router(admin_etfs.router, prefix="/api/admin/etfs", tags=["admin"])
app.include_router(requests_public.router, prefix="/api/requests", tags=["requests"])
app.include_router(admin_requests.router, prefix="/api/admin/requests", tags=["admin"])

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
