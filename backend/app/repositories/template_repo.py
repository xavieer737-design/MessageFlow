from __future__ import annotations
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MessageTemplate


class TemplateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int, template_id: int) -> MessageTemplate | None:
        return self.db.scalar(
            select(MessageTemplate).where(
                MessageTemplate.id == template_id, MessageTemplate.user_id == user_id
            )
        )

    def list(self, user_id: int) -> list[MessageTemplate]:
        return list(
            self.db.scalars(
                select(MessageTemplate)
                .where(MessageTemplate.user_id == user_id)
                .order_by(MessageTemplate.created_at.desc())
            ).all()
        )

    def create(self, user_id: int, name: str, message: str) -> MessageTemplate:
        template = MessageTemplate(user_id=user_id, name=name, message=message)
        self.db.add(template)
        self.db.flush()
        return template

    def update(self, template: MessageTemplate, name: str, message: str) -> MessageTemplate:
        template.name = name
        template.message = message
        self.db.flush()
        return template

    def delete(self, template: MessageTemplate) -> None:
        self.db.delete(template)
        self.db.flush()

    def count(self, user_id: int) -> int:
        return self.db.scalar(
            select(func.count()).select_from(MessageTemplate).where(MessageTemplate.user_id == user_id)
        ) or 0
