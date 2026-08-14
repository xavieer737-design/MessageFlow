from __future__ import annotations
"""Repository layer: user-scoped data access.

Every repository method takes `user_id` so cross-user access is
impossible by construction - IDs are always scoped to the caller.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Contact, ContactGroup
from app.schemas.contact import ContactUpdate


class ContactRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int, contact_id: int) -> Contact | None:
        return self.db.scalar(
            select(Contact).where(Contact.id == contact_id, Contact.user_id == user_id)
        )

    def get_by_phone(self, user_id: int, phone: str) -> Contact | None:
        return self.db.scalar(
            select(Contact).where(Contact.user_id == user_id, Contact.phone == phone)
        )

    def list(
        self,
        user_id: int,
        search: str = "",
        group_id: int | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[Contact], int]:
        query = select(Contact).where(Contact.user_id == user_id)
        count_query = select(func.count()).select_from(Contact).where(Contact.user_id == user_id)

        if search:
            like = f"%{search}%"
            query = query.where(
                Contact.first_name.ilike(like)
                | Contact.last_name.ilike(like)
                | Contact.phone.ilike(like)
                | Contact.email.ilike(like)
                | Contact.company.ilike(like)
            )
            count_query = count_query.where(
                Contact.first_name.ilike(like)
                | Contact.last_name.ilike(like)
                | Contact.phone.ilike(like)
                | Contact.email.ilike(like)
                | Contact.company.ilike(like)
            )

        if group_id:
            query = query.join(contact_groups_table()).where(
                contact_groups_table().c.group_id == group_id
            )
            count_query = count_query.join(contact_groups_table()).where(
                contact_groups_table().c.group_id == group_id
            )

        column = {
            "created_at": Contact.created_at,
            "name": Contact.first_name,
            "phone": Contact.phone,
            "email": Contact.email,
            "company": Contact.company,
        }.get(sort_by, Contact.created_at)
        column = column.asc() if sort_dir == "asc" else column.desc()
        query = query.order_by(column, Contact.id.desc())

        total = self.db.scalar(count_query) or 0
        items = self.db.scalars(
            query.offset((page - 1) * page_size).limit(page_size)
        ).all()
        return list(items), total

    def create(
        self,
        user_id: int,
        phone: str,
        first_name=None,
        last_name=None,
        email=None,
        company=None,
        notes=None,
        custom_fields=None,
        group_ids=None,
    ) -> Contact:
        contact = Contact(
            user_id=user_id,
            phone=phone,
            first_name=first_name,
            last_name=last_name,
            email=email,
            company=company,
            notes=notes,
            custom_fields=custom_fields or {},
        )
        if group_ids:
            groups = self.db.scalars(
                select(ContactGroup).where(
                    ContactGroup.user_id == user_id, ContactGroup.id.in_(group_ids)
                )
            ).all()
            contact.groups = list(groups)
        self.db.add(contact)
        self.db.flush()
        return contact

    def update(self, user_id: int, contact: Contact, data: ContactUpdate) -> Contact:
        for field in ("phone", "first_name", "last_name", "email", "company", "notes", "custom_fields"):
            value = getattr(data, field)
            if value is not None or field in ("first_name", "last_name", "email", "company", "notes"):
                setattr(contact, field, value)
        if data.group_ids is not None:
            groups = (
                self.db.scalars(
                    select(ContactGroup).where(
                        ContactGroup.user_id == user_id, ContactGroup.id.in_(data.group_ids)
                    )
                ).all()
                if data.group_ids
                else []
            )
            contact.groups = list(groups)
        self.db.flush()
        return contact

    def delete(self, contact: Contact) -> None:
        self.db.delete(contact)
        self.db.flush()

    def count(self, user_id: int) -> int:
        return self.db.scalar(
            select(func.count()).select_from(Contact).where(Contact.user_id == user_id)
        ) or 0


def contact_groups_table():
    from app.models import contact_group_members

    return contact_group_members
