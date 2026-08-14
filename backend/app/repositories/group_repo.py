from __future__ import annotations
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ContactGroup, contact_group_members


class GroupRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int, group_id: int) -> ContactGroup | None:
        return self.db.scalar(
            select(ContactGroup).where(
                ContactGroup.id == group_id, ContactGroup.user_id == user_id
            )
        )

    def list(self, user_id: int) -> list[ContactGroup]:
        return list(
            self.db.scalars(
                select(ContactGroup)
                .where(ContactGroup.user_id == user_id)
                .order_by(ContactGroup.name.asc())
            ).all()
        )

    def create(self, user_id: int, name: str, description: str | None = None) -> ContactGroup:
        group = ContactGroup(user_id=user_id, name=name, description=description)
        self.db.add(group)
        self.db.flush()
        return group

    def update(self, group: ContactGroup, name: str, description: str | None) -> ContactGroup:
        group.name = name
        group.description = description
        self.db.flush()
        return group

    def delete(self, group: ContactGroup) -> None:
        self.db.delete(group)
        self.db.flush()

    def contact_count(self, user_id: int) -> dict[int, int]:
        rows = self.db.execute(
            select(contact_group_members.c.group_id, func.count())
            .join(ContactGroup, ContactGroup.id == contact_group_members.c.group_id)
            .where(ContactGroup.user_id == user_id)
            .group_by(contact_group_members.c.group_id)
        ).all()
        return {gid: n for gid, n in rows}

    def contact_ids(self, user_id: int, group_id: int) -> list[int]:
        return list(
            self.db.scalars(
                select(contact_group_members.c.contact_id).where(
                    contact_group_members.c.group_id == group_id
                )
            ).all()
        )
