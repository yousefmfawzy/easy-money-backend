import io
from fastapi.testclient import TestClient

def get_jpeg_bytes():
    return b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00"

def test_trade_request_buy_success(client: TestClient, auth_client: TestClient):
    # Seeded ETFs start at 0; the admin must price the market first.
    assert auth_client.post("/api/admin/etfs/1/value", json={"value": "1500.00"}).status_code == 200
    files = {"requester_image": ("test.jpg", io.BytesIO(get_jpeg_bytes()), "image/jpeg")}
    data = {
        "requester_name": "Test User",
        "etf_id": 1,
        "request_type": "BUY",
        "units": "2.5",
        "created_at": "2020-01-01T00:00:00Z", # Should be ignored
        "etf_value_snapshot": "9999.99"       # Should be ignored
    }
    
    res = client.post("/api/requests", data=data, files=files)
    assert res.status_code == 201
    res_data = res.json()
    
    assert res_data["requester_name"] == "Test User"
    assert res_data["request_type"] == "BUY"
    assert res_data["units"] == "2.50"
    assert res_data["status"] == "PENDING"
    assert res_data["etf_value_snapshot"] == "1500.00"
    assert res_data["total_value_snapshot"] == "3750.00"
    assert "2020-01-01" not in res_data["created_at"]
    assert res_data["processed_at"] is None

def test_trade_request_sell_success(client: TestClient, auth_client: TestClient):
    assert auth_client.post("/api/admin/etfs/2/value", json={"value": "1250.00"}).status_code == 200
    files = {"requester_image": ("test.jpg", io.BytesIO(get_jpeg_bytes()), "image/jpeg")}
    data = {
        "requester_name": "Test User 2",
        "etf_id": 2,
        "request_type": "SELL",
        "units": "10"
    }
    
    res = client.post("/api/requests", data=data, files=files)
    assert res.status_code == 201
    assert res.json()["total_value_snapshot"] == "12500.00"

def test_missing_image_rejected(client: TestClient):
    data = {
        "requester_name": "Test User",
        "etf_id": 1,
        "request_type": "BUY",
        "units": "2.5"
    }
    res = client.post("/api/requests", data=data)
    assert res.status_code == 422

def test_zero_or_negative_units_rejected(client: TestClient):
    # Zero units
    files = {"requester_image": ("test.jpg", io.BytesIO(get_jpeg_bytes()), "image/jpeg")}
    data = {
        "requester_name": "Test User",
        "etf_id": 1,
        "request_type": "BUY",
        "units": "0"
    }
    res = client.post("/api/requests", data=data, files=files)
    assert res.status_code == 422
    
    # Negative units
    files2 = {"requester_image": ("test.jpg", io.BytesIO(get_jpeg_bytes()), "image/jpeg")}
    data2 = {
        "requester_name": "Test User",
        "etf_id": 1,
        "request_type": "BUY",
        "units": "-5"
    }
    res2 = client.post("/api/requests", data=data2, files=files2)
    assert res2.status_code == 422

def test_unknown_etf_rejected(client: TestClient):
    files = {"requester_image": ("test.jpg", io.BytesIO(get_jpeg_bytes()), "image/jpeg")}
    data = {
        "requester_name": "Test User",
        "etf_id": 999,
        "request_type": "BUY",
        "units": "1"
    }
    res = client.post("/api/requests", data=data, files=files)
    assert res.status_code == 404

def test_snapshot_remains_unchanged_after_etf_price_update(client: TestClient, auth_client: TestClient):
    assert auth_client.post("/api/admin/etfs/3/value", json={"value": "3000.00"}).status_code == 200
    files = {"requester_image": ("test.jpg", io.BytesIO(get_jpeg_bytes()), "image/jpeg")}
    data = {
        "requester_name": "Test User",
        "etf_id": 3,
        "request_type": "BUY",
        "units": "2"
    }
    
    res = client.post("/api/requests", data=data, files=files)
    assert res.status_code == 201
    req_id = res.json()["id"]
    
    # Update ETF price via admin route
    update_res = auth_client.post("/api/admin/etfs/3/value", json={"value": "4000.00"})
    assert update_res.status_code == 200
    
    # Fetch request via admin route and verify snapshot is still 3000
    get_req_res = auth_client.get(f"/api/admin/requests/{req_id}")
    assert get_req_res.status_code == 200
    assert get_req_res.json()["etf_value_snapshot"] == "3000.00"
    assert get_req_res.json()["total_value_snapshot"] == "6000.00"
