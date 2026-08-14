from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.columns import utc_datetime_column
from app.db.session import Base


class OptOut(Base):
    """Numbers the user must never message (consent-based anti-spam)."""

    __tablename__ = "opt_outs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Stored in normalized E.164 form, e.g. +919876543210
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = utc_datetime_column()

    __table_args__ = (
        Index("uq_optout_user_phone", "user_id", "phone", unique=True),
    )
