from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories.device_repo import DeviceRepository
from app.schemas.device import (
    DeviceHeartbeatRequest,
    DeviceOut,
    DeviceRegisterRequest,
    PairingCompleteOut,
    PairingCompleteRequest,
    PairingStartOut,
    PairingStartRequest,
    PairingStatusOut,
    TestMessageRequest,
    TestMessageResult,
)
from app.services import send_service
from app.services.audit_service import log_action
from app.services.connection_manager import connection_manager
from app.services.pairing_service import (
    PairingError,
    complete_pairing,
    pairing_status,
    start_pairing,
)

router = APIRouter(prefix="/devices", tags=["devices"])


def _get_device_or_404(db: Session, user_id: int, device_id: int):
    device = DeviceRepository(db).get(user_id, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def _serialize_device(db: Session, device) -> DeviceOut:
    counters = send_service.device_counters(db, device.id)
    base = DeviceOut.model_validate(device).model_dump()
    base.update(counters)
    base["is_online"] = connection_manager.is_connected(device.id)
    return DeviceOut(**base)


@router.get("", response_model=list[DeviceOut])
def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    devices = DeviceRepository(db).list(user.id)
    return [_serialize_device(db, device) for device in devices]


@router.post("/register", response_model=DeviceOut, status_code=201)
def register_device(
    payload: DeviceRegisterRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register a device record (legacy Phase 1 flow).

    Pairing is the preferred Phase 2 flow (see /pairing/*); this endpoint
    only stores metadata and never marks the device connected.
    """
    repo = DeviceRepository(db)
    existing = repo.get_by_identifier(user.id, payload.device_identifier)
    if existing:
        raise HTTPException(status_code=409, detail="Device with this identifier is already registered")
    device = repo.create(user.id, payload.device_name.strip(), payload.device_identifier, payload.platform)
    log_action(db, user.id, "device.registered", "device", device.id)
    db.commit()
    db.refresh(device)
    return _serialize_device(db, device)


# --- Pairing (Phase 2) ---


@router.post("/pairing/start", response_model=PairingStartOut)
def pairing_start(
    payload: PairingStartRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a short-lived, single-use pairing session for the QR code."""
    try:
        session, token, qr_payload = start_pairing(
            db,
            user,
            payload.device_name,
            payload.device_identifier,
            server_url=str(request.base_url).rstrip("/"),
        )
    except PairingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    return PairingStartOut(
        session_id=session.id,
        token=token,
        qr_payload=qr_payload,
        expires_at=session.expires_at,
    )


@router.post("/pairing/complete", response_model=PairingCompleteOut)
def pairing_complete(
    payload: PairingCompleteRequest,
    db: Session = Depends(get_db),
):
    """Redeem a pairing token with the device's public key.

    Called by the Android app; no user session required (the token itself
    is the credential). Single-use: replaying the token returns 409/410.
    """
    try:
        device, device_token = complete_pairing(
            db,
            payload.token,
            payload.device_name,
            payload.device_identifier,
            payload.public_key,
            phone_model=payload.phone_model,
            android_version=payload.android_version,
            app_version=payload.app_version,
        )
    except PairingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    db.refresh(device)
    return PairingCompleteOut(
        device=DeviceOut.model_validate(device),
        device_token=device_token,
        server_time=send_service._now(),
    )


@router.get("/pairing/{session_id}", response_model=PairingStatusOut)
def pairing_status_endpoint(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Poll a pairing session from the web dashboard (QR screen)."""
    try:
        status = pairing_status(db, user.id, session_id)
    except PairingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return PairingStatusOut(**status)


# --- Heartbeat / lifecycle ---


@router.post("/{device_id}/heartbeat", response_model=DeviceOut)
def device_heartbeat(
    device_id: int,
    payload: DeviceHeartbeatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """REST fallback heartbeat (the WebSocket heartbeat is primary).

    Updates last_seen and telemetry; connectivity state is owned by the
    WebSocket layer and is not changed here.
    """
    repo = DeviceRepository(db)
    device = repo.get(user.id, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.device_identifier != payload.device_identifier:
        raise HTTPException(status_code=403, detail="Device identifier mismatch")
    device = send_service.process_heartbeat(
        db,
        device,
        battery_level=payload.battery_level,
        sim_state=payload.sim_state,
        network_state=payload.network_state,
        app_version=payload.app_version,
        phone_model=payload.phone_model,
        android_version=payload.android_version,
    )
    db.commit()
    db.refresh(device)
    return _serialize_device(db, device)


@router.post("/{device_id}/disconnect", response_model=DeviceOut)
def disconnect_device(
    device_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Explicitly disconnect a device (user action from the dashboard)."""
    import asyncio

    device = _get_device_or_404(db, user.id, device_id)
    send_service.mark_device_disconnected(db, device, "user requested")
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                connection_manager.send_to_device(
                    device.id, {"type": "disconnect", "command_id": ""}
                ),
                loop,
            )
    except RuntimeError:
        pass
    db.commit()
    db.refresh(device)
    return _serialize_device(db, device)


@router.delete("/{device_id}", status_code=204)
def delete_device(
    device_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = DeviceRepository(db)
    device = repo.get(user.id, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    repo.delete(device)
    log_action(db, user.id, "device.deleted", "device", device_id)
    db.commit()


# --- Test message ---


@router.post("/{device_id}/test-message", response_model=TestMessageResult, status_code=202)
def send_test_message(
    device_id: int,
    payload: TestMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send one test SMS through a connected device (real result only)."""
    device = _get_device_or_404(db, user.id, device_id)
    try:
        attempt = send_service.send_test_message(db, user.id, device, payload.phone, payload.message)
    except send_service.SendError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    db.refresh(attempt)
    return TestMessageResult(
        message_id=attempt.message_id,
        status=attempt.status,
        phone=attempt.phone,
        error=attempt.error,
        created_at=attempt.created_at,
        updated_at=attempt.updated_at,
    )


@router.get("/{device_id}/test-message/{message_id}", response_model=TestMessageResult)
def get_test_message_result(
    device_id: int,
    message_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = _get_device_or_404(db, user.id, device_id)
    attempt = send_service.test_message_result(db, user.id, device.id, message_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Test message not found")
    return TestMessageResult(
        message_id=attempt.message_id,
        status=attempt.status,
        phone=attempt.phone,
        error=attempt.error,
        created_at=attempt.created_at,
        updated_at=attempt.updated_at,
    )
