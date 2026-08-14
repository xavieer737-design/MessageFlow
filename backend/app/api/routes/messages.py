from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Campaign, Contact, Device, MessageLog, User
from app.schemas.message import MessageLogListOut

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=MessageLogListOut)
def list_messages(
    status: str | None = Query(default=None),
    campaign_id: int | None = None,
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(MessageLog).where(MessageLog.user_id == user.id)
    count_query = select(func.count()).select_from(MessageLog).where(MessageLog.user_id == user.id)

    if status:
        query = query.where(MessageLog.status == status)
        count_query = count_query.where(MessageLog.status == status)
    if campaign_id:
        query = query.where(MessageLog.campaign_id == campaign_id)
        count_query = count_query.where(MessageLog.campaign_id == campaign_id)

    logs = db.scalars(
        query.order_by(MessageLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    campaign_ids = {log.campaign_id for log in logs if log.campaign_id}
    contact_ids = {log.contact_id for log in logs if log.contact_id}
    device_ids = {log.device_id for log in logs if log.device_id}

    campaign_names = dict(
        db.execute(select(Campaign.id, Campaign.name).where(Campaign.id.in_(campaign_ids))).all()
    ) if campaign_ids else {}
    contact_info = {
        cid: (name, phone)
        for cid, name, phone in db.execute(
            select(
                Contact.id,
                func.coalesce(Contact.first_name, ""),
                Contact.phone,
            ).where(Contact.id.in_(contact_ids))
        ).all()
    } if contact_ids else {}
    device_names = dict(
        db.execute(select(Device.id, Device.device_name).where(Device.id.in_(device_ids))).all()
    ) if device_ids else {}

    total = db.scalar(count_query) or 0
    pages = max(1, -(-total // page_size))

    items = []
    for log in logs:
        name, phone = contact_info.get(log.contact_id, ("", ""))
        items.append(
            {
                "id": log.id,
                "user_id": log.user_id,
                "campaign_id": log.campaign_id,
                "contact_id": log.contact_id,
                "device_id": log.device_id,
                "message": log.message,
                "status": log.status,
                "error": log.error,
                "sent_at": log.sent_at,
                "created_at": log.created_at,
                "campaign_name": campaign_names.get(log.campaign_id),
                "contact_name": name or None,
                "phone": phone or None,
                "device_name": device_names.get(log.device_id),
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }
