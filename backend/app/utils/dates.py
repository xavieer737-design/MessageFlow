"""Date helpers.

SQLite (used in tests) returns naive datetimes even for
DateTime(timezone=True) columns; PostgreSQL returns aware ones. These
helpers normalize so Python-side comparisons never break.
"""

from datetime import datetime, timezone


def ensure_utc(value: datetime | None) -> datetime | None:
    """Attach UTC tzinfo to naive datetimes (assumed to be UTC)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
