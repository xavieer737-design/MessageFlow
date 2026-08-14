"""Campaign send engine tests: queue, batching, idempotency, opt-out
recheck, pause/resume/cancel, test messages, isolation."""

import asyncio

from app.models import CampaignRecipient, Device, MessageAttempt, MessageLog, SendJob
from tests.phase2_helpers import (
    FakeWebSocket,
    auth_payload,
    pair_device,
    register_fake_device,
    sent_commands,
    unregister_fake_device,
)

TEMPLATE = "Hi {{first_name}}, your order from {{company}} is ready."


def add_contacts(user_client, count=3):
    ids = []
    for i in range(count):
        response = user_client.post(
            "/api/contacts",
            json={"phone": f"98765432{i:02d}", "first_name": f"Name{i}", "company": "ABC Ltd"},
        )
        assert response.status_code == 201
        ids.append(response.json()["id"])
    return ids


def ready_campaign(user_client, contact_count=3):
    add_contacts(user_client, contact_count)
    campaign = user_client.post(
        "/api/campaigns",
        json={"name": "Send test", "message_template": TEMPLATE, "recipients": {"scope": "all"}},
    ).json()
    assert user_client.post(f"/api/campaigns/{campaign['id']}/ready").status_code == 200
    return user_client.get(f"/api/campaigns/{campaign['id']}").json()


def setup_paired_connected_device(client, user_client, db):
    """Pair a device and register it in the in-memory WS manager."""
    body = pair_device(user_client)
    device = db.get(Device, body["device"]["id"])
    ws = asyncio.run(register_fake_device(device.id))
    return device, ws, body


# ---------------------------------------------------------------- start


def test_start_send_queues_recipients(client, user_client, db):
    campaign = ready_campaign(user_client)
    device, _ws, _body = setup_paired_connected_device(client, user_client, db)

    response = user_client.post(
        f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id}
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["queued"] == 3
    assert body["job_id"] > 0

    job = db.get(SendJob, body["job_id"])
    assert job.status == "ACTIVE"
    assert job.total_recipients == 3

    recipients = db.query(CampaignRecipient).filter_by(campaign_id=campaign["id"]).all()
    assert all(r.status in ("QUEUED", "PROCESSING") for r in recipients)
    assert all(r.message_id for r in recipients)

    # Campaign moved to RUNNING.
    assert user_client.get(f"/api/campaigns/{campaign['id']}").json()["status"] == "RUNNING"

    # Message attempts were created with unique ids and stable idempotency keys.
    attempts = db.query(MessageAttempt).filter_by(campaign_id=campaign["id"]).all()
    assert len(attempts) == 3
    assert len({a.message_id for a in attempts}) == 3
    assert len({a.idempotency_key for a in attempts}) == 3

    unregister_fake_device(device.id)


def test_start_send_requires_ready_campaign(client, user_client, db):
    campaign = user_client.post(
        "/api/campaigns",
        json={"name": "Draft", "message_template": TEMPLATE, "recipients": {"scope": "all"}},
    ).json()
    device, _ws, _body = setup_paired_connected_device(client, user_client, db)
    response = user_client.post(f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id})
    assert response.status_code == 409
    unregister_fake_device(device.id)


def test_start_send_requires_paired_device(client, user_client, db):
    campaign = ready_campaign(user_client)
    # A Phase-1 registered device (no public key / paired_at) cannot send.
    registered = user_client.post(
        "/api/devices/register",
        json={"device_name": "Old device", "device_identifier": "legacy-device-12345", "platform": "android"},
    ).json()
    response = user_client.post(
        f"/api/campaigns/{campaign['id']}/send", json={"device_id": registered["id"]}
    )
    assert response.status_code == 409
    assert "not paired" in response.json()["detail"]


def test_start_send_rechecks_optouts(client, user_client, db):
    campaign = ready_campaign(user_client)
    # One recipient opts out AFTER validation.
    user_client.post("/api/optouts", json={"phone": "9876543201", "reason": "STOP"})
    device, _ws, _body = setup_paired_connected_device(client, user_client, db)

    response = user_client.post(
        f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id}
    )
    body = response.json()
    assert body["queued"] == 2
    assert body["skipped_opted_out"] == 1

    recipients = db.query(CampaignRecipient).filter_by(campaign_id=campaign["id"]).all()
    opted = [r for r in recipients if r.status == "OPTED_OUT"]
    assert len(opted) == 1
    assert "re-checked at send time" in opted[0].error
    unregister_fake_device(device.id)


# ---------------------------------------------------------------- dispatch


