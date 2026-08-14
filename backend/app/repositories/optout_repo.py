from __future__ import annotations
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import OptOut


class OptOutRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int, optout_id: int) -> OptOut | None:
        return self.db.scalar(
            select(OptOut).where(OptOut.id == optout_id, OptOut.user_id == user_id)
        )

    def get_by_phone(self, user_id: int, phone: str) -> OptOut | None:
        return self.db.scalar(
            select(OptOut).where(OptOut.user_id == user_id, OptOut.phone == phone)
        )

    def list(self, user_id: int, search: str = "", page: int = 1, page_size: int = 25):
        query = select(OptOut).where(OptOut.user_id == user_id)
        count_query = select(func.count()).select_from(OptOut).where(OptOut.user_id == user_id)
        if search:
            like = f"%{search}%"
            query = query.where(OptOut.phone.ilike(like))
            count_query = count_query.where(OptOut.phone.ilike(like))
        total = self.db.scalar(count_query) or 0
        items = self.db.scalars(
            query.order_by(OptOut.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return list(items), total

    def create(self, user_id: int, phone: str, reason: str | None = None) -> OptOut:
        entry = OptOut(user_id=user_id, phone=phone, reason=reason)
        self.db.add(entry)
        self.db.flush()
        return entry

    def delete(self, entry: OptOut) -> None:
        self.db.delete(entry)
        self.db.flush()

    def count(self, user_id: int) -> int:
        return self.db.scalar(
            select(func.count()).select_from(OptOut).where(OptOut.user_id == user_id)
        ) or 0
