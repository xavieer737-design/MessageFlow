"""QR pairing business logic.

Flow:
1. Web user calls POST /api/devices/pairing/start -> a random one-time
   token (only its SHA-256 hash is stored) with a short TTL.
2. The QR code embeds a JSON payload: {"mf":1,"server":<url>,"token":<token>}.
   No passwords, JWT secrets, database credentials or private keys ever
   appear in the QR.
3. The Android app scans the QR and calls POST /api/devices/pairing/complete
   with the token + its public key (generated in the Android Keystore).
4. The backend validates hash, expiry and one-time use, creates the Device
   record with the public key, and returns a short-lived device JWT used
   to authenticate the WebSocket connection.
"""

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_device_token
from app.models import Device, PairingSession, User
from app.services.audit_service import log_action
from app.utils.dates import ensure_utc


class PairingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def build_qr_payload(server_url: str, token: str) -> str:
    """JSON payload placed inside the QR code.

    `server` lets the phone discover which backend to reach; the token is
    the single-use credential. Nothing secret beyond the short-lived token.
    """
    return json.dumps({"mf": 1, "server": server_url.rstrip("/"), "token": token})


def start_pairing(
    db: Session,
    user: User,
    device_name: str,
    device_identifier: str,
    server_url: str | None = None,
) -> tuple[PairingSession, str, str]:
    """Create a pairing session. Returns (session, token, qr_payload)."""
    if len(device_identifier) < 8:
        raise PairingError("device_identifier must be at least 8 characters", 422)

    token = generate_token()
    session = PairingSession(
        user_id=user.id,
        token_hash=hash_token(token),
        device_name=device_name.strip() or "Android device",
        device_identifier=device_identifier,
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.PAIRING_TOKEN_TTL_MINUTES),
    )
    db.add(session)
    db.flush()

    server = server_url or "http://localhost:8000"
    qr_payload = build_qr_payload(server, token)

    log_action(db, user.id, "pairing.started", "device", None, {"session_id": session.id})
    return session, token, qr_payload


def complete_pairing(
    db: Session,
    token: str,
    device_name: str,
    device_identifier: str,
    public_key: str,
    phone_model: str | None = None,
    android_version: str | None = None,
    app_version: str | None = None,
) -> tuple[Device, str]:
    """Validate a pairing token and create the paired Device record.

    Returns (device, device_token). Single-use: the session is consumed
    atomically so a token can never be replayed.
    """
    now = datetime.now(timezone.utc)
    session = db.scalar(
        select(PairingSession).where(PairingSession.token_hash == hash_token(token))
    )
    if not session:
        raise PairingError("Invalid pairing token.", 404)
    if session.consumed_at is not None:
        raise PairingError("This pairing token has already been used.", 409)
    if ensure_utc(session.expires_at) < now:
        raise PairingError("This pairing token has expired. Start a new pairing.", 410)
    if session.device_name != device_name or session.device_identifier != device_identifier:
        # The completing request must match the intent captured at start.
        raise PairingError("Pairing details do not match the pairing session.", 409)

    # Consume the session first (one-time use).
    session.consumed_at = now

    existing = db.scalar(
        select(Device).where(
            Device.user_id == session.user_id,
            Device.device_identifier == device_identifier,
        )
    )
    if existing:
        device = existing
        device.public_key = public_key
        device.device_name = device_name
        device.paired_at = now
        device.phone_model = phone_model
        device.android_version = android_version
        device.app_version = app_version
        device.connection_status = "DISCONNECTED"
        device.last_seen = None
    else:
        device = Device(
            user_id=session.user_id,
            device_name=device_name,
            device_identifier=device_identifier,
            platform="android",
            connection_status="DISCONNECTED",
            public_key=public_key,
            paired_at=now,
            phone_model=phone_model,
            android_version=android_version,
            app_version=app_version,
        )
        db.add(device)
    db.flush()
    session.device_id = device.id

    log_action(
        db,
        session.user_id,
        "device.paired",
        "device",
        device.id,
        {"device_name": device_name},
    )

    device_token = create_device_token(device.id, session.user_id, device.device_identifier)
    return device, device_token


def pairing_status(db: Session, user_id: int, session_id: int) -> dict:
    session = db.scalar(
        select(PairingSession).where(
            PairingSession.id == session_id, PairingSession.user_id == user_id
        )
    )
    if not session:
        raise PairingError("Pairing session not found.", 404)
    if session.consumed_at is not None and session.device is not None:
        return {
            "session_id": session.id,
            "status": "paired",
            "expires_at": session.expires_at,
            "device": session.device,
        }
    if ensure_utc(session.expires_at) < datetime.now(timezone.utc):
        return {"session_id": session.id, "status": "expired", "expires_at": session.expires_at}
    return {"session_id": session.id, "status": "pending", "expires_at": session.expires_at}