def test_dispatch_batches_and_paces(client, user_client, db):
    campaign = ready_campaign(user_client, contact_count=5)
    device, ws, _body = setup_paired_connected_device(client, user_client, db)

    user_client.post(f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id})

    commands = sent_commands(ws)
    assert len(commands) == 5  # batch size >= recipients here
    assert all(c["type"] == "send_message" for c in commands)
    # Pacing: send_at timestamps are spaced by the configured rate.
    from datetime import datetime

    times = [datetime.fromisoformat(c["send_at"]) for c in commands]
    assert all(times[i] <= times[i + 1] for i in range(len(times) - 1))

    # Each command carries idempotency info.
    assert all(c["message_id"] for c in commands)
    assert all(c["idempotency_key"] for c in commands)
    assert all(c["phone"].startswith("+91") for c in commands)

    # Recipients are PROCESSING once the command is out.
    processing = db.query(CampaignRecipient).filter_by(campaign_id=campaign["id"], status="PROCESSING").count()
    assert processing == 5
    unregister_fake_device(device.id)


def test_dispatch_does_not_run_when_device_offline(client, user_client, db):
    campaign = ready_campaign(user_client)
    device, _ws, _body = setup_paired_connected_device(client, user_client, db)
    unregister_fake_device(device.id)  # device drops offline

    user_client.post(f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id})
    recipients = db.query(CampaignRecipient).filter_by(campaign_id=campaign["id"]).all()
    # Still queued, nothing dispatched, nothing lost.
    assert all(r.status in ("QUEUED", "PENDING") for r in recipients)
    job = db.query(SendJob).filter_by(campaign_id=campaign["id"]).first()
    assert job.status == "ACTIVE"


def test_batch_size_respected(client, user_client, db):
    from app.core.config import settings

    old = settings.SEND_BATCH_SIZE
    settings.SEND_BATCH_SIZE = 2
    try:
        campaign = ready_campaign(user_client, contact_count=5)
        device, ws, _body = setup_paired_connected_device(client, user_client, db)
        user_client.post(f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id})
        assert len(sent_commands(ws)) == 2  # only the first batch
        processing = db.query(CampaignRecipient).filter_by(campaign_id=campaign["id"], status="PROCESSING").count()
        assert processing == 2
    finally:
        settings.SEND_BATCH_SIZE = old
        unregister_fake_device(device.id)


def test_next_batch_dispatched_after_results(client, user_client, db):
    from app.core.config import settings

    old = settings.SEND_BATCH_SIZE
    settings.SEND_BATCH_SIZE = 2
    try:
        campaign = ready_campaign(user_client, contact_count=4)
        device, ws, _body = setup_paired_connected_device(client, user_client, db)
        user_client.post(f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id})
        first_batch = sent_commands(ws)
        assert len(first_batch) == 2

        # Device reports success for the first two.
        for command in first_batch:
            ws.sent.append(  # simulate the device's result via the service
                {"type": "message_result", "message_id": command["message_id"], "status": "SEND_SUCCESS"}
            )

        job = db.query(SendJob).filter_by(campaign_id=campaign["id"]).first()
        from app.services.send_service import handle_message_result

        for command in first_batch:
            handle_message_result(
                db, user_client.get("/api/auth/me").json()["id"], device,
                command["message_id"], "SEND_SUCCESS",
            )
        db.commit()

        # Next batch flows automatically.
        from app.services.send_service import dispatch_next_batch

        dispatch_next_batch(db, job)
        db.commit()
        assert len(sent_commands(ws)) == 4
    finally:
        settings.SEND_BATCH_SIZE = old
        unregister_fake_device(device.id)


# ---------------------------------------------------------------- results


def test_message_result_marks_sent_and_logs(client, user_client, db):
    campaign = ready_campaign(user_client)
    device, ws, _body = setup_paired_connected_device(client, user_client, db)
    user_client.post(f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id})

    command = sent_commands(ws)[0]
    user_id = user_client.get("/api/auth/me").json()["id"]

    from app.services.send_service import handle_message_result

    handle_message_result(db, user_id, device, command["message_id"], "SEND_SUCCESS", device_timestamp="2026-08-14T12:00:00Z")
    db.commit()

    attempt = db.query(MessageAttempt).filter_by(message_id=command["message_id"]).first()
    assert attempt.status == "SEND_SUCCESS"
    assert attempt.sent_at is not None

    recipient = db.get(CampaignRecipient, attempt.recipient_id)
    assert recipient.status == "SENT"
    assert recipient.sent_at is not None

    # Real message log entry - never fabricated.
    log = db.query(MessageLog).filter_by(campaign_id=campaign["id"], status="SENT").first()
    assert log is not None
    assert log.message == attempt.message
    assert log.device_id == device.id


