from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.group import GroupBrief


class ContactBase(BaseModel):
    phone: str = Field(min_length=3, max_length=32)
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    company: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)
    custom_fields: dict[str, str] = Field(default_factory=dict)


class ContactCreate(ContactBase):
    group_ids: list[int] = Field(default_factory=list)


class ContactUpdate(ContactBase):
    group_ids: list[int] | None = None


class ContactOut(ContactBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    groups: list[GroupBrief] = Field(default_factory=list)
    # True when the contact's phone is on the user's opt-out list.
    opted_out: bool = False
    created_at: datetime
    updated_at: datetime


class ContactListOut(BaseModel):
    items: list[ContactOut]
    total: int
    page: int
    page_size: int
    pages: int
