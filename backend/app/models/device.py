from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.columns import utc_datetime_column, utcnow
from app.db.session import Base


class Device(Base):
    """An Android device paired to a MessageFlow account.

    Phase 2: pairing stores the device's public key (private key never
    leaves the phone), telemetry comes only from real heartbeats, and
    CONNECTED is only set after successful authenticated WebSocket
    communication - never merely because a row exists.
    """

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Unique identifier issued by the Android app (e.g. Android ID / UUID).
    device_identifier: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="android", nullable=False)
    connection_status: Mapped[str] = mapped_column(
        String(20), default="DISCONNECTED", index=True, nullable=False
    )
    # Device identity: public key (PEM) generated in the Android Keystore.
    public_key: Mapped[str | None] = mapped_column(Text)
    paired_at: Mapped[datetime | None] = utc_datetime_column(nullable=True)
    last_seen: Mapped[datetime | None] = utc_datetime_column(nullable=True)
    # Telemetry reported by the device (only what is actually reported).
    phone_model: Mapped[str | None] = mapped_column(String(120))
    android_version: Mapped[str | None] = mapped_column(String(40))
    app_version: Mapped[str | None] = mapped_column(String(40))
    battery_level: Mapped[int | None] = mapped_column(Integer)
    sim_state: Mapped[str | None] = mapped_column(String(40))
    network_state: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = utc_datetime_column()
    updated_at: Mapped[datetime] = utc_datetime_column(onupdate=utcnow)

    __table_args__ = (
        # A device identifier is unique per user.
        Index("uq_device_user_identifier", "user_id", "device_identifier", unique=True),
    )


class PairingSession(Base):
    """One-time, short-lived QR pairing session.

    Only the SHA-256 hash of the token is stored; the token itself is
    shown in the QR code and never persisted. Sessions are single-use.
    """

    __tablename__ = "pairing_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # sha256 hex of the random pairing token.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    device_name: Mapped[str] = mapped_column(String(120), nullable=False)
    device_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = utc_datetime_column()
    consumed_at: Mapped[datetime | None] = utc_datetime_column(nullable=True)
    created_at: Mapped[datetime] = utc_datetime_column()
    # The Device created when the token was redeemed.
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL")
    )

    device: Mapped[Device | None] = relationship()


class SendJob(Base):
    """A send queue for one campaign on one device.

    The server controls the queue; the Android device only executes
    batches it is told to send. Nothing is stored on the device long-term.
    """

    __tablename__ = "send_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True, nullable=False)
    batch_size: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    rate_per_minute: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    total_recipients: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = utc_datetime_column()
    completed_at: Mapped[datetime | None] = utc_datetime_column(nullable=True)
    created_at: Mapped[datetime] = utc_datetime_column()
    updated_at: Mapped[datetime] = utc_datetime_column(onupdate=utcnow)

    campaign = relationship("Campaign")
    device = relationship("Device")

    __table_args__ = (
        # Only one send job per campaign at a time.
        Index("uq_sendjob_campaign", "campaign_id", unique=True),
    )


class MessageAttempt(Base):
    """Every send attempt for a recipient, with idempotency bookkeeping.

    - message_id: unique per attempt; the Android device acknowledges by it.
    - idempotency_key: stable per logical message (campaign:recipient);
      a repeated dispatch for the same key is never re-sent once a
      terminal result exists.
    """

    __tablename__ = "message_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    recipient_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaign_recipients.id", ondelete="SET NULL"), index=True
    )
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    message_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True, nullable=False)
    error: Mapped[str | None] = mapped_column(String(500))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    sent_at: Mapped[datetime | None] = utc_datetime_column(nullable=True)
    device_timestamp: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = utc_datetime_column()
    updated_at: Mapped[datetime] = utc_datetime_column(onupdate=utcnow)

    __table_args__ = (
        Index("uq_attempt_idempotency", "idempotency_key", unique=True),
        Index("ix_attempt_campaign_status", "campaign_id", "status"),
    )