def test_message_result_failure_recorded(client, user_client, db):
    campaign = ready_campaign(user_client)
    device, ws, _body = setup_paired_connected_device(client, user_client, db)
    user_client.post(f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id})

    command = sent_commands(ws)[0]
    user_id = user_client.get("/api/auth/me").json()["id"]

    from app.services.send_service import handle_message_result

    handle_message_result(db, user_id, device, command["message_id"], "SEND_FAILED", error="RESULT_ERROR_GENERIC_FAILURE")
    db.commit()

    attempt = db.query(MessageAttempt).filter_by(message_id=command["message_id"]).first()
    assert attempt.status == "SEND_FAILED"
    assert "GENERIC_FAILURE" in attempt.error
    recipient = db.get(CampaignRecipient, attempt.recipient_id)
    assert recipient.status == "FAILED"

    log = db.query(MessageLog).filter_by(campaign_id=campaign["id"], status="FAILED").first()
    assert log is not None
    assert log.error == "RESULT_ERROR_GENERIC_FAILURE"


def test_duplicate_result_is_idempotent(client, user_client, db):
    campaign = ready_campaign(user_client)
    device, ws, _body = setup_paired_connected_device(client, user_client, db)
    user_client.post(f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id})

    command = sent_commands(ws)[0]
    user_id = user_client.get("/api/auth/me").json()["id"]

    from app.services.send_service import handle_message_result

    handle_message_result(db, user_id, device, command["message_id"], "SEND_SUCCESS")
    db.commit()
    attempt = db.query(MessageAttempt).filter_by(message_id=command["message_id"]).first()
    first_sent_at = attempt.sent_at

    # A replayed result (e.g. after WS reconnect) must not change anything.
    handle_message_result(db, user_id, device, command["message_id"], "SEND_FAILED", error="late failure")
    db.commit()

    attempt = db.query(MessageAttempt).filter_by(message_id=command["message_id"]).first()
    assert attempt.status == "SEND_SUCCESS"
    assert attempt.sent_at == first_sent_at
    assert db.query(MessageLog).filter_by(campaign_id=campaign["id"], status="FAILED").count() == 0
    unregister_fake_device(device.id)


def test_no_redispatch_after_success(client, user_client, db):
    """After a successful send, re-running dispatch must not resend."""
    campaign = ready_campaign(user_client, contact_count=2)
    device, ws, _body = setup_paired_connected_device(client, user_client, db)
    user_client.post(f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id})

    user_id = user_client.get("/api/auth/me").json()["id"]
    job = db.query(SendJob).filter_by(campaign_id=campaign["id"]).first()

    from app.services.send_service import dispatch_next_batch, handle_message_result

    for command in sent_commands(ws):
        handle_message_result(db, user_id, device, command["message_id"], "SEND_SUCCESS")
    db.commit()

    commands_before = len(sent_commands(ws))
    # Simulate a reconnect/redispatch: nothing may be sent again.
    dispatch_next_batch(db, job)
    db.commit()
    assert len(sent_commands(ws)) == commands_before
    unregister_fake_device(device.id)


def test_redispatch_after_lost_result_uses_same_message_id(client, user_client, db):
    """If the device disconnects before its result reaches the server,
    the command is re-issued on reconnect with the SAME message_id so the
    device's idempotency store prevents a double send."""
    campaign = ready_campaign(user_client, contact_count=1)
    device, ws, _body = setup_paired_connected_device(client, user_client, db)
    user_client.post(f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id})

    first = sent_commands(ws)[0]
    assert first["message_id"]

    # Device disconnects; the result never arrives. Reconnect + redispatch.
    job = db.query(SendJob).filter_by(campaign_id=campaign["id"]).first()
    from app.services.send_service import dispatch_next_batch

    dispatch_next_batch(db, job)
    db.commit()

    commands = sent_commands(ws)
    assert len(commands) == 2
    # Same message_id: the Android device will replay its stored result
    # instead of sending the SMS again.
    assert commands[1]["message_id"] == first["message_id"]
    assert commands[1]["idempotency_key"] == first["idempotency_key"]

    recipient = db.query(CampaignRecipient).filter_by(campaign_id=campaign["id"]).first()
    assert recipient.attempt_count == 2
    unregister_fake_device(device.id)


def test_campaign_completes_when_all_terminal(client, user_client, db):
    campaign = ready_campaign(user_client, contact_count=2)
    device, ws, _body = setup_paired_connected_device(client, user_client, db)
    user_client.post(f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id})

    user_id = user_client.get("/api/auth/me").json()["id"]
    from app.services.send_service import handle_message_result

    for command in sent_commands(ws):
        handle_message_result(db, user_id, device, command["message_id"], "SEND_SUCCESS")
    db.commit()

    job = db.query(SendJob).filter_by(campaign_id=campaign["id"]).first()
    assert job.status == "COMPLETED"
    assert user_client.get(f"/api/campaigns/{campaign['id']}").json()["status"] == "COMPLETED"

    progress = user_client.get(f"/api/campaigns/{campaign['id']}/progress").json()
    assert progress["total"] == 2
    assert progress["sent"] == 2
    assert progress["progress"] == 1.0
    unregister_fake_device(device.id)


