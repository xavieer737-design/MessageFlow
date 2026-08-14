from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceRegisterRequest(BaseModel):
    device_name: str = Field(min_length=1, max_length=120)
    device_identifier: str = Field(min_length=8, max_length=255)
    platform: str = Field(default="android", max_length=40)


class DeviceHeartbeatRequest(BaseModel):
    device_identifier: str = Field(min_length=8, max_length=255)


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    device_name: str
    device_identifier: str
    platform: str
    connection_status: str
    last_seen: datetime | None
    created_at: datetime
    updated_at: datetime
