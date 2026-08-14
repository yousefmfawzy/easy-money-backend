from fastapi.testclient import TestClient

def test_login_success(client: TestClient, seeded_db, settings):
    # Valid login
    response = client.post(
        "/api/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 43200

def test_login_invalid_password(client: TestClient, seeded_db, settings):
    response = client.post(
        "/api/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": "wrong-password"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "AUTH_FAILED"

def test_login_invalid_username(client: TestClient, seeded_db):
    response = client.post(
        "/api/auth/login",
        json={"username": "unknown_admin", "password": "somepassword"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "AUTH_FAILED"

def test_get_me_unauthorized(client: TestClient):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"

def test_get_me_authorized(client: TestClient, seeded_db, settings):
    login_response = client.post(
        "/api/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD}
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == settings.ADMIN_USERNAME
    assert "id" in data