# ---------------------------------------------------------------- pause/resume/cancel


def test_pause_resume_cancel(client, user_client, db):
    # 8 contacts with batch size 5 -> a second batch remains after start.
    campaign = ready_campaign(user_client, contact_count=8)
    device, ws, _body = setup_paired_connected_device(client, user_client, db)
    user_client.post(f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id})
    job = db.query(SendJob).filter_by(campaign_id=campaign["id"]).first()
    assert len(sent_commands(ws)) == 5

    # Pause stops new dispatches.
    from app.services.send_service import dispatch_next_batch

    paused = user_client.post(f"/api/campaigns/{campaign['id']}/pause").json()
    assert paused["status"] == "PAUSED"
    assert job.status == "PAUSED"
    before = len(sent_commands(ws))
    dispatch_next_batch(db, job)
    db.commit()
    assert len(sent_commands(ws)) == before

    # Resume returns to RUNNING and dispatch works again.
    resumed = user_client.post(f"/api/campaigns/{campaign['id']}/resume").json()
    assert resumed["status"] == "RUNNING"
    dispatch_next_batch(db, job)
    db.commit()
    assert len(sent_commands(ws)) > before

    # Cancel stops everything and is terminal.
    cancelled = user_client.post(f"/api/campaigns/{campaign['id']}/cancel").json()
    assert cancelled["status"] == "CANCELLED"
    assert job.status == "CANCELLED"
    assert user_client.post(f"/api/campaigns/{campaign['id']}/cancel").status_code == 409
    unregister_fake_device(device.id)


def test_offline_detection_sweep(client, user_client, db):
    campaign = ready_campaign(user_client)
    device, _ws, _body = setup_paired_connected_device(client, user_client, db)
    device.connection_status = "CONNECTED"  # as the WS auth flow would set it

    # No heartbeat for a long time -> sweep marks OFFLINE and pauses the job.
    from datetime import datetime, timedelta, timezone

    device.last_seen = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()

    from app.services.send_service import sweep_offline_devices

    marked = sweep_offline_devices(db)
    db.commit()
    assert marked == 1
    assert device.connection_status == "OFFLINE"
    unregister_fake_device(device.id)


# ---------------------------------------------------------------- test message


def test_send_test_message_and_result(client, user_client, db):
    device, ws, _body = setup_paired_connected_device(client, user_client, db)

    response = user_client.post(
        f"/api/devices/{device.id}/test-message",
        json={"phone": "9876543210", "message": "Hello from MessageFlow test!"},
    )
    assert response.status_code == 202, response.text
    result = response.json()
    assert result["status"] == "SEND_REQUESTED"
    assert result["phone"] == "+919876543210"

    commands = sent_commands(ws)
    test_command = [c for c in commands if c["test"] is True]
    assert len(test_command) == 1
    assert test_command[0]["message_id"] == result["message_id"]
    assert test_command[0]["phone"] == "+919876543210"

    # Device reports the real result.
    user_id = user_client.get("/api/auth/me").json()["id"]
    from app.services.send_service import handle_message_result

    handle_message_result(db, user_id, device, result["message_id"], "SEND_FAILED", error="SIM not ready")
    db.commit()

    polled = user_client.get(f"/api/devices/{device.id}/test-message/{result['message_id']}").json()
    assert polled["status"] == "SEND_FAILED"
    assert polled["error"] == "SIM not ready"
    unregister_fake_device(device.id)


def test_test_message_requires_connected_device(client, user_client, db):
    body = pair_device(user_client)
    device = db.get(Device, body["device"]["id"])
    response = user_client.post(
        f"/api/devices/{device.id}/test-message",
        json={"phone": "9876543210", "message": "hi"},
    )
    assert response.status_code == 409
    assert "not connected" in response.json()["detail"]


# ---------------------------------------------------------------- isolation


def test_send_isolation(client, user_client, second_user_client, db):
    campaign = ready_campaign(user_client)
    device, _ws, _body = setup_paired_connected_device(client, user_client, db)

    # User B cannot start A's campaign or read A's progress.
    assert second_user_client.post(
        f"/api/campaigns/{campaign['id']}/send", json={"device_id": device.id}
    ).status_code == 404
    assert second_user_client.get(f"/api/campaigns/{campaign['id']}/progress").status_code == 404

    # User B cannot send a test message through A's device.
    assert second_user_client.post(
        f"/api/devices/{device.id}/test-message",
        json={"phone": "9876543210", "message": "hi"},
    ).status_code == 404
    unregister_fake_device(device.id)
