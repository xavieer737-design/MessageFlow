from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OptOutCreate(BaseModel):
    phone: str = Field(min_length=3, max_length=32)
    reason: str | None = Field(default=None, max_length=500)


class OptOutBulkCreate(BaseModel):
    phones: list[str] = Field(min_length=1, max_length=5000)


class OptOutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    phone: str
    reason: str | None
    created_at: datetime


class OptOutListOut(BaseModel):
    items: list[OptOutOut]
    total: int
    page: int
    page_size: int
    pages: int


class OptOutBulkResult(BaseModel):
    imported: int
    skipped_invalid: list[str]
    duplicates: int
