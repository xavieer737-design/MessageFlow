from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Campaign, Device, User
from app.repositories.campaign_repo import CampaignRepository
from app.repositories.device_repo import DeviceRepository
from app.schemas.campaign import (
    CampaignCreate,
    CampaignListOut,
    CampaignOut,
    CampaignProgressOut,
    CampaignSendOut,
    CampaignSendRequest,
    CampaignUpdate,
    CampaignValidationReport,
)
from app.services import campaign_service, send_service
from app.services.audit_service import log_action
from app.services.campaign_service import CampaignError
from app.services.send_service import SendError

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _get_campaign_or_404(db: Session, user_id: int, campaign_id: int) -> Campaign:
    campaign = CampaignRepository(db).get(user_id, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def _serialize_campaign(db: Session, campaign: Campaign) -> CampaignOut:
    summary = campaign_service.campaign_summary(db, campaign)
    return CampaignOut(
        id=campaign.id,
        user_id=campaign.user_id,
        name=campaign.name,
        message_template=campaign.message_template,
        status=campaign.status,
        scheduled_at=campaign.scheduled_at,
        recipient_scope=campaign.recipient_scope or "all",
        recipient_group_id=campaign.recipient_group_id,
        recipient_contact_ids=campaign.recipient_contact_ids or [],
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        **summary,
        recipients=campaign.recipients,
    )


@router.get("", response_model=CampaignListOut)
def list_campaigns(
    status: str | None = None,
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Campaign).where(Campaign.user_id == user.id)
    count_query = select(func.count()).select_from(Campaign).where(Campaign.user_id == user.id)
    if status:
        query = query.where(Campaign.status == status)
        count_query = count_query.where(Campaign.status == status)
    if search:
        like = f"%{search}%"
        query = query.where(Campaign.name.ilike(like))
        count_query = count_query.where(Campaign.name.ilike(like))
    total = db.scalar(count_query) or 0
    campaigns = db.scalars(
        query.order_by(Campaign.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    pages = max(1, -(-total // page_size))
    return {
        "items": [_serialize_campaign(db, c) for c in campaigns],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(
    payload: CampaignCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        campaign = campaign_service.create_campaign(
            db,
            user.id,
            payload.name.strip(),
            payload.message_template,
            payload.recipients,
            payload.status,
            payload.scheduled_at,
        )
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(db, campaign)


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campaign = _get_campaign_or_404(db, user.id, campaign_id)
    return _serialize_campaign(db, campaign)


@router.put("/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campaign = _get_campaign_or_404(db, user.id, campaign_id)
    try:
        campaign = campaign_service.update_campaign(
            db, user.id, campaign, payload.model_dump(exclude_unset=True)
        )
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(db, campaign)


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campaign = _get_campaign_or_404(db, user.id, campaign_id)
    db.delete(campaign)
    log_action(db, user.id, "campaign.deleted", "campaign", campaign_id)
    db.commit()


@router.post("/{campaign_id}/validate", response_model=CampaignValidationReport)
def validate_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campaign = _get_campaign_or_404(db, user.id, campaign_id)
    try:
        report = campaign_service.build_validation_report(db, user.id, campaign)
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    return report


@router.post("/{campaign_id}/ready", response_model=CampaignOut)
def mark_ready(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campaign = _get_campaign_or_404(db, user.id, campaign_id)
    try:
        campaign = campaign_service.mark_ready(db, user.id, campaign)
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(db, campaign)


@router.post("/{campaign_id}/duplicate", response_model=CampaignOut, status_code=201)
def duplicate_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campaign = _get_campaign_or_404(db, user.id, campaign_id)
    try:
        copy = campaign_service.duplicate_campaign(db, user.id, campaign)
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    db.refresh(copy)
    return _serialize_campaign(db, copy)


@router.post("/{campaign_id}/pause", response_model=CampaignOut)
def pause_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campaign = _get_campaign_or_404(db, user.id, campaign_id)
    try:
        campaign = campaign_service.pause_campaign(db, user.id, campaign)
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(db, campaign)


@router.post("/{campaign_id}/resume", response_model=CampaignOut)
def resume_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campaign = _get_campaign_or_404(db, user.id, campaign_id)
    try:
        campaign = campaign_service.resume_campaign(db, user.id, campaign)
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(db, campaign)


@router.post("/{campaign_id}/cancel", response_model=CampaignOut)
def cancel_campaign(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campaign = _get_campaign_or_404(db, user.id, campaign_id)
    try:
        campaign = campaign_service.cancel_campaign(db, user.id, campaign)
        if campaign.status == "CANCELLED":
            # Cancel any in-flight send job too - no new messages.
            send_service.cancel_send_job(db, user.id, campaign)
    except CampaignError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(db, campaign)


# --- Sending (Phase 2) ---


@router.post("/{campaign_id}/send", response_model=CampaignSendOut, status_code=202)
def send_campaign(
    campaign_id: int,
    payload: CampaignSendRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start sending a READY campaign through a connected device.

    Opt-outs are re-checked at this moment, a send queue is created, and
    the first batch is dispatched to the device. Results arrive
    asynchronously and are recorded only when the device reports them.
    """
    campaign = _get_campaign_or_404(db, user.id, campaign_id)
    device = DeviceRepository(db).get(user.id, payload.device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    try:
        job, counts = send_service.start_campaign_send(db, user.id, campaign, device)
        dispatched = send_service.dispatch_next_batch(db, job)
    except SendError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    db.refresh(job)
    return CampaignSendOut(
        job_id=job.id,
        campaign_id=campaign.id,
        device_id=device.id,
        status=job.status,
        queued=counts["queued"],
        skipped_opted_out=counts["skipped_opted_out"],
        skipped_invalid=counts["skipped_invalid"],
        message=(
            f"Campaign queued on {device.device_name}: {counts['queued']} message(s). "
            f"First batch dispatched: {dispatched}."
        ),
    )


@router.get("/{campaign_id}/progress", response_model=CampaignProgressOut)
def campaign_progress(
    campaign_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Real-time progress of a campaign send (polled by the dashboard)."""
    campaign = _get_campaign_or_404(db, user.id, campaign_id)
    return CampaignProgressOut(**send_service.campaign_progress(db, user.id, campaign))
