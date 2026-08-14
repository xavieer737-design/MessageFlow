from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.columns import utc_datetime_column, utcnow
from app.db.session import Base


class Device(Base):
    """An Android device registered for future SMS sending.

    Phase 1 only stores registration metadata. No actual connectivity,
    battery or SIM data is fabricated - those fields are added in Phase 2
    when the Android companion app reports them via the heartbeat API.
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
    last_seen: Mapped[datetime | None] = utc_datetime_column(nullable=True)
    created_at: Mapped[datetime] = utc_datetime_column()
    updated_at: Mapped[datetime] = utc_datetime_column(onupdate=utcnow)

    __table_args__ = (
        # A device identifier is unique per user.
        Index("uq_device_user_identifier", "user_id", "device_identifier", unique=True),
    )
