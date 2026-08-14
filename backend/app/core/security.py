"""Password hashing and JWT helpers.

Uses bcrypt directly for password hashing and PyJWT for signed tokens.
All secrets come from environment configuration - never from code.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (includes per-password salt)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str) -> str:
    return create_token(
        subject,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str) -> str:
    return create_token(
        subject,
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str | None = None) -> dict | None:
    """Decode and validate a JWT. Returns payload or None if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if expected_type is not None and payload.get("type") != expected_type:
        return None
    return payload


# --- Device tokens (Phase 2) ---


def create_device_token(device_id: int, user_id: int, device_identifier: str) -> str:
    """Short-lived JWT authenticating a paired Android device over the
    WebSocket. Bound to the device record and its owner."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(device_id),
        "type": "device",
        "uid": user_id,
        "did": device_identifier,
        "iat": now,
        "exp": now + timedelta(days=settings.DEVICE_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_device_token(token: str) -> dict | None:
    return decode_token(token, "device")
