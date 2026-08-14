from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Device


class DeviceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int, device_id: int) -> Device | None:
        return self.db.scalar(
            select(Device).where(Device.id == device_id, Device.user_id == user_id)
        )

    def get_by_identifier(self, user_id: int, identifier: str) -> Device | None:
        return self.db.scalar(
            select(Device).where(
                Device.user_id == user_id, Device.device_identifier == identifier
            )
        )

    def list(self, user_id: int) -> list[Device]:
        return list(
            self.db.scalars(
                select(Device).where(Device.user_id == user_id).order_by(Device.created_at.desc())
            ).all()
        )

    def create(self, user_id: int, device_name: str, identifier: str, platform: str) -> Device:
        device = Device(
            user_id=user_id,
            device_name=device_name,
            device_identifier=identifier,
            platform=platform or "android",
            connection_status="DISCONNECTED",
        )
        self.db.add(device)
        self.db.flush()
        return device

    def heartbeat(self, device: Device) -> Device:
        device.last_seen = datetime.now(timezone.utc)
        self.db.flush()
        return device

    def delete(self, device: Device) -> None:
        self.db.delete(device)
        self.db.flush()

    def connected_count(self, user_id: int) -> int:
        return len(
            list(
                self.db.scalars(
                    select(Device).where(
                        Device.user_id == user_id,
                        Device.connection_status == "CONNECTED",
                    )
                ).all()
            )
        )
