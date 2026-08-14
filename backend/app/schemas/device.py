from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceRegisterRequest(BaseModel):
    device_name: str = Field(min_length=1, max_length=120)
    device_identifier: str = Field(min_length=8, max_length=255)
    platform: str = Field(default="android", max_length=40)


class DeviceHeartbeatRequest(BaseModel):
    device_identifier: str = Field(min_length=8, max_length=255)
    battery_level: int | None = Field(default=None, ge=0, le=100)
    sim_state: str | None = Field(default=None, max_length=40)
    network_state: str | None = Field(default=None, max_length=40)
    app_version: str | None = Field(default=None, max_length=40)
    phone_model: str | None = Field(default=None, max_length=120)
    android_version: str | None = Field(default=None, max_length=40)


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    device_name: str
    device_identifier: str
    platform: str
    connection_status: str
    public_key: str | None = None
    paired_at: datetime | None = None
    phone_model: str | None = None
    android_version: str | None = None
    app_version: str | None = None
    battery_level: int | None = None
    sim_state: str | None = None
    network_state: str | None = None
    last_seen: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Live counters for the device card (computed from real records).
    messages_queued: int = 0
    messages_sent: int = 0
    messages_failed: int = 0
    is_online: bool = False


# --- Pairing ---


class PairingStartRequest(BaseModel):
    device_name: str = Field(min_length=1, max_length=120)
    device_identifier: str = Field(min_length=8, max_length=255)


class PairingStartOut(BaseModel):
    session_id: int
    token: str
    qr_payload: str  # JSON the Android app scans
    expires_at: datetime


class PairingCompleteRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    device_name: str = Field(min_length=1, max_length=120)
    device_identifier: str = Field(min_length=8, max_length=255)
    public_key: str = Field(min_length=32)
    phone_model: str | None = Field(default=None, max_length=120)
    android_version: str | None = Field(default=None, max_length=40)
    app_version: str | None = Field(default=None, max_length=40)


class PairingCompleteOut(BaseModel):
    device: DeviceOut
    device_token: str
    server_time: datetime


class PairingStatusOut(BaseModel):
    session_id: int
    status: str  # pending | expired | paired
    expires_at: datetime | None = None
    device: DeviceOut | None = None


# --- Test message ---


class TestMessageRequest(BaseModel):
    phone: str = Field(min_length=3, max_length=32)
    message: str = Field(min_length=1, max_length=5000)


class TestMessageResult(BaseModel):
    message_id: str
    status: str  # PENDING | SEND_REQUESTED | SEND_SUCCESS | SEND_FAILED | SKIPPED | OPTED_OUT
    phone: str
    error: str | None = None
    created_at: datetime
    updated_at: datetime
