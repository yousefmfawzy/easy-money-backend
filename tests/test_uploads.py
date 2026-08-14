import io
from fastapi.testclient import TestClient

def test_upload_valid_image(auth_client: TestClient):
    jpeg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00"
    files = {"file": ("test.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")}
    
    res = auth_client.post("/api/admin/etfs/1/logo", files=files)
    assert res.status_code == 200
    data = res.json()
    assert "logo_url" in data
    assert data["logo_url"].startswith("/uploads/etfs/")
    assert data["logo_url"].endswith(".jpg")
    assert "test.jpg" not in data["logo_url"]

def test_upload_text_rejected(auth_client: TestClient):
    files = {"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")}
    res = auth_client.post("/api/admin/etfs/1/logo", files=files)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "UNSUPPORTED_IMAGE_TYPE"

def test_upload_magic_mismatch(auth_client: TestClient):
    files = {"file": ("test.jpg", io.BytesIO(b"Not a jpeg but declares as one"), "image/jpeg")}
    res = auth_client.post("/api/admin/etfs/1/logo", files=files)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "UNSUPPORTED_IMAGE_TYPE"

def test_upload_too_large(auth_client: TestClient, monkeypatch):
    from app.core.config import get_settings
    
    settings = get_settings()
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0) # 0 MB max size, effectively 0 bytes
    
    jpeg_bytes = b"\xFF\xD8\xFF\xE0" + b"A" * 1024
    files = {"file": ("test.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")}
    
    res = auth_client.post("/api/admin/etfs/1/logo", files=files)
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "FILE_TOO_LARGE"
