from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, String, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.columns import utc_datetime_column, utcnow
from app.db.session import Base

# Many-to-many association between contacts and groups.
contact_group_members = Table(
    "contact_group_members",
    Base.metadata,
    Column("contact_id", ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", ForeignKey("contact_groups.id", ondelete="CASCADE"), primary_key=True),
)


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(2000))
    # Free-form key/value extra fields, e.g. {"city": "Mumbai"}
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = utc_datetime_column()
    updated_at: Mapped[datetime] = utc_datetime_column(onupdate=utcnow)

    groups: Mapped[list["ContactGroup"]] = relationship(
        secondary=contact_group_members, back_populates="contacts", lazy="selectin"
    )

    __table_args__ = (
        # A phone number must be unique within one user's address book.
        Index("uq_contact_user_phone", "user_id", "phone", unique=True),
        Index("ix_contact_user_name", "user_id", "first_name", "last_name"),
    )


class ContactGroup(Base):
    __tablename__ = "contact_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = utc_datetime_column()

    contacts: Mapped[list[Contact]] = relationship(
        secondary=contact_group_members, back_populates="groups", lazy="selectin"
    )

    __table_args__ = (Index("uq_group_user_name", "user_id", "name", unique=True),)
