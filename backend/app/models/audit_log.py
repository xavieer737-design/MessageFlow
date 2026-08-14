from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.columns import utc_datetime_column
from app.db.session import Base


class AuditLog(Base):
    """Append-only audit trail of important user actions.

    Powers the dashboard "Recent Activity" feed and supports compliance
    requirements (who did what, when).
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    action: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_id: Mapped[int | None] = mapped_column()
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = utc_datetime_column()

    __table_args__ = (Index("ix_audit_user_created", "user_id", "created_at"),)
