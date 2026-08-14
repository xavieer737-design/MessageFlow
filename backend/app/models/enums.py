"""Status constants used across models.

Stored as plain strings in the database (with CHECK constraints on
PostgreSQL) so the schema stays portable across SQLite and PostgreSQL.
"""

from enum import Enum


class StrEnum(str, Enum):
    """String enum that serializes to its value."""

    def __str__(self) -> str:  # pragma: no cover
        return self.value


class CampaignStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class RecipientStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    OPTED_OUT = "OPTED_OUT"


class DeviceConnectionStatus(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"


class MessageStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    OPTED_OUT = "OPTED_OUT"
