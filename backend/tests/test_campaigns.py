"""Campaign creation, validation, personalization, opt-out filtering."""

from tests.conftest import register

TEMPLATE = "Hi {{first_name}}, your order from {{company}} is ready."


def add_contacts(user_client):
    payloads = [
        {"phone": "9876543210", "first_name": "Rahul", "company": "ABC Ltd"},
        {"phone": "9876543211", "first_name": "Amit", "company": "XYZ Ltd"},
        {"phone": "9876543212", "first_name": "Neha", "company": "ABC Ltd"},
    ]
    ids = []
    for payload in payloads:
        response = user_client.post("/api/contacts", json=payload)
        assert response.status_code == 201
        ids.append(response.json()["id"])
    return ids


def test_create_campaign_draft(user_client):
    add_contacts(user_client)
    response = user_client.post(
        "/api/campaigns",
        json={
            "name": "Launch",
            "message_template": TEMPLATE,
            "recipients": {"scope": "all"},
            "status": "DRAFT",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["recipient_count"] == 3


def test_campaign_targets_group(user_client):
    ids = add_contacts(user_client)
    group = user_client.post("/api/groups", json={"name": "VIP"}).json()
    user_client.post(f"/api/groups/{group['id']}/contacts", json={"contact_ids": ids[:2]})

    response = user_client.post(
        "/api/campaigns",
        json={
            "name": "VIP only",
            "message_template": TEMPLATE,
            "recipients": {"scope": "group", "group_id": group["id"]},
        },
    )
    assert response.status_code == 201
    assert response.json()["recipient_count"] == 2


def test_campaign_targets_selected_contacts(user_client):
    ids = add_contacts(user_client)
    response = user_client.post(
        "/api/campaigns",
        json={
            "name": "Selected",
            "message_template": TEMPLATE,
            "recipients": {"scope": "contacts", "contact_ids": [ids[0], ids[2]]},
        },
    )
    assert response.status_code == 201
    assert response.json()["recipient_count"] == 2


def test_validation_personalizes_messages(user_client):
    add_contacts(user_client)
    campaign = user_client.post(
        "/api/campaigns",
        json={"name": "Launch", "message_template": TEMPLATE, "recipients": {"scope": "all"}},
    ).json()
    report = user_client.post(f"/api/campaigns/{campaign['id']}/validate").json()
    assert report["valid"] is True
    assert report["total_recipients"] == 3
    assert report["pending"] == 3
    previews = {p["name"]: p["preview"] for p in report["previews"]}
    assert "Hi Rahul, your order from ABC Ltd is ready." in previews.values()
    assert "Hi Amit, your order from XYZ Ltd is ready." in previews.values()


def test_validation_filters_opted_out(user_client):
    add_contacts(user_client)
    user_client.post("/api/optouts", json={"phone": "9876543211", "reason": "STOP"})

    campaign = user_client.post(
        "/api/campaigns",
        json={"name": "Launch", "message_template": TEMPLATE, "recipients": {"scope": "all"}},
    ).json()
    report = user_client.post(f"/api/campaigns/{campaign['id']}/validate").json()
    assert report["skipped_opted_out"] == 1
    assert report["pending"] == 2
    assert any(
        w["category"] == "opted_out" and "opted out" in w["message"] for w in report["warnings"]
    )
    # Recipients persisted with the OPTED_OUT status.
    detail = user_client.get(f"/api/campaigns/{campaign['id']}").json()
    statuses = {r["status"] for r in detail["recipients"]}
    assert "OPTED_OUT" in statuses


def test_validation_flags_invalid_phone(user_client, db):
    """Defense in depth: even if an invalid phone somehow lands in the
    database, campaign validation flags and skips it."""
    add_contacts(user_client)
    from sqlalchemy import update as sa_update

    from app.models import Contact

    # Simulate legacy/corrupt data bypassing the API guards.
    db.execute(sa_update(Contact).values(phone="not-a-number").where(Contact.phone == "+919876543210"))
    db.commit()

    campaign = user_client.post(
        "/api/campaigns",
        json={"name": "Launch", "message_template": TEMPLATE, "recipients": {"scope": "all"}},
    ).json()
    report = user_client.post(f"/api/campaigns/{campaign['id']}/validate").json()
    assert report["skipped_invalid_phone"] == 1
    assert report["valid"] is False
    assert any(e["category"] == "invalid_phone" for e in report["errors"])


def test_validation_flags_unsupported_variables(user_client):
    add_contacts(user_client)
    campaign = user_client.post(
        "/api/campaigns",
        json={
            "name": "Bad var",
            "message_template": "Hi {{first_name}} {{order_id}}",
            "recipients": {"scope": "all"},
        },
    ).json()
    report = user_client.post(f"/api/campaigns/{campaign['id']}/validate").json()
    assert report["valid"] is False
    assert any(e["category"] == "unsupported_variables" for e in report["errors"])


def test_validation_flags_sms_length(user_client):
    add_contacts(user_client)
    long_message = "a" * 1700  # > 10 GSM segments
    campaign = user_client.post(
        "/api/campaigns",
        json={"name": "Long", "message_template": long_message, "recipients": {"scope": "all"}},
    ).json()
    report = user_client.post(f"/api/campaigns/{campaign['id']}/validate").json()
    assert any(e["category"] == "sms_length" for e in report["errors"])


def test_mark_ready_requires_clean_validation(user_client):
    add_contacts(user_client)
    campaign = user_client.post(
        "/api/campaigns",
        json={"name": "Launch", "message_template": TEMPLATE, "recipients": {"scope": "all"}},
    ).json()
    ready = user_client.post(f"/api/campaigns/{campaign['id']}/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "READY"


def test_mark_ready_rejected_when_invalid(user_client):
    add_contacts(user_client)
    campaign = user_client.post(
        "/api/campaigns",
        json={"name": "Bad", "message_template": "Hi {{first_name}} {{nope}}", "recipients": {"scope": "all"}},
    ).json()
    response = user_client.post(f"/api/campaigns/{campaign['id']}/ready")
    assert response.status_code == 422


def test_status_transitions(user_client):
    add_contacts(user_client)
    campaign = user_client.post(
        "/api/campaigns",
        json={"name": "Launch", "message_template": TEMPLATE, "recipients": {"scope": "all"}},
    ).json()
    cid = campaign["id"]

    # Draft -> Ready
    assert user_client.post(f"/api/campaigns/{cid}/ready").json()["status"] == "READY"
    # Ready -> Paused
    assert user_client.post(f"/api/campaigns/{cid}/pause").json()["status"] == "PAUSED"
    # Paused -> Ready
    assert user_client.post(f"/api/campaigns/{cid}/resume").json()["status"] == "READY"
    # Ready -> Cancelled
    assert user_client.post(f"/api/campaigns/{cid}/cancel").json()["status"] == "CANCELLED"
    # Cancelled is terminal
    assert user_client.post(f"/api/campaigns/{cid}/cancel").status_code == 409


def test_edit_only_in_draft(user_client):
    add_contacts(user_client)
    campaign = user_client.post(
        "/api/campaigns",
        json={"name": "Launch", "message_template": TEMPLATE, "recipients": {"scope": "all"}},
    ).json()
    user_client.post(f"/api/campaigns/{campaign['id']}/ready")
    response = user_client.put(
        f"/api/campaigns/{campaign['id']}",
        json={"name": "Renamed"},
    )
    assert response.status_code == 409


def test_duplicate_campaign(user_client):
    add_contacts(user_client)
    campaign = user_client.post(
        "/api/campaigns",
        json={"name": "Launch", "message_template": TEMPLATE, "recipients": {"scope": "all"}},
    ).json()
    copy = user_client.post(f"/api/campaigns/{campaign['id']}/duplicate").json()
    assert copy["name"] == "Launch (copy)"
    assert copy["status"] == "DRAFT"
    assert copy["recipient_count"] == 3


def test_validation_writes_real_message_logs(user_client):
    """SKIPPED/OPTED_OUT validation results produce real log entries."""
    add_contacts(user_client)
    user_client.post("/api/optouts", json={"phone": "9876543211"})
    campaign = user_client.post(
        "/api/campaigns",
        json={"name": "Launch", "message_template": TEMPLATE, "recipients": {"scope": "all"}},
    ).json()
    user_client.post(f"/api/campaigns/{campaign['id']}/validate")

    logs = user_client.get("/api/messages").json()
    assert logs["total"] == 1
    assert logs["items"][0]["status"] == "OPTED_OUT"
    assert logs["items"][0]["error"] == "opted out"
    assert logs["items"][0]["campaign_name"] == "Launch"


def test_campaign_isolation(client, user_client, second_user_client):
    add_contacts(user_client)
    campaign = user_client.post(
        "/api/campaigns",
        json={"name": "Mine", "message_template": TEMPLATE, "recipients": {"scope": "all"}},
    ).json()
    assert second_user_client.get(f"/api/campaigns/{campaign['id']}").status_code == 404
    assert second_user_client.post(f"/api/campaigns/{campaign['id']}/validate").status_code == 404
    assert second_user_client.delete(f"/api/campaigns/{campaign['id']}").status_code == 404
