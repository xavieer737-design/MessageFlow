from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    campaign_id: int | None
    contact_id: int | None
    device_id: int | None
    message: str | None
    status: str
    error: str | None
    sent_at: datetime | None
    created_at: datetime
    campaign_name: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    device_name: str | None = None


class MessageLogListOut(BaseModel):
    items: list[MessageLogOut]
    total: int
    page: int
    page_size: int
    pages: int
