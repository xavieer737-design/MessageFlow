"""Device WebSocket authentication and protocol tests."""

import json

from fastapi.testclient import TestClient

from app.models import Device, OptOut
from tests.phase2_helpers import DeviceIdentity, auth_payload, pair_device


def _connect_and_authenticate(client: TestClient, identity, device, token) -> dict:
    with client.websocket_connect("/api/devices/ws") as ws:
        challenge = ws.receive_json()
        assert challenge["type"] == "challenge"
        ws.send_text(auth_payload(identity, challenge["nonce"], device, token))
        return ws.receive_json()


def test_ws_rejects_missing_token(client, user_client):
    identity = DeviceIdentity()
    body = pair_device(user_client, identity)
    with client.websocket_connect("/api/devices/ws") as ws:
        challenge = ws.receive_json()
        ws.send_text(json.dumps({"type": "auth", "device_id": body["device"]["id"], "token": "", "signature": ""}))
        # Server closes with an auth failure code.
        with __import__("pytest").raises(Exception):
            ws.receive_json()


def test_ws_rejects_invalid_token(client, user_client):
    identity = DeviceIdentity()
    body = pair_device(user_client, identity)
    with client.websocket_connect("/api/devices/ws") as ws:
        challenge = ws.receive_json()
        ws.send_text(
            json.dumps(
                {
                    "type": "auth",
                    "device_id": body["device"]["id"],
                    "token": "not-a-real-token",
                    "signature": identity.sign(challenge["nonce"]),
                }
            )
        )
        with __import__("pytest").raises(Exception):
            ws.receive_json()


def test_ws_rejects_wrong_signature(client, user_client):
    identity = DeviceIdentity()
    body = pair_device(user_client, identity)
    attacker = DeviceIdentity()  # different key
    with client.websocket_connect("/api/devices/ws") as ws:
        challenge = ws.receive_json()
        ws.send_text(
            json.dumps(
                {
                    "type": "auth",
                    "device_id": body["device"]["id"],
                    "token": body["device_token"],
                    "signature": attacker.sign(challenge["nonce"]),
                }
            )
        )
        with __import__("pytest").raises(Exception):
            ws.receive_json()


def test_ws_rejects_device_id_mismatch(client, user_client):
    identity = DeviceIdentity()
    body = pair_device(user_client, identity)
    with client.websocket_connect("/api/devices/ws") as ws:
        challenge = ws.receive_json()
        ws.send_text(
            json.dumps(
                {
                    "type": "auth",
                    "device_id": body["device"]["id"] + 999,
                    "token": body["device_token"],
                    "signature": identity.sign(challenge["nonce"]),
                }
            )
        )
        with __import__("pytest").raises(Exception):
            ws.receive_json()


def test_ws_authenticates_and_marks_connected(client, user_client, db):
    identity = DeviceIdentity()
    body = pair_device(user_client, identity)

    with client.websocket_connect("/api/devices/ws") as ws:
        challenge = ws.receive_json()
        ws.send_text(auth_payload(identity, challenge["nonce"], body["device"], body["device_token"]))
        welcome = ws.receive_json()
        assert welcome["type"] == "welcome"
        assert welcome["device_id"] == body["device"]["id"]

        device = db.get(Device, body["device"]["id"])
        assert device.connection_status == "CONNECTED"

    # After disconnect the device goes OFFLINE (never stays CONNECTED).
    device = db.get(Device, body["device"]["id"])
    assert device.connection_status == "OFFLINE"


def test_ws_heartbeat_updates_telemetry(client, user_client, db):
    identity = DeviceIdentity()
    body = pair_device(user_client, identity)

    with client.websocket_connect("/api/devices/ws") as ws:
        challenge = ws.receive_json()
        ws.send_text(auth_payload(identity, challenge["nonce"], body["device"], body["device_token"]))
        ws.receive_json()  # welcome

        ws.send_text(
            json.dumps(
                {
                    "type": "heartbeat",
                    "battery_level": 82,
                    "sim_state": "READY",
                    "network_state": "WIFI",
                    "app_version": "1.0.0",
                }
            )
        )
        ack = ws.receive_json()
        assert ack["type"] == "heartbeat_ack"

    device = db.get(Device, body["device"]["id"])
    assert device.battery_level == 82
    assert device.sim_state == "READY"
    assert device.network_state == "WIFI"
    assert device.app_version == "1.0.0"
    assert device.last_seen is not None


def test_ws_heartbeat_rest_route(user_client, db):
    body = pair_device(user_client)
    device_id = body["device"]["id"]
    response = user_client.post(
        f"/api/devices/{device_id}/heartbeat",
        json={
            "device_identifier": "android-id-1234567890",
            "battery_level": 55,
            "sim_state": "READY",
        },
    )
    assert response.status_code == 200
    assert response.json()["battery_level"] == 55
    device = db.get(Device, device_id)
    assert device.sim_state == "READY"
    # REST heartbeat never claims connectivity.
    assert device.connection_status == "DISCONNECTED"


def test_ws_incoming_sms_stop_adds_optout(client, user_client, db):
    identity = DeviceIdentity()
    body = pair_device(user_client, identity)

    with client.websocket_connect("/api/devices/ws") as ws:
        challenge = ws.receive_json()
        ws.send_text(auth_payload(identity, challenge["nonce"], body["device"], body["device_token"]))
        ws.receive_json()

        ws.send_text(
            json.dumps(
                {"type": "incoming_sms", "sender": "9876543210", "body": "STOP", "received_at": "now"}
            )
        )
        ack = ws.receive_json()
        assert ack["type"] == "incoming_sms_ack"
        assert ack["matched"] is True
        assert ack["phone"] == "+919876543210"

    entry = db.scalar(
        __import__("sqlalchemy").select(OptOut).where(OptOut.phone == "+919876543210")
    )
    assert entry is not None
    assert entry.reason == "STOP keyword received on device"


def test_ws_incoming_sms_non_stop_ignored(client, user_client, db):
    identity = DeviceIdentity()
    body = pair_device(user_client, identity)

    with client.websocket_connect("/api/devices/ws") as ws:
        challenge = ws.receive_json()
        ws.send_text(auth_payload(identity, challenge["nonce"], body["device"], body["device_token"]))
        ws.receive_json()
        ws.send_text(json.dumps({"type": "incoming_sms", "sender": "9876543210", "body": "hello there"}))
        ack = ws.receive_json()
        assert ack["matched"] is False

    assert db.query(OptOut).count() == 0


def test_ws_device_impersonation_blocked(client, user_client, second_user_client):
    """An attacker with a leaked device token cannot impersonate a device:
    they must also hold the device's private key (the challenge-response
    signature is verified against the stored public key)."""
    identity = DeviceIdentity()
    body = pair_device(user_client, identity)
    attacker_key = DeviceIdentity()  # attacker's own keypair

    with client.websocket_connect("/api/devices/ws") as ws:
        challenge = ws.receive_json()
        ws.send_text(
            json.dumps(
                {
                    "type": "auth",
                    "device_id": body["device"]["id"],
                    "token": body["device_token"],  # leaked valid token
                    "signature": attacker_key.sign(challenge["nonce"]),  # wrong private key
                }
            )
        )
        with __import__("pytest").raises(Exception):
            ws.receive_json()

    # And user B has no devices of their own.
    assert second_user_client.get("/api/devices").json() == []
