"""Aggregate all API routers."""

from fastapi import APIRouter

from app.api.routes import (
    auth,
    campaigns,
    contacts,
    dashboard,
    devices,
    devices_ws,
    groups,
    messages,
    optouts,
    templates,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(contacts.router)
api_router.include_router(groups.router)
api_router.include_router(templates.router)
api_router.include_router(campaigns.router)
api_router.include_router(devices.router)
api_router.include_router(devices_ws.router)
api_router.include_router(messages.router)
api_router.include_router(optouts.router)
api_router.include_router(dashboard.router)
