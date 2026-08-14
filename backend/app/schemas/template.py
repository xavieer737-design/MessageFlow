from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=5000)


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(TemplateBase):
    pass


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    message: str
    created_at: datetime
    updated_at: datetime


class TemplatePreviewRequest(BaseModel):
    """Preview a template against a sample contact."""

    message: str = Field(min_length=0, max_length=5000)
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    notes: str | None = None


class TemplatePreviewOut(BaseModel):
    preview: str
    variables_found: list[str]
    variables_missing: list[str]
