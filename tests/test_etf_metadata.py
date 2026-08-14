from fastapi.testclient import TestClient

def test_etf_rename_no_history(auth_client: TestClient):
    # Rename ETF 1
    response = auth_client.patch("/api/admin/etfs/1", json={"name": "New Name"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["current_value"] == "0.00"
    
    # Verify no history created
    history_resp = auth_client.get("/api/etfs/1/history")
    assert len(history_resp.json()) == 0

def test_etf_rename_empty_rejected(auth_client: TestClient):
    response = auth_client.patch("/api/admin/etfs/1", json={"name": "   "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
