from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecipientTarget(BaseModel):
    """How a campaign selects its recipients.

    Exactly one of: all / group / contacts.
    """

    scope: Literal["all", "group", "contacts"] = "all"
    group_id: int | None = None
    contact_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope == "group" and not self.group_id:
            raise ValueError("group_id is required when scope is 'group'")
        if self.scope == "contacts" and not self.contact_ids:
            raise ValueError("contact_ids are required when scope is 'contacts'")
        return self


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    message_template: str = Field(min_length=1, max_length=5000)
    recipients: RecipientTarget = RecipientTarget()
    status: Literal["DRAFT", "READY"] = "DRAFT"
    scheduled_at: datetime | None = None


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    message_template: str | None = Field(default=None, min_length=1, max_length=5000)
    recipients: RecipientTarget | None = None
    status: Literal["DRAFT", "READY", "PAUSED", "CANCELLED"] | None = None
    scheduled_at: datetime | None = None


class CampaignRecipientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    contact_id: int | None
    personalized_message: str | None
    status: str
    error: str | None
    message_id: str | None = None
    queued_at: datetime | None = None
    sent_at: datetime | None = None
    attempt_count: int = 0
    created_at: datetime
    updated_at: datetime


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    message_template: str
    status: str
    scheduled_at: datetime | None
    # How recipients were selected (all | group | contacts).
    recipient_scope: str = "all"
    recipient_group_id: int | None = None
    recipient_contact_ids: list[int] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    recipient_count: int = 0
    sent_count: int = 0
    failed_count: int = 0
    pending_count: int = 0
    queued_count: int = 0
    skipped_count: int = 0
    opted_out_count: int = 0
    processing_count: int = 0
    recipients: list[CampaignRecipientOut] = Field(default_factory=list)


class CampaignListOut(BaseModel):
    items: list[CampaignOut]
    total: int
    page: int
    page_size: int
    pages: int


# --- Sending (Phase 2) ---


class CampaignSendRequest(BaseModel):
    device_id: int


class CampaignSendOut(BaseModel):
    job_id: int
    campaign_id: int
    device_id: int
    status: str
    queued: int
    skipped_opted_out: int
    skipped_invalid: int
    message: str


class CampaignProgressOut(BaseModel):
    campaign_id: int
    campaign_status: str
    job_status: str | None = None
    device_id: int | None = None
    device_name: str | None = None
    device_connection_status: str | None = None
    total: int
    pending: int
    queued: int
    processing: int
    sent: int
    failed: int
    skipped: int
    opted_out: int
    # 0..1 fraction of recipients that reached a terminal state.
    progress: float = 0.0


# --- Validation ---


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning", "info"]
    category: str
    message: str
    count: int = 1


class RecipientPreview(BaseModel):
    contact_id: int
    name: str
    phone: str
    preview: str | None
    status: str
    error: str | None


class CampaignValidationReport(BaseModel):
    campaign_id: int
    valid: bool
    total_recipients: int
    pending: int
    skipped_invalid_phone: int
    skipped_duplicate: int
    skipped_opted_out: int
    skipped_empty_message: int
    skipped_missing_fields: int
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    infos: list[ValidationIssue]
    previews: list[RecipientPreview]
