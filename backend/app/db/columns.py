"""Shared SQLAlchemy column/type helpers."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utc_datetime_column(**kwargs) -> Mapped[datetime]:
    """A timezone-aware UTC datetime column with server default now().

    Returns a ready-to-assign MappedColumn, e.g.::

        created_at: Mapped[datetime] = utc_datetime_column()

    Nullable columns (e.g. last_seen) do not get an auto default.
    """
    if not kwargs.get("nullable", False):
        kwargs.setdefault("default", utcnow)
        kwargs.setdefault("server_default", func.now())
    kwargs.setdefault("nullable", False)
    return mapped_column(DateTime(timezone=True), **kwargs)
