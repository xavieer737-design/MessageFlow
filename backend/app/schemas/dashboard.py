from datetime import datetime

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_contacts: int
    active_campaigns: int
    messages_sent: int
    failed_messages: int
    opt_outs: int
    connected_devices: int
    total_campaigns: int
    total_templates: int


class RecentCampaign(BaseModel):
    id: int
    name: str
    status: str
    recipient_count: int
    created_at: datetime


class RecentActivity(BaseModel):
    id: int
    action: str
    resource_type: str | None
    resource_id: int | None
    details: dict
    created_at: datetime


class DeviceStatusCard(BaseModel):
    id: int
    device_name: str
    platform: str
    connection_status: str
    last_seen: datetime | None


class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent_campaigns: list[RecentCampaign]
    recent_activity: list[RecentActivity]
    devices: list[DeviceStatusCard]
