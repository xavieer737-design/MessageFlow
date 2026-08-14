from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.columns import utc_datetime_column, utcnow
from app.db.session import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # Raw message text with template variables, e.g. "Hi {{first_name}} ..."
    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True, nullable=False)
    scheduled_at: Mapped[datetime | None] = utc_datetime_column(nullable=True)
    # Recipient selection: all | group | contacts
    recipient_scope: Mapped[str] = mapped_column(String(20), default="all", nullable=False)
    recipient_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("contact_groups.id", ondelete="SET NULL")
    )
    recipient_contact_ids: Mapped[list[int] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = utc_datetime_column()
    updated_at: Mapped[datetime] = utc_datetime_column(onupdate=utcnow)

    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", lazy="selectin"
    )


class CampaignRecipient(Base):
    __tablename__ = "campaign_recipients"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True, nullable=False
    )
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    # The personalized message generated for this specific recipient.
    personalized_message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True, nullable=False)
    # Reason when SKIPPED / OPTED_OUT / FAILED (e.g. "invalid phone", "opted out").
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = utc_datetime_column()
    updated_at: Mapped[datetime] = utc_datetime_column(onupdate=utcnow)

    campaign: Mapped[Campaign] = relationship(back_populates="recipients")
