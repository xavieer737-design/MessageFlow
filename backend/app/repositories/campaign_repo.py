from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Campaign


class CampaignRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int, campaign_id: int) -> Campaign | None:
        return self.db.scalar(
            select(Campaign).where(
                Campaign.id == campaign_id, Campaign.user_id == user_id
            )
        )

    def list(self, user_id: int) -> list[Campaign]:
        return list(
            self.db.scalars(
                select(Campaign)
                .where(Campaign.user_id == user_id)
                .order_by(Campaign.created_at.desc())
            ).all()
        )

    def count(self, user_id: int) -> int:
        from sqlalchemy import func

        return self.db.scalar(
            select(func.count()).select_from(Campaign).where(Campaign.user_id == user_id)
        ) or 0

    def active_count(self, user_id: int) -> int:
        from sqlalchemy import func

        return self.db.scalar(
            select(func.count())
            .select_from(Campaign)
            .where(
                Campaign.user_id == user_id,
                Campaign.status.in_(["READY", "SCHEDULED", "RUNNING", "PAUSED"]),
            )
        ) or 0
