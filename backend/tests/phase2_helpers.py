"""Shared helpers for Phase 2 tests: RSA identities, pairing, fake WS."""

import asyncio
import base64
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.services.connection_manager import connection_manager


class DeviceIdentity:
    """A test-side Android identity (RSA keypair, like the Keystore)."""

    def __init__(self) -> None:
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key_pem = (
            self.private_key.public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("utf-8")
        )

    def sign(self, message: str) -> str:
        signature = self.private_key.sign(
            message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256()
        )
        return base64.b64encode(signature).decode("ascii")


def pair_device(client, identity: DeviceIdentity | None = None, device_identifier: str | None = None) -> dict:
    """Full pairing flow through the API. Returns pairing response body."""
    identity = identity or DeviceIdentity()
    identifier = device_identifier or "android-id-1234567890"

    started = client.post(
        "/api/devices/pairing/start",
        json={"device_name": "Pixel 8", "device_identifier": identifier},
    )
    assert started.status_code == 200, started.text
    start_body = started.json()

    completed = client.post(
        "/api/devices/pairing/complete",
        json={
            "token": start_body["token"],
            "device_name": "Pixel 8",
            "device_identifier": identifier,
            "public_key": identity.public_key_pem,
            "phone_model": "Google Pixel 8",
            "android_version": "14",
            "app_version": "1.0.0",
        },
    )
    assert completed.status_code == 200, completed.text
    return completed.json()


class FakeWebSocket:
    """In-memory stand-in for a registered device WebSocket."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


async def register_fake_device(device_id: int) -> FakeWebSocket:
    ws = FakeWebSocket()
    await connection_manager.register(device_id, ws)
    return ws


def unregister_fake_device(device_id: int) -> None:
    asyncio.run(connection_manager.unregister(device_id))


def sent_commands(ws: FakeWebSocket) -> list[dict]:
    return [m for m in ws.sent if m.get("type") == "send_message"]


def auth_payload(identity: DeviceIdentity, nonce: str, device: dict, token: str) -> str:
    return json.dumps(
        {
            "type": "auth",
            "device_id": device["id"],
            "token": token,
            "signature": identity.sign(nonce),
        }
    )
