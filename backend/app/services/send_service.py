"""Campaign send engine (Phase 2).

Server-controlled queueing:
- READY campaigns can be started on a paired, connected device.
- Opt-outs are re-checked immediately before each batch is dispatched -
  never trusting the state from validation time.
- Recipients are dispatched in small configurable batches; pacing honors
  the configured rate (messages/minute).
- Nothing is marked SENT unless the Android device reports SmsManager
  success (MessageAttempt.status = SEND_SUCCESS).
- Idempotency: every logical message has a stable idempotency_key and a
  unique message_id per attempt. Results are replayed, never re-sent.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Campaign,
    CampaignRecipient,
    Device,
    MessageAttempt,
    MessageLog,
    OptOut,
    SendJob,
)
from app.services.audit_service import log_action
from app.services.connection_manager import connection_manager
from app.services.phone_service import normalize_phone


class SendError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


TERMINAL_ATTEMPT_STATUSES = {"SEND_SUCCESS", "SEND_FAILED", "SKIPPED", "OPTED_OUT"}
TERMINAL_RECIPIENT_STATUSES = {"SENT", "FAILED", "SKIPPED", "OPTED_OUT"}
# PROCESSING is included so that after a reconnect, commands whose result
# was lost in transit are re-issued. The Android device's idempotency
# store guarantees they are never sent twice (previous result is replayed).
SENDABLE_RECIPIENT_STATUSES = {"PENDING", "QUEUED", "PROCESSING"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _opt_out_phones(db: Session, user_id: int) -> set[str]:
    return set(db.scalars(select(OptOut.phone).where(OptOut.user_id == user_id)).all())


# ---------------------------------------------------------------- start


def start_campaign_send(
    db: Session, user_id: int, campaign: Campaign, device: Device
) -> tuple[SendJob, dict]:
    """Start sending a READY campaign through a connected device.

    Re-checks opt-outs and phone validity right now, creates the send
    queue (SendJob + MessageAttempt rows + message ids), marks the
    campaign RUNNING and dispatches the first batch.
    """
    if campaign.user_id != user_id:
        raise SendError("Campaign not found.", 404)
    if campaign.status != "READY":
        raise SendError(f"Cannot send a campaign in status {campaign.status}.", 409)
    if device.user_id != user_id:
        raise SendError("Device not found.", 404)
    if not device.paired_at:
        raise SendError("Device is not paired.", 409)

    existing_job = db.scalar(
        select(SendJob).where(SendJob.campaign_id == campaign.id)
    )
    if existing_job:
        raise SendError("This campaign already has a send job.", 409)

    opt_outs = _opt_out_phones(db, user_id)

    job = SendJob(
        user_id=user_id,
        campaign_id=campaign.id,
        device_id=device.id,
        status="ACTIVE",
        batch_size=settings.SEND_BATCH_SIZE,
        rate_per_minute=settings.SEND_RATE_PER_MINUTE,
        total_recipients=0,
    )
    db.add(job)
    db.flush()

    queued = 0
    opted_out = 0
    invalid = 0
    recipients = db.scalars(
        select(CampaignRecipient).where(
            CampaignRecipient.campaign_id == campaign.id,
            CampaignRecipient.status.in_(SENDABLE_RECIPIENT_STATUSES),
        )
    ).all()

    for recipient in recipients:
        phone_result = normalize_phone(recipient.contact.phone if recipient.contact else "")
        if not phone_result.valid:
            recipient.status = "SKIPPED"
            recipient.error = "invalid phone number at send time"
            invalid += 1
            continue
        if phone_result.normalized in opt_outs:
            recipient.status = "OPTED_OUT"
            recipient.error = "opted out (re-checked at send time)"
            opted_out += 1
            continue

        message_id = str(uuid.uuid4())
        recipient.message_id = message_id
        recipient.status = "QUEUED"
        recipient.queued_at = _now()
        recipient.attempt_count = 0
        attempt = MessageAttempt(
            user_id=user_id,
            campaign_id=campaign.id,
            recipient_id=recipient.id,
            contact_id=recipient.contact_id,
            device_id=device.id,
            phone=phone_result.normalized,
            message=recipient.personalized_message or "",
            message_id=message_id,
            idempotency_key=f"c{campaign.id}:r{recipient.id}",
            status="PENDING",
            attempt_number=1,
        )
        db.add(attempt)
        queued += 1

    job.total_recipients = queued
    campaign.status = "RUNNING"

    log_action(
        db,
        user_id,
        "campaign.sent",
        "campaign",
        campaign.id,
        {"device_id": device.id, "queued": queued, "opted_out": opted_out},
    )
    db.flush()
    return job, {
        "queued": queued,
        "skipped_opted_out": opted_out,
        "skipped_invalid": invalid,
    }


# ---------------------------------------------------------------- dispatch


def dispatch_next_batch(db: Session, job: SendJob) -> int:
    """Dispatch the next batch of recipients to the device.

    Returns the number of commands dispatched. Respects job status
    (ACTIVE only), device connectivity, batch size and per-minute pacing.
    """
    if job.status != "ACTIVE":
        return 0

    device = db.get(Device, job.device_id)
    if not device or not connection_manager.is_connected(device.id):
        return 0

    campaign = db.get(Campaign, job.campaign_id)
    if not campaign or campaign.status != "RUNNING":
        return 0

    # Re-check opt-outs immediately before dispatch (never stale).
    opt_outs = _opt_out_phones(db, job.user_id)

    recipients = db.scalars(
        select(CampaignRecipient)
        .where(
            CampaignRecipient.campaign_id == job.campaign_id,
            CampaignRecipient.status.in_(SENDABLE_RECIPIENT_STATUSES),
        )
        .order_by(CampaignRecipient.id.asc())
        .limit(job.batch_size)
    ).all()

    dispatched = 0
    interval = 60.0 / max(1, job.rate_per_minute)
    now = _now()

    for index, recipient in enumerate(recipients):
        if not connection_manager.is_connected(device.id):
            break

        phone_result = normalize_phone(recipient.contact.phone if recipient.contact else "")
        if not phone_result.valid:
            recipient.status = "SKIPPED"
            recipient.error = "invalid phone number at send time"
            continue
        if phone_result.normalized in opt_outs:
            recipient.status = "OPTED_OUT"
            recipient.error = "opted out (re-checked at send time)"
            continue

        # Idempotency: if this logical message already succeeded, skip.
        prior = db.scalar(
            select(MessageAttempt).where(
                MessageAttempt.idempotency_key == f"c{job.campaign_id}:r{recipient.id}",
                MessageAttempt.status == "SEND_SUCCESS",
            )
        )
        if prior:
            recipient.status = "SENT"
            recipient.sent_at = prior.sent_at or now
            continue

        attempt = db.scalar(
            select(MessageAttempt).where(
                MessageAttempt.campaign_id == job.campaign_id,
                MessageAttempt.recipient_id == recipient.id,
            )
        )
        if attempt is None:
            attempt = MessageAttempt(
                user_id=job.user_id,
                campaign_id=job.campaign_id,
                recipient_id=recipient.id,
                contact_id=recipient.contact_id,
                device_id=device.id,
                phone=phone_result.normalized,
                message=recipient.personalized_message or "",
                message_id=recipient.message_id or str(uuid.uuid4()),
                idempotency_key=f"c{job.campaign_id}:r{recipient.id}",
                status="PENDING",
                attempt_number=recipient.attempt_count + 1,
            )
            db.add(attempt)
            db.flush()
        else:
            # A retry (e.g. after reconnect with a lost result). The same
            # message_id is kept so the device can replay its stored result.
            attempt.status = "PENDING"
            attempt.device_id = device.id
            attempt.attempt_number = recipient.attempt_count + 1

        recipient.attempt_count = recipient.attempt_count + 1
        if recipient.status == "PROCESSING":
            recipient.status = "QUEUED"  # being re-issued after reconnect

        message_id = attempt.message_id
        recipient.message_id = message_id

        send_at = now + timedelta(seconds=interval * index)
        command = {
            "type": "send_message",
            "command_id": str(uuid.uuid4()),
            "message_id": message_id,
            "idempotency_key": attempt.idempotency_key,
            "phone": phone_result.normalized,
            "message": attempt.message,
            "send_at": send_at.isoformat(),
        }
        delivered = await_send(device.id, command)
        if not delivered:
            # Device dropped between check and send: revert and stop.
            attempt.status = "PENDING"
            recipient.attempt_count = recipient.attempt_count - 1
            db.flush()
            mark_device_offline(db, device)
            break

        attempt.status = "SEND_REQUESTED"
        recipient.status = "PROCESSING"
        dispatched += 1
        db.flush()

    return dispatched


def await_send(device_id: int, payload: dict) -> bool:
    """Synchronous-friendly send used from sync service code.

    Runs the async send on the running event loop when available, falling
    back to a direct registry lookup. FastAPI sync endpoints run in a
    threadpool, so we use asyncio.run_coroutine_threadsafe when a loop is
    running; otherwise we call the manager directly (tests).
    """
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(
            connection_manager.send_to_device(device_id, payload), loop
        )
        return future.result(timeout=10)
    return asyncio.run(connection_manager.send_to_device(device_id, payload))


# ---------------------------------------------------------------- results


def handle_message_result(
    db: Session,
    user_id: int,
    device: Device,
    message_id: str,
    status: str,
    error: str | None = None,
    device_timestamp: str | None = None,
) -> MessageAttempt | None:
    """Process a MESSAGE_RESULT from the Android device.

    Idempotent: a result for a message that already reached a terminal
    state is recorded but never changes the outcome.
    """
    attempt = db.scalar(
        select(MessageAttempt).where(
            MessageAttempt.message_id == message_id,
            MessageAttempt.user_id == user_id,
            MessageAttempt.device_id == device.id,
        )
    )
    if not attempt:
        return None

    now = _now()
    if attempt.status in TERMINAL_ATTEMPT_STATUSES:
        # Idempotent replay: keep the original result.
        log_action(
            db, user_id, "send.duplicate_result_ignored", "message_attempt", attempt.id,
            {"message_id": message_id, "status": status},
        )
        return attempt

    if status == "SEND_SUCCESS":
        attempt.status = "SEND_SUCCESS"
        attempt.error = None
        attempt.sent_at = now
        attempt.device_timestamp = device_timestamp
        if attempt.recipient_id:
            db.execute(
                update(CampaignRecipient)
                .where(CampaignRecipient.id == attempt.recipient_id)
                .values(status="SENT", sent_at=now, error=None)
            )
        if attempt.campaign_id:
            db.add(
                MessageLog(
                    user_id=user_id,
                    campaign_id=attempt.campaign_id,
                    contact_id=attempt.contact_id,
                    device_id=device.id,
                    message=attempt.message,
                    status="SENT",
                    sent_at=now,
                )
            )
    elif status == "SEND_FAILED":
        attempt.status = "SEND_FAILED"
        attempt.error = error or "device reported failure"
        attempt.device_timestamp = device_timestamp
        if attempt.recipient_id:
            db.execute(
                update(CampaignRecipient)
                .where(CampaignRecipient.id == attempt.recipient_id)
                .values(status="FAILED", error=attempt.error)
            )
        if attempt.campaign_id:
            db.add(
                MessageLog(
                    user_id=user_id,
                    campaign_id=attempt.campaign_id,
                    contact_id=attempt.contact_id,
                    device_id=device.id,
                    message=attempt.message,
                    status="FAILED",
                    error=attempt.error,
                )
            )
    else:
        return attempt

    db.flush()
    log_action(
        db, user_id, "send.result", "message_attempt", attempt.id,
        {"message_id": message_id, "status": attempt.status},
    )

    # Job completion check.
    if attempt.campaign_id:
        _maybe_complete_job(db, user_id, attempt.campaign_id, device.id)
    return attempt


def _maybe_complete_job(db: Session, user_id: int, campaign_id: int, device_id: int) -> None:
    job = db.scalar(
        select(SendJob).where(
            SendJob.campaign_id == campaign_id, SendJob.device_id == device_id
        )
    )
    campaign = db.get(Campaign, campaign_id)
    if not job or not campaign:
        return
    if job.status not in ("ACTIVE", "PAUSED"):
        return

    from sqlalchemy import func

    pending = db.scalar(
        select(func.count())
        .select_from(CampaignRecipient)
        .where(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.status.in_(("PENDING", "QUEUED", "PROCESSING")),
        )
    )
    if pending:
        return

    job.status = "COMPLETED"
    job.completed_at = _now()
    if campaign.status == "RUNNING":
        campaign.status = "COMPLETED"
    log_action(db, user_id, "campaign.completed", "campaign", campaign_id)
    db.flush()


# ---------------------------------------------------------------- pause/resume/cancel


def pause_send_job(db: Session, user_id: int, campaign: Campaign) -> SendJob | None:
    """Pause the send job for a campaign. Returns None when no job exists."""
    job = db.scalar(select(SendJob).where(SendJob.campaign_id == campaign.id))
    if not job or job.user_id != user_id:
        return None
    if job.status != "ACTIVE":
        raise SendError(f"Cannot pause a job in status {job.status}.", 409)
    job.status = "PAUSED"
    # Tell the device to stop dispatching further sends from its queue.
    await_send(job.device_id, {"type": "pause", "command_id": str(uuid.uuid4())})
    db.flush()
    return job


def resume_send_job(db: Session, user_id: int, campaign: Campaign) -> SendJob | None:
    """Resume the send job for a campaign. Returns None when no job exists."""
    job = db.scalar(select(SendJob).where(SendJob.campaign_id == campaign.id))
    if not job or job.user_id != user_id:
        return None
    if job.status != "PAUSED":
        raise SendError(f"Cannot resume a job in status {job.status}.", 409)
    job.status = "ACTIVE"
    await_send(job.device_id, {"type": "resume", "command_id": str(uuid.uuid4())})
    db.flush()
    return job


def cancel_send_job(db: Session, user_id: int, campaign: Campaign) -> SendJob | None:
    """Cancel the send job for a campaign. Returns None when no job exists.

    Already-dispatched commands may still complete on the device; the
    results are recorded, but no new commands are issued.
    """
    job = db.scalar(select(SendJob).where(SendJob.campaign_id == campaign.id))
    if not job or job.user_id != user_id:
        return None
    if job.status in ("COMPLETED", "CANCELLED"):
        return job
    job.status = "CANCELLED"
    job.completed_at = _now()
    # No new messages: tell the device to drop queued work.
    await_send(job.device_id, {"type": "cancel", "command_id": str(uuid.uuid4())})
    db.flush()
    return job


# ---------------------------------------------------------------- progress


def campaign_progress(db: Session, user_id: int, campaign: Campaign) -> dict:
    rows = db.execute(
        select(CampaignRecipient.status, CampaignRecipient.id)
        .where(CampaignRecipient.campaign_id == campaign.id)
    ).all()
    counts = {
        "pending": 0, "queued": 0, "processing": 0, "sent": 0,
        "failed": 0, "skipped": 0, "opted_out": 0,
    }
    for status, _ in rows:
        key = status.lower() if status.lower() in counts else "pending"
        counts[key] += 1

    job = db.scalar(select(SendJob).where(SendJob.campaign_id == campaign.id))
    device = db.get(Device, job.device_id) if job else None

    total = len(rows)
    terminal = counts["sent"] + counts["failed"] + counts["skipped"] + counts["opted_out"]
    return {
        "campaign_id": campaign.id,
        "campaign_status": campaign.status,
        "job_status": job.status if job else None,
        "device_id": device.id if device else None,
        "device_name": device.device_name if device else None,
        "device_connection_status": device.connection_status if device else None,
        "total": total,
        "progress": round(terminal / total, 4) if total else 0.0,
        **counts,
    }


# ---------------------------------------------------------------- test messages


def send_test_message(
    db: Session, user_id: int, device: Device, phone: str, message: str
) -> MessageAttempt:
    """Send a single test SMS through the device.

    Requires the device to be paired and currently connected; the result
    is delivered asynchronously via MESSAGE_RESULT. Never faked.
    """
    if device.user_id != user_id:
        raise SendError("Device not found.", 404)
    if not device.paired_at:
        raise SendError("Device is not paired.", 409)
    if not connection_manager.is_connected(device.id):
        raise SendError(
            "Device is not connected right now. Reconnect it before sending a test message.", 409
        )

    phone_result = normalize_phone(phone)
    if not phone_result.valid:
        raise SendError(f"Invalid phone number: {phone_result.reason}", 422)

    if not message.strip():
        raise SendError("Message cannot be empty.", 422)

    message_id = str(uuid.uuid4())
    attempt = MessageAttempt(
        user_id=user_id,
        campaign_id=None,
        recipient_id=None,
        contact_id=None,
        device_id=device.id,
        phone=phone_result.normalized,
        message=message,
        message_id=message_id,
        idempotency_key=f"test:{message_id}",
        status="PENDING",
        attempt_number=1,
    )
    db.add(attempt)
    db.flush()

    command = {
        "type": "send_message",
        "command_id": str(uuid.uuid4()),
        "message_id": message_id,
        "idempotency_key": attempt.idempotency_key,
        "phone": phone_result.normalized,
        "message": message,
        "send_at": _now().isoformat(),
        "test": True,
    }
    if not await_send(device.id, command):
        attempt.status = "PENDING"
        db.flush()
        mark_device_offline(db, device)
        raise SendError("Could not deliver the command to the device. It may have disconnected.", 409)

    attempt.status = "SEND_REQUESTED"
    log_action(db, user_id, "device.test_message", "device", device.id, {"message_id": message_id})
    db.flush()
    return attempt


def test_message_result(db: Session, user_id: int, device_id: int, message_id: str) -> MessageAttempt | None:
    return db.scalar(
        select(MessageAttempt).where(
            MessageAttempt.message_id == message_id,
            MessageAttempt.user_id == user_id,
            MessageAttempt.device_id == device_id,
            MessageAttempt.campaign_id.is_(None),
        )
    )


# ---------------------------------------------------------------- STOP keywords


def handle_incoming_sms(
    db: Session, device: Device, sender: str, body: str, received_at: str | None = None
) -> dict:
    """Process inbound SMS forwarded by the Android device.

    If the body contains a STOP keyword (normalized), the sender's number
    is added to the user's opt-out list so future sends are blocked.
    Never auto-replies unless explicitly configured (default: off).
    """
    phone_result = normalize_phone(sender)
    if not phone_result.valid:
        return {"matched": False, "reason": "invalid sender"}

    text = (body or "").strip().upper().replace("\u00a0", " ")
    keywords = {k.strip().upper() for k in settings.STOP_KEYWORDS.split(",") if k.strip()}
    matched = text in keywords or any(
        text.startswith(k + " ") or text.endswith(" " + k) for k in keywords
    )

    if not matched:
        return {"matched": False, "reason": "no stop keyword"}

    existing = db.scalar(
        select(OptOut).where(
            OptOut.user_id == device.user_id, OptOut.phone == phone_result.normalized
        )
    )
    if not existing:
        db.add(
            OptOut(
                user_id=device.user_id,
                phone=phone_result.normalized,
                reason="STOP keyword received on device",
            )
        )
        log_action(
            db,
            device.user_id,
            "optout.stop_keyword",
            "optout",
            None,
            {"phone": phone_result.normalized, "sender": sender, "device_id": device.id},
        )
    db.flush()

    reply = None
    if settings.STOP_AUTO_REPLY_ENABLED:
        message_id = str(uuid.uuid4())
        reply = {
            "type": "send_message",
            "command_id": str(uuid.uuid4()),
            "message_id": message_id,
            "idempotency_key": f"reply:{message_id}",
            "phone": phone_result.normalized,
            "message": settings.STOP_AUTO_REPLY_TEXT,
            "send_at": _now().isoformat(),
            "test": False,
            "is_reply": True,
        }
        await_send(device.id, reply)
    return {"matched": True, "phone": phone_result.normalized, "auto_reply": bool(reply)}


# ---------------------------------------------------------------- heartbeat/offline


def process_heartbeat(
    db: Session,
    device: Device,
    battery_level: int | None = None,
    sim_state: str | None = None,
    network_state: str | None = None,
    app_version: str | None = None,
    phone_model: str | None = None,
    android_version: str | None = None,
) -> Device:
    now = _now()
    device.last_seen = now
    if battery_level is not None:
        device.battery_level = battery_level
    if sim_state is not None:
        device.sim_state = sim_state
    if network_state is not None:
        device.network_state = network_state
    if app_version is not None:
        device.app_version = app_version
    if phone_model is not None:
        device.phone_model = phone_model
    if android_version is not None:
        device.android_version = android_version
    # A heartbeat only proves liveness, not connectivity: CONNECTED is
    # managed by the WebSocket layer.
    db.flush()
    return device


def mark_device_offline(db: Session, device: Device, reason: str = "connection lost") -> Device:
    if device.connection_status == "CONNECTED":
        device.connection_status = "OFFLINE"
        log_action(db, device.user_id, "device.offline", "device", device.id, {"reason": reason})
        db.flush()
    return device


def mark_device_connected(db: Session, device: Device) -> Device:
    device.connection_status = "CONNECTED"
    device.last_seen = _now()
    log_action(db, device.user_id, "device.online", "device", device.id)
    db.flush()
    return device


def mark_device_disconnected(db: Session, device: Device, reason: str = "user requested") -> Device:
    if device.connection_status in ("CONNECTED", "CONNECTING", "OFFLINE"):
        device.connection_status = "DISCONNECTED"
        log_action(db, device.user_id, "device.disconnected", "device", device.id, {"reason": reason})
        db.flush()
    return device


def sweep_offline_devices(db: Session) -> int:
    """Mark devices OFFLINE when no traffic arrived within the timeout.

    Also auto-pauses send jobs on those devices when configured.
    Returns the number of devices marked offline.
    """
    cutoff = _now() - timedelta(seconds=settings.DEVICE_OFFLINE_TIMEOUT_SECONDS)
    devices = db.scalars(
        select(Device).where(
            Device.connection_status == "CONNECTED",
            (Device.last_seen.is_(None)) | (Device.last_seen < cutoff),
        )
    ).all()

    marked = 0
    for device in devices:
        mark_device_offline(db, device, "heartbeat timeout")
        marked += 1
        if settings.PAUSE_CAMPAIGN_ON_DEVICE_OFFLINE:
            jobs = db.scalars(
                select(SendJob).where(
                    SendJob.device_id == device.id, SendJob.status == "ACTIVE"
                )
            ).all()
            for job in jobs:
                job.status = "PAUSED"
                campaign = db.get(Campaign, job.campaign_id)
                if campaign and campaign.status == "RUNNING":
                    campaign.status = "PAUSED"
                log_action(
                    db, device.user_id, "campaign.paused_device_offline",
                    "campaign", job.campaign_id,
                )
    db.flush()
    return marked


def active_jobs_for_device(db: Session, device_id: int) -> list[SendJob]:
    return list(
        db.scalars(
            select(SendJob).where(SendJob.device_id == device_id, SendJob.status == "ACTIVE")
        ).all()
    )


def device_counters(db: Session, device_id: int) -> dict:
    """Real counters for the device card."""
    from sqlalchemy import func

    job = db.scalar(select(SendJob).where(SendJob.device_id == device_id))
    queued = 0
    if job:
        queued = db.scalar(
            select(func.count())
            .select_from(CampaignRecipient)
            .where(
                CampaignRecipient.campaign_id == job.campaign_id,
                CampaignRecipient.status.in_(("QUEUED", "PROCESSING")),
            )
        ) or 0
    sent = db.scalar(
        select(func.count())
        .select_from(MessageLog)
        .where(MessageLog.device_id == device_id, MessageLog.status == "SENT")
    ) or 0
    failed = db.scalar(
        select(func.count())
        .select_from(MessageLog)
        .where(MessageLog.device_id == device_id, MessageLog.status == "FAILED")
    ) or 0
    return {
        "messages_queued": queued,
        "messages_sent": sent,
        "messages_failed": failed,
    }
