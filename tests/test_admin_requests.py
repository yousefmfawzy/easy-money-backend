import io
from fastapi.testclient import TestClient

def get_jpeg_bytes():
    return b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00"

def create_request_helper(client: TestClient, name: str, etf_id: int, rtype: str, units: str):
    files = {"requester_image": ("test.jpg", io.BytesIO(get_jpeg_bytes()), "image/jpeg")}
    data = {
        "requester_name": name,
        "etf_id": etf_id,
        "request_type": rtype,
        "units": units
    }
    return client.post("/api/requests", data=data, files=files).json()

def test_admin_listing_and_filtering(client: TestClient, auth_client: TestClient):
    # Create multiple requests
    create_request_helper(client, "Req 1", 1, "BUY", "10")
    create_request_helper(client, "Req 2", 1, "SELL", "5")
    create_request_helper(client, "Req 3", 2, "BUY", "1")
    
    # List all
    res = auth_client.get("/api/admin/requests")
    assert res.status_code == 200
    reqs = res.json()
    assert len(reqs) >= 3
    
    # Verify newest first (created_at DESC)
    # Since they are created in quick succession, we can at least check IDs if created_at is identical
    assert reqs[0]["id"] > reqs[1]["id"]
    
    # Filter by etf_id
    res_etf1 = auth_client.get("/api/admin/requests?etf_id=1")
    assert len(res_etf1.json()) == 2
    
    # Filter by request_type
    res_sell = auth_client.get("/api/admin/requests?request_type=SELL")
    assert len(res_sell.json()) == 1
    
    # Combination
    res_combo = auth_client.get("/api/admin/requests?etf_id=1&request_type=BUY")
    assert len(res_combo.json()) == 1

def test_admin_approve_and_reject(client: TestClient, auth_client: TestClient):
    req_json = create_request_helper(client, "Approve Me", 1, "BUY", "2")
    req_id = req_json["id"]
    
    # Approve
    res_app = auth_client.patch(f"/api/admin/requests/{req_id}/status", json={"status": "APPROVED"})
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "APPROVED"
    assert res_app.json()["processed_at"] is not None
    
    # Back to PENDING
    res_pend = auth_client.patch(f"/api/admin/requests/{req_id}/status", json={"status": "PENDING"})
    assert res_pend.status_code == 200
    assert res_pend.json()["processed_at"] is None
    
    # Reject
    res_rej = auth_client.patch(f"/api/admin/requests/{req_id}/status", json={"status": "REJECTED"})
    assert res_rej.status_code == 200
    assert res_rej.json()["status"] == "REJECTED"
    assert res_rej.json()["processed_at"] is not None

def test_approve_does_not_mutate_etf(client: TestClient, auth_client: TestClient):
    # Get ETF 4 before
    etf_before = auth_client.get("/api/etfs/4").json()
    history_before = auth_client.get("/api/etfs/4/history").json()
    
    # Create request
    req = create_request_helper(client, "Test mutate", 4, "BUY", "5")
    req_id = req["id"]
    
    # Approve
    auth_client.patch(f"/api/admin/requests/{req_id}/status", json={"status": "APPROVED"})
    
    # Get ETF 4 after
    etf_after = auth_client.get("/api/etfs/4").json()
    history_after = auth_client.get("/api/etfs/4/history").json()
    
    assert etf_before["current_value"] == etf_after["current_value"]
    assert etf_before["previous_value"] == etf_after["previous_value"]
    assert etf_before["trend"] == etf_after["trend"]
    assert len(history_before) == len(history_after)

def test_admin_routes_unauthorized(client: TestClient):
    # Without token
    assert client.get("/api/admin/requests").status_code == 401
    assert client.get("/api/admin/requests/1").status_code == 401
    assert client.patch("/api/admin/requests/1/status", json={"status": "APPROVED"}).status_code == 401
