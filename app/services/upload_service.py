import os
import uuid
from fastapi import UploadFile
from app.core.config import get_settings
from app.core.errors import AppError

settings = get_settings()

ALLOWED_TYPES = {
    "image/jpeg": b"\xFF\xD8\xFF",
    "image/png": b"\x89\x50\x4E\x47",
    "image/webp": b"RIFF" # Note: we just check first 4 bytes for WEBP
}

EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp"
}

async def save_upload(file: UploadFile, subdirectory: str) -> str:
    if file.content_type not in ALLOWED_TYPES:
        raise AppError(400, "UNSUPPORTED_IMAGE_TYPE", "Only JPEG, PNG, and WEBP images are supported")
        
    chunk = await file.read(12)
    if not chunk:
        raise AppError(400, "UNSUPPORTED_IMAGE_TYPE", "File is empty")
        
    if file.content_type == "image/jpeg" and not chunk.startswith(b"\xFF\xD8\xFF"):
        raise AppError(400, "UNSUPPORTED_IMAGE_TYPE", "File content does not match declared type")
    elif file.content_type == "image/png" and not chunk.startswith(b"\x89\x50\x4E\x47"):
        raise AppError(400, "UNSUPPORTED_IMAGE_TYPE", "File content does not match declared type")
    elif file.content_type == "image/webp" and not (chunk.startswith(b"RIFF") and chunk[8:12] == b"WEBP"):
        raise AppError(400, "UNSUPPORTED_IMAGE_TYPE", "File content does not match declared type")
        
    await file.seek(0)
    
    ext = EXTENSIONS[file.content_type]
    filename = f"{uuid.uuid4().hex}{ext}"
    rel_path = f"{subdirectory}/{filename}"
    
    base_dir = os.path.abspath(settings.UPLOAD_DIR)
    target_dir = os.path.abspath(os.path.join(base_dir, subdirectory))
    if not target_dir.startswith(base_dir):
        raise AppError(400, "BAD_REQUEST", "Invalid path")
        
    os.makedirs(target_dir, exist_ok=True)
    full_path = os.path.join(target_dir, filename)
    
    size = 0
    max_size = settings.MAX_UPLOAD_MB * 1024 * 1024
    
    with open(full_path, "wb") as f:
        while True:
            chunk = await file.read(8192)
            if not chunk:
                break
            size += len(chunk)
            if size > max_size:
                f.close()
                os.remove(full_path)
                raise AppError(413, "FILE_TOO_LARGE", f"File exceeds the maximum limit of {settings.MAX_UPLOAD_MB} MB")
            f.write(chunk)
            
    return rel_path
