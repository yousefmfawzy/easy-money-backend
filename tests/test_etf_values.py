from fastapi.testclient import TestClient

def test_etf_absolute_value(auth_client: TestClient):
    auth_client.post("/api/admin/etfs/1/value", json={"value": "1000"})
    
    res = auth_client.post("/api/admin/etfs/1/value", json={"value": "1200"})
    assert res.status_code == 200
    data = res.json()
    assert data["previous_value"] == "1000.00"
    assert data["last_change_amount"] == "200.00"
    assert data["last_change_percentage"] == "20.00"
    assert data["trend"] == "UP"
    
    hist = auth_client.get("/api/etfs/1/history").json()
    last = hist[-1]
    assert last["change_type"] == "ABSOLUTE"
    assert last["input_value"] == "1200.00"

def test_etf_downward_and_flat(auth_client: TestClient):
    auth_client.post("/api/admin/etfs/2/value", json={"value": "1000"})
    res = auth_client.post("/api/admin/etfs/2/value", json={"value": "900"})
    assert res.json()["trend"] == "DOWN"
    
    res2 = auth_client.post("/api/admin/etfs/2/value", json={"value": "900"})
    assert res2.json()["trend"] == "FLAT"
    assert res2.json()["last_change_amount"] == "0.00"
    
    hist = auth_client.get("/api/etfs/2/history").json()
    assert len(hist) == 3

def test_negative_absolute_rejected(auth_client: TestClient):
    res = auth_client.post("/api/admin/etfs/1/value", json={"value": "-10"})
    assert res.status_code == 422

def test_etf_percentage_adjust(auth_client: TestClient):
    auth_client.post("/api/admin/etfs/3/value", json={"value": "1000"})
    
    res = auth_client.post("/api/admin/etfs/3/adjust", json={"percentage": "10"})
    assert res.json()["current_value"] == "1100.00"
    
    res2 = auth_client.post("/api/admin/etfs/3/adjust", json={"percentage": "-10"})
    assert res2.json()["current_value"] == "990.00"
    
    hist = auth_client.get("/api/etfs/3/history").json()
    assert hist[-1]["change_type"] == "PERCENTAGE"
    assert hist[-1]["input_value"] == "-10.00"

def test_percentage_against_zero_rejected(auth_client: TestClient):
    res = auth_client.post("/api/admin/etfs/4/adjust", json={"percentage": "10"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "ZERO_VALUE_PERCENTAGE"
    
    hist = auth_client.get("/api/etfs/4/history").json()
    assert len(hist) == 0

def test_chained_percentage_drift(auth_client: TestClient):
    auth_client.post("/api/admin/etfs/5/value", json={"value": "100"})
    
    for _ in range(10):
        auth_client.post("/api/admin/etfs/5/adjust", json={"percentage": "10"})
        
    res = auth_client.get("/api/etfs/5")
    assert res.json()["current_value"] == "259.39"

def test_public_get_etfs(client: TestClient, seeded_db, settings):
    res = client.get("/api/etfs")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 7
    assert data[0]["id"] == 1
    assert data[-1]["id"] == 7
    assert data[0]["currency"] == settings.CURRENCY

def test_history_oldest_first(auth_client: TestClient):
    auth_client.post("/api/admin/etfs/6/value", json={"value": "100"})
    auth_client.post("/api/admin/etfs/6/value", json={"value": "200"})
    
    hist = auth_client.get("/api/etfs/6/history").json()
    assert len(hist) == 2
    assert hist[0]["new_value"] == "100.00"
    assert hist[1]["new_value"] == "200.00"
