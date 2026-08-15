"""Pairing session tests: generation, expiry, one-time use, isolation."""

import json
from datetime import datetime, timedelta, timezone

from app.models import PairingSession
from tests.phase2_helpers import DeviceIdentity, pair_device


def test_pairing_start_creates_session(user_client, db):
    response = user_client.post(
        "/api/devices/pairing/start",
        json={"device_name": "Pixel 8", "device_identifier": "android-id-1234567890"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] > 0
    assert len(body["token"]) >= 32

    # QR payload contains only the token + server URL - no secrets.
    qr = json.loads(body["qr_payload"])
    assert qr["mf"] == 1
    assert qr["token"] == body["token"]
    assert qr["server"].startswith("http")

    # Only the token hash is stored - never the token itself.
    session = db.get(PairingSession, body["session_id"])
    assert session.token_hash != body["token"]
    assert session.token_hash == __import__("app.services.pairing_service", fromlist=["hash_token"]).hash_token(body["token"])
    assert session.consumed_at is None


def test_pairing_complete_creates_device_with_public_key(user_client):
    identity = DeviceIdentity()
    body = pair_device(user_client, identity)

    assert body["device"]["device_name"] == "Pixel 8"
    assert body["device"]["public_key"] == identity.public_key_pem
    assert body["device"]["paired_at"] is not None
    assert body["device"]["phone_model"] == "Google Pixel 8"
    assert body["device"]["android_version"] == "14"
    assert body["device"]["connection_status"] == "DISCONNECTED"  # not connected yet
    assert body["device_token"]

    # Devices list shows the paired device.
    devices = user_client.get("/api/devices").json()
    assert len(devices) == 1
    assert devices[0]["id"] == body["device"]["id"]


def test_pairing_token_is_single_use(user_client):
    started = user_client.post(
        "/api/devices/pairing/start",
        json={"device_name": "Pixel 8", "device_identifier": "android-id-1234567890"},
    ).json()
    payload = {
        "token": started["token"],
        "device_name": "Pixel 8",
        "device_identifier": "android-id-1234567890",
        "public_key": DeviceIdentity().public_key_pem,
    }
    assert user_client.post("/api/devices/pairing/complete", json=payload).status_code == 200

    # Replaying the same token must fail.
    replay = user_client.post("/api/devices/pairing/complete", json=payload)
    assert replay.status_code == 409
    assert "already been used" in replay.json()["detail"]


def test_pairing_token_expires(user_client, db):
    started = user_client.post(
        "/api/devices/pairing/start",
        json={"device_name": "Pixel 8", "device_identifier": "android-id-1234567890"},
    ).json()
    session = db.get(PairingSession, started["session_id"])
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    response = user_client.post(
        "/api/devices/pairing/complete",
        json={
            "token": started["token"],
            "device_name": "Pixel 8",
            "device_identifier": "android-id-1234567890",
            "public_key": DeviceIdentity().public_key_pem,
        },
    )
    assert response.status_code == 410
    assert "expired" in response.json()["detail"]


def test_pairing_unknown_token(user_client):
    response = user_client.post(
        "/api/devices/pairing/complete",
        json={
            "token": "does-not-exist-1234567890",
            "device_name": "Pixel 8",
            "device_identifier": "android-id-1234567890",
            "public_key": DeviceIdentity().public_key_pem,
        },
    )
    assert response.status_code == 404


def test_pairing_details_must_match_session(user_client):
    started = user_client.post(
        "/api/devices/pairing/start",
        json={"device_name": "Pixel 8", "device_identifier": "android-id-1234567890"},
    ).json()
    response = user_client.post(
        "/api/devices/pairing/complete",
        json={
            "token": started["token"],
            "device_name": "Different Device",
            "device_identifier": "android-id-1234567890",
            "public_key": DeviceIdentity().public_key_pem,
        },
    )
    assert response.status_code == 409


def test_pairing_status_polling(user_client):
    started = user_client.post(
        "/api/devices/pairing/start",
        json={"device_name": "Pixel 8", "device_identifier": "android-id-1234567890"},
    ).json()
    pending = user_client.get(f"/api/devices/pairing/{started['session_id']}").json()
    assert pending["status"] == "pending"

    # Redeem the same session's token (as the Android app would).
    identity = DeviceIdentity()
    completed = user_client.post(
        "/api/devices/pairing/complete",
        json={
            "token": started["token"],
            "device_name": "Pixel 8",
            "device_identifier": "android-id-1234567890",
            "public_key": identity.public_key_pem,
        },
    )
    assert completed.status_code == 200

    paired = user_client.get(f"/api/devices/pairing/{started['session_id']}").json()
    assert paired["status"] == "paired"
    assert paired["device"]["device_name"] == "Pixel 8"


def test_pairing_session_isolation(client, user_client, second_user_client):
    started = user_client.post(
        "/api/devices/pairing/start",
        json={"device_name": "Pixel 8", "device_identifier": "android-id-1234567890"},
    ).json()
    # User B cannot poll user A's pairing session.
    assert second_user_client.get(f"/api/devices/pairing/{started['session_id']}").status_code == 404
    # And user B's device list stays empty.
    assert second_user_client.get("/api/devices").json() == []


def test_pairing_complete_requires_valid_public_key(user_client):
    started = user_client.post(
        "/api/devices/pairing/start",
        json={"device_name": "Pixel 8", "device_identifier": "android-id-1234567890"},
    ).json()
    response = user_client.post(
        "/api/devices/pairing/complete",
        json={
            "token": started["token"],
            "device_name": "Pixel 8",
            "device_identifier": "android-id-1234567890",
            "public_key": "not-a-pem-key",
        },
    )
    assert response.status_code == 422


def test_repairing_same_device_updates_key(user_client):
    first = pair_device(user_client)
    second_identity = DeviceIdentity()
    second = pair_device(user_client, identity=second_identity, device_identifier="android-id-1234567890")

    # Same device row, updated public key, no duplicates.
    assert second["device"]["id"] == first["device"]["id"]
    devices = user_client.get("/api/devices").json()
    assert len(devices) == 1
    assert devices[0]["public_key"] == second_identity.public_key_pem


def test_qr_server_url_uses_forwarded_host(user_client):
    """Behind the Vite dev proxy / a reverse proxy, the QR must carry the
    address the browser used - not the proxy's upstream target.

    Regression: changeOrigin rewrites Host to 127.0.0.1:8000, which a phone
    resolves to itself, so pairing could never connect.
    """
    response = user_client.post(
        "/api/devices/pairing/start",
        json={"device_name": "Pixel 8", "device_identifier": "android-id-1234567890"},
        headers={"X-Forwarded-Host": "192.168.1.50:5173", "X-Forwarded-Proto": "http"},
    )
    assert response.status_code == 200
    qr = json.loads(response.json()["qr_payload"])
    assert qr["server"] == "http://192.168.1.50:5173"


def test_qr_server_url_respects_explicit_setting(user_client, monkeypatch):
    """PUBLIC_SERVER_URL always wins - required when the phone reaches the
    backend through an address the request itself never sees."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "PUBLIC_SERVER_URL", "https://sms.example.com")
    response = user_client.post(
        "/api/devices/pairing/start",
        json={"device_name": "Pixel 8", "device_identifier": "android-id-1234567890"},
        headers={"X-Forwarded-Host": "192.168.1.50:5173"},
    )
    assert response.status_code == 200
    qr = json.loads(response.json()["qr_payload"])
    assert qr["server"] == "https://sms.example.com"
