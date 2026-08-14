"""Dashboard statistics computed from real database records only."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    AuditLog,
    Campaign,
    CampaignRecipient,
    Contact,
    Device,
    MessageLog,
    MessageTemplate,
    OptOut,
    User,
)
from app.schemas.dashboard import (
    DashboardResponse,
    DashboardStats,
    DeviceStatusCard,
    RecentActivity,
    RecentCampaign,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardResponse)
def dashboard_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = user.id

    total_contacts = db.scalar(
        select(func.count()).select_from(Contact).where(Contact.user_id == uid)
    ) or 0
    active_campaigns = db.scalar(
        select(func.count())
        .select_from(Campaign)
        .where(Campaign.user_id == uid, Campaign.status.in_(["READY", "SCHEDULED", "RUNNING", "PAUSED"]))
    ) or 0
    messages_sent = db.scalar(
        select(func.count())
        .select_from(MessageLog)
        .where(MessageLog.user_id == uid, MessageLog.status == "SENT")
    ) or 0
    failed_messages = db.scalar(
        select(func.count())
        .select_from(MessageLog)
        .where(MessageLog.user_id == uid, MessageLog.status == "FAILED")
    ) or 0
    opt_outs = db.scalar(
        select(func.count()).select_from(OptOut).where(OptOut.user_id == uid)
    ) or 0
    connected_devices = db.scalar(
        select(func.count())
        .select_from(Device)
        .where(Device.user_id == uid, Device.connection_status == "CONNECTED")
    ) or 0
    total_campaigns = db.scalar(
        select(func.count()).select_from(Campaign).where(Campaign.user_id == uid)
    ) or 0
    total_templates = db.scalar(
        select(func.count()).select_from(MessageTemplate).where(MessageTemplate.user_id == uid)
    ) or 0

    recent_campaigns = db.scalars(
        select(Campaign)
        .where(Campaign.user_id == uid)
        .order_by(Campaign.created_at.desc())
        .limit(5)
    ).all()
    recent_activity = db.scalars(
        select(AuditLog)
        .where(AuditLog.user_id == uid)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    ).all()
    devices = db.scalars(
        select(Device).where(Device.user_id == uid).order_by(Device.created_at.desc())
    ).all()

    recipient_counts = dict(
        db.execute(
            select(Campaign.id, func.count())
            .select_from(Campaign)
            .join(
                CampaignRecipient,
                Campaign.id == CampaignRecipient.campaign_id,
            )
            .where(Campaign.user_id == uid)
            .group_by(Campaign.id)
        ).all()
    )

    return DashboardResponse(
        stats=DashboardStats(
            total_contacts=total_contacts,
            active_campaigns=active_campaigns,
            messages_sent=messages_sent,
            failed_messages=failed_messages,
            opt_outs=opt_outs,
            connected_devices=connected_devices,
            total_campaigns=total_campaigns,
            total_templates=total_templates,
        ),
        recent_campaigns=[
            RecentCampaign(
                id=c.id,
                name=c.name,
                status=c.status,
                recipient_count=recipient_counts.get(c.id, 0),
                created_at=c.created_at,
            )
            for c in recent_campaigns
        ],
        recent_activity=[
            RecentActivity(
                id=a.id,
                action=a.action,
                resource_type=a.resource_type,
                resource_id=a.resource_id,
                details=a.details or {},
                created_at=a.created_at,
            )
            for a in recent_activity
        ],
        devices=[
            DeviceStatusCard(
                id=d.id,
                device_name=d.device_name,
                platform=d.platform,
                connection_status=d.connection_status,
                last_seen=d.last_seen,
            )
            for d in devices
        ],
    )
