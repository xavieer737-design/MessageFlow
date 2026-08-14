from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.columns import utc_datetime_column
from app.db.session import Base


class MessageLog(Base):
    """One entry per message created by a real application operation.

    In Phase 1 the only entries are SKIPPED/OPTED_OUT records produced by
    campaign validation and preparation. SENT/FAILED entries will only
    exist once a real Android device delivers messages (Phase 2).
    Nothing here is ever fabricated.
    """

    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"), index=True
    )
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    error: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = utc_datetime_column(nullable=True)
    created_at: Mapped[datetime] = utc_datetime_column()
