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
    PROCESSING = "PROCESSING"  # command dispatched to the Android device
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


class MessageAttemptStatus(StrEnum):
    """Precise per-attempt states (see docs: delivery terminology).

    SEND_SUCCESS / SEND_FAILED are only written when the Android device
    reports the result of the actual SmsManager call. Nothing is ever
    marked sent by the backend on its own.
    """

    PENDING = "PENDING"              # attempt recorded, not yet dispatched
    SEND_REQUESTED = "SEND_REQUESTED"  # command delivered to the Android device
    SEND_SUCCESS = "SEND_SUCCESS"    # device confirmed SmsManager success
    SEND_FAILED = "SEND_FAILED"      # device reported an error
    SKIPPED = "SKIPPED"
    OPTED_OUT = "OPTED_OUT"


class SendJobStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"
