from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories.device_repo import DeviceRepository
from app.schemas.device import (
    DeviceHeartbeatRequest,
    DeviceOut,
    DeviceRegisterRequest,
)
from app.services.audit_service import log_action

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceOut])
def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return DeviceRepository(db).list(user.id)


@router.post("/register", response_model=DeviceOut, status_code=201)
def register_device(
    payload: DeviceRegisterRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register a device for future pairing.

    Phase 1 stores the registration only; the device stays DISCONNECTED
    until the Phase 2 Android app establishes a real connection.
    """
    repo = DeviceRepository(db)
    existing = repo.get_by_identifier(user.id, payload.device_identifier)
    if existing:
        raise HTTPException(status_code=409, detail="Device with this identifier is already registered")
    device = repo.create(user.id, payload.device_name.strip(), payload.device_identifier, payload.platform)
    log_action(db, user.id, "device.registered", "device", device.id)
    db.commit()
    db.refresh(device)
    return device


@router.post("/{device_id}/heartbeat", response_model=DeviceOut)
def device_heartbeat(
    device_id: int,
    payload: DeviceHeartbeatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update last_seen for a registered device.

    Called by the future Android companion app. Phase 1 records the
    heartbeat timestamp without claiming any connectivity state change.
    """
    repo = DeviceRepository(db)
    device = repo.get(user.id, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.device_identifier != payload.device_identifier:
        raise HTTPException(status_code=403, detail="Device identifier mismatch")
    device = repo.heartbeat(device)
    db.commit()
    db.refresh(device)
    return device


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
