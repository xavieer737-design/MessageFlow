"""Device WebSocket endpoint.

Protocol (JSON messages):

Client connects to  /api/devices/ws

1. Server sends:      {"type": "challenge", "nonce": "<random hex>"}
2. Client replies:    {"type": "auth", "device_id": N, "token": "<device JWT>",
                       "signature": "<base64 RSA-SHA256 signature of nonce>"}
   The signature is produced with the private key that lives only in the
   Android Keystore; the server verifies it against the stored public key.
3. Server sends:      {"type": "welcome", "device_id": N, "server_time": ...}

Then:

Client -> Server:
  {"type": "heartbeat", "battery_level": 82, "sim_state": "READY",
   "network_state": "WIFI", "app_version": "1.0.0"}
  {"type": "message_result", "message_id": "...", "status": "SEND_SUCCESS|SEND_FAILED",
   "error": "...", "timestamp": "..."}
  {"type": "incoming_sms", "sender": "+919876543210", "body": "STOP", "received_at": "..."}
  {"type": "pong"}

Server -> Client:
  {"type": "send_message", "command_id": "...", "message_id": "...",
   "idempotency_key": "...", "phone": "...", "message": "...",
   "send_at": "<iso>", "test": bool}
  {"type": "pause"} / {"type": "resume"} / {"type": "cancel"}
  {"type": "ping"}
  {"type": "error", "message": "..."}

A device is only marked CONNECTED after successful authentication here.
"""

import asyncio
import base64
import json
import logging
import secrets

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_device_token
from app.db.session import get_db
from app.models import Campaign, Device
from app.services import send_service
from app.services.connection_manager import connection_manager
from app.services.send_service import process_heartbeat

router = APIRouter(tags=["devices-ws"])

PENDING_AUTH_TIMEOUT = 15.0


def _verify_signature(public_key_pem: str, nonce: str, signature_b64: str) -> bool:
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        signature = base64.b64decode(signature_b64)
        public_key.verify(
            signature,
            nonce.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:  # noqa: BLE001 - any crypto failure means reject
        return False


async def _send(websocket: WebSocket, payload: dict) -> None:
    try:
        await websocket.send_json(payload)
    except Exception:  # noqa: BLE001
        pass


@router.websocket("/devices/ws")
async def devices_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    device: Device | None = None
    try:
        # 1. Challenge
        nonce = secrets.token_hex(16)
        await _send(websocket, {"type": "challenge", "nonce": nonce})

        # 2. Authenticate (with timeout)
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=PENDING_AUTH_TIMEOUT)
        except asyncio.TimeoutError:
            await websocket.close(code=4001, reason="authentication timeout")
            return

        try:
            auth = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.close(code=4003, reason="invalid auth payload")
            return

        if auth.get("type") != "auth":
            await websocket.close(code=4003, reason="expected auth message")
            return

        payload = decode_device_token(auth.get("token", ""))
        if not payload:
            await websocket.close(code=4001, reason="invalid device token")
            return

        device = db.get(Device, int(payload["sub"]))
        if not device or device.user_id != int(payload["uid"]):
            await websocket.close(code=4001, reason="unknown device")
            return
        if device.device_identifier != payload.get("did"):
            await websocket.close(code=4001, reason="device identity mismatch")
            return
        if int(auth.get("device_id", -1)) != device.id:
            await websocket.close(code=4003, reason="device_id mismatch")
            return
        if not device.public_key:
            await websocket.close(code=4001, reason="device not paired")
            return

        # 3. Verify the challenge signature with the stored public key.
        signature = auth.get("signature", "")
        if not _verify_signature(device.public_key, nonce, signature):
            await websocket.close(code=4003, reason="signature verification failed")
            return

        # Authenticated.
        await connection_manager.register(device.id, websocket)
        send_service.mark_device_connected(db, device)
        db.commit()
        await _send(websocket, {"type": "welcome", "device_id": device.id})

        # 4. Message loop
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await _send(websocket, {"type": "error", "message": "invalid JSON"})
                continue

            msg_type = message.get("type")

            if msg_type == "heartbeat":
                process_heartbeat(
                    db,
                    device,
                    battery_level=message.get("battery_level"),
                    sim_state=message.get("sim_state"),
                    network_state=message.get("network_state"),
                    app_version=message.get("app_version"),
                    phone_model=message.get("phone_model"),
                    android_version=message.get("android_version"),
                )
                db.commit()
                await _send(websocket, {"type": "heartbeat_ack", "server_time": str(send_service._now())})

            elif msg_type == "message_result":
                attempt = send_service.handle_message_result(
                    db,
                    device.user_id,
                    device,
                    message.get("message_id", ""),
                    message.get("status", ""),
                    error=message.get("error"),
                    device_timestamp=message.get("timestamp"),
                )
                db.commit()
                await _send(
                    websocket,
                    {
                        "type": "result_ack",
                        "message_id": message.get("message_id", ""),
                        "recorded": attempt is not None,
                    },
                )

            elif msg_type == "incoming_sms":
                result = send_service.handle_incoming_sms(
                    db,
                    device,
                    sender=message.get("sender", ""),
                    body=message.get("body", ""),
                    received_at=message.get("received_at"),
                )
                db.commit()
                await _send(websocket, {"type": "incoming_sms_ack", **result})

            elif msg_type == "pong":
                pass

            else:
                await _send(websocket, {"type": "error", "message": f"unknown message type: {msg_type}"})

    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - keep the socket error contained
        logging.getLogger(__name__).exception("device websocket error")
    finally:
        if device is not None:
            await connection_manager.unregister(device.id, websocket)
            if device.connection_status == "CONNECTED":
                send_service.mark_device_offline(db, device, "websocket closed")
            # Auto-pause any active job on this device.
            if settings.PAUSE_CAMPAIGN_ON_DEVICE_OFFLINE:
                jobs = send_service.active_jobs_for_device(db, device.id)
                for job in jobs:
                    job.status = "PAUSED"
                    campaign = db.get(Campaign, job.campaign_id)
                    if campaign and campaign.status == "RUNNING":
                        campaign.status = "PAUSED"
            db.commit()


async def device_ws_ping_loop() -> None:
    """Send periodic pings to keep device connections alive."""
    while True:
        await asyncio.sleep(settings.DEVICE_WS_PING_SECONDS)
        await connection_manager.broadcast({"type": "ping"})
