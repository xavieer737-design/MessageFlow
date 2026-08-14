from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories.contact_repo import ContactRepository
from app.repositories.group_repo import GroupRepository
from app.schemas.group import (
    GroupAddContactsRequest,
    GroupCreate,
    GroupDetailOut,
    GroupOut,
    GroupRemoveContactsRequest,
    GroupUpdate,
)
from app.services.audit_service import log_action

router = APIRouter(prefix="/groups", tags=["groups"])


def _get_group_or_404(db: Session, user_id: int, group_id: int):
    group = GroupRepository(db).get(user_id, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@router.get("", response_model=list[GroupOut])
def list_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = GroupRepository(db)
    groups = repo.list(user.id)
    counts = repo.contact_count(user.id)
    return [
        GroupOut(
            id=g.id,
            user_id=g.user_id,
            name=g.name,
            description=g.description,
            created_at=g.created_at,
            contact_count=counts.get(g.id, 0),
        )
        for g in groups
    ]


@router.post("", response_model=GroupOut, status_code=201)
def create_group(
    payload: GroupCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = GroupRepository(db)
    existing = [g for g in repo.list(user.id) if g.name.lower() == payload.name.lower()]
    if existing:
        raise HTTPException(status_code=409, detail="A group with this name already exists")
    group = repo.create(user.id, payload.name.strip(), payload.description)
    log_action(db, user.id, "group.created", "group", group.id)
    db.commit()
    db.refresh(group)
    return GroupOut(
        id=group.id,
        user_id=group.user_id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        contact_count=0,
    )


@router.get("/{group_id}", response_model=GroupDetailOut)
def get_group(
    group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = _get_group_or_404(db, user.id, group_id)
    repo = GroupRepository(db)
    counts = repo.contact_count(user.id)
    return GroupDetailOut(
        id=group.id,
        user_id=group.user_id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        contact_count=counts.get(group.id, 0),
        contact_ids=repo.contact_ids(user.id, group.id),
    )


@router.put("/{group_id}", response_model=GroupOut)
def update_group(
    group_id: int,
    payload: GroupUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = _get_group_or_404(db, user.id, group_id)
    repo = GroupRepository(db)
    for other in repo.list(user.id):
        if other.id != group.id and other.name.lower() == payload.name.lower():
            raise HTTPException(status_code=409, detail="A group with this name already exists")
    group = repo.update(group, payload.name.strip(), payload.description)
    log_action(db, user.id, "group.updated", "group", group.id)
    db.commit()
    db.refresh(group)
    counts = repo.contact_count(user.id)
    return GroupOut(
        id=group.id,
        user_id=group.user_id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        contact_count=counts.get(group.id, 0),
    )


@router.delete("/{group_id}", status_code=204)
def delete_group(
    group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = _get_group_or_404(db, user.id, group_id)
    GroupRepository(db).delete(group)
    log_action(db, user.id, "group.deleted", "group", group_id)
    db.commit()


@router.post("/{group_id}/contacts", response_model=GroupDetailOut)
def add_contacts_to_group(
    group_id: int,
    payload: GroupAddContactsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = _get_group_or_404(db, user.id, group_id)
    contact_repo = ContactRepository(db)
    group_repo = GroupRepository(db)
    existing_ids = set(group_repo.contact_ids(user.id, group.id))
    for contact_id in payload.contact_ids:
        contact = contact_repo.get(user.id, contact_id)
        if contact and contact.id not in existing_ids:
            group.contacts.append(contact)
    db.flush()
    log_action(db, user.id, "group.contacts_added", "group", group.id, {"count": len(payload.contact_ids)})
    db.commit()
    db.refresh(group)
    counts = group_repo.contact_count(user.id)
    return GroupDetailOut(
        id=group.id,
        user_id=group.user_id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        contact_count=counts.get(group.id, 0),
        contact_ids=group_repo.contact_ids(user.id, group.id),
    )


@router.post("/{group_id}/contacts/remove", response_model=GroupDetailOut)
def remove_contacts_from_group(
    group_id: int,
    payload: GroupRemoveContactsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = _get_group_or_404(db, user.id, group_id)
    group_repo = GroupRepository(db)
    remove_ids = set(payload.contact_ids)
    group.contacts = [c for c in group.contacts if c.id not in remove_ids]
    db.flush()
    log_action(db, user.id, "group.contacts_removed", "group", group.id, {"count": len(remove_ids)})
    db.commit()
    db.refresh(group)
    counts = group_repo.contact_count(user.id)
    return GroupDetailOut(
        id=group.id,
        user_id=group.user_id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        contact_count=counts.get(group.id, 0),
        contact_ids=group_repo.contact_ids(user.id, group.id),
    )
