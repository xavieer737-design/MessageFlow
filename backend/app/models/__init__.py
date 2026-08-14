"""Import all models so SQLAlchemy metadata and Alembic autogenerate see them."""

from app.models.audit_log import AuditLog
from app.models.campaign import Campaign, CampaignRecipient
from app.models.contact import Contact, ContactGroup, contact_group_members
from app.models.device import Device, MessageAttempt, PairingSession, SendJob
from app.models.enums import (
    CampaignStatus,
    DeviceConnectionStatus,
    MessageAttemptStatus,
    MessageStatus,
    RecipientStatus,
    SendJobStatus,
)
from app.models.message_log import MessageLog
from app.models.opt_out import OptOut
from app.models.template import MessageTemplate
from app.models.user import User

__all__ = [
    "AuditLog",
    "Campaign",
    "CampaignRecipient",
    "CampaignStatus",
    "Contact",
    "ContactGroup",
    "Device",
    "DeviceConnectionStatus",
    "MessageAttempt",
    "MessageAttemptStatus",
    "MessageLog",
    "MessageStatus",
    "MessageTemplate",
    "OptOut",
    "PairingSession",
    "RecipientStatus",
    "SendJob",
    "SendJobStatus",
    "User",
    "contact_group_members",
]
