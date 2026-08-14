"""Background maintenance loops (Phase 2).

- dispatch loop: pushes the next batch of every ACTIVE send job to its
  connected device (server-controlled pacing/batching).
- offline sweep: marks devices OFFLINE after a heartbeat timeout and
  auto-pauses their send jobs.

Both loops use their own short-lived DB sessions; they are disabled in
tests via SEND_DISPATCH_ENABLED=false.
"""

import asyncio
import logging

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Device, SendJob
from app.services import send_service
from app.services.connection_manager import connection_manager

logger = logging.getLogger(__name__)

DISPATCH_INTERVAL_SECONDS = 2.0
SWEEP_INTERVAL_SECONDS = 10.0


async def _dispatch_loop() -> None:
    while True:
        await asyncio.sleep(DISPATCH_INTERVAL_SECONDS)
        try:
            db = SessionLocal()
            try:
                jobs = db.query(SendJob).filter(SendJob.status == "ACTIVE").all()
                for job in jobs:
                    device = db.get(Device, job.device_id)
                    if device and connection_manager.is_connected(device.id):
                        try:
                            send_service.dispatch_next_batch(db, job)
                            db.commit()
                        except Exception as exc:  # noqa: BLE001
                            db.rollback()
                            logger.exception("batch dispatch failed for job %s: %s", job.id, exc)
            finally:
                db.close()
        except Exception:  # noqa: BLE001
            logger.exception("dispatch loop error")


async def _offline_sweep_loop() -> None:
    while True:
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
        try:
            db = SessionLocal()
            try:
                send_service.sweep_offline_devices(db)
                db.commit()
            finally:
                db.close()
        except Exception:  # noqa: BLE001
            logger.exception("offline sweep error")


async def start_background_loops() -> None:
    if not settings.SEND_DISPATCH_ENABLED:
        logger.info("send dispatch loop disabled (SEND_DISPATCH_ENABLED=false)")
        return
    asyncio.create_task(_dispatch_loop())
    asyncio.create_task(_offline_sweep_loop())
    logger.info("background loops started (dispatch=%ss, sweep=%ss)",
                DISPATCH_INTERVAL_SECONDS, SWEEP_INTERVAL_SECONDS)
