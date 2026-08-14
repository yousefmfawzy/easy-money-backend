"""Timestamps must reach the client as explicit UTC.

SQLite drops tzinfo, so a naive serialization would make the React dashboard
read every camp timestamp as local time. Added after the orchestrator caught
this in end-to-end verification.
"""

import io
from datetime import datetime, timezone


JPEG = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"


def _image():
    return {"requester_image": ("me.jpg", io.BytesIO(JPEG), "image/jpeg")}


def _assert_utc(value: str):
    assert value.endswith("Z"), f"{value!r} carries no UTC designator"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(None)


def test_all_timestamps_are_utc_designated(client, auth_client):
    auth_client.post("/api/admin/etfs/1/value", json={"value": "500.00"})

    _assert_utc(client.get("/api/etfs/1").json()["updated_at"])
    _assert_utc(client.get("/api/etfs/1/history").json()[0]["created_at"])

    created = client.post(
        "/api/requests",
        data={
            "requester_name": "Mina",
            "etf_id": 1,
            "request_type": "BUY",
            "units": "1",
        },
        files=_image(),
    ).json()
    _assert_utc(created["created_at"])
    assert created["processed_at"] is None

    processed = auth_client.patch(
        f"/api/admin/requests/{created['id']}/status", json={"status": "APPROVED"}
    ).json()
    _assert_utc(processed["processed_at"])


def test_server_generated_created_at_is_recent(client, auth_client):
    auth_client.post("/api/admin/etfs/1/value", json={"value": "100.00"})
    created = client.post(
        "/api/requests",
        data={
            "requester_name": "Sara",
            "etf_id": 1,
            "request_type": "SELL",
            "units": "1",
            # A client-supplied timestamp must be ignored entirely.
            "created_at": "2001-01-01T00:00:00Z",
        },
        files=_image(),
    ).json()

    parsed = datetime.fromisoformat(created["created_at"].replace("Z", "+00:00"))
    delta = abs((datetime.now(timezone.utc) - parsed).total_seconds())
    assert delta < 60, "created_at did not come from the server clock"
