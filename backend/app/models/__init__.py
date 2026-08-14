"""Import all models so SQLAlchemy metadata and Alembic autogenerate see them."""

from app.models.audit_log import AuditLog
from app.models.campaign import Campaign, CampaignRecipient
from app.models.contact import Contact, ContactGroup, contact_group_members
from app.models.device import Device
from app.models.enums import (
    CampaignStatus,
    DeviceConnectionStatus,
    MessageStatus,
    RecipientStatus,
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
    "MessageLog",
    "MessageStatus",
    "MessageTemplate",
    "OptOut",
    "RecipientStatus",
    "User",
    "contact_group_members",
]
