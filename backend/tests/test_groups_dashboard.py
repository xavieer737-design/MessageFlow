"""Groups and dashboard tests."""


def make_contact(client, phone, first_name="Rahul"):
    return client.post(
        "/api/contacts",
        json={"phone": phone, "first_name": first_name, "company": "ABC Ltd"},
    )


def test_group_crud(user_client):
    created = user_client.post("/api/groups", json={"name": "VIP", "description": "Top clients"})
    assert created.status_code == 201
    group = created.json()
    assert group["name"] == "VIP"
    assert group["contact_count"] == 0

    updated = user_client.put(
        f"/api/groups/{group['id']}", json={"name": "Premium", "description": "Best"}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Premium"

    assert user_client.delete(f"/api/groups/{group['id']}").status_code == 204
    assert user_client.get(f"/api/groups/{group['id']}").status_code == 404


def test_group_name_conflict(user_client):
    user_client.post("/api/groups", json={"name": "VIP"})
    response = user_client.post("/api/groups", json={"name": "vip"})
    assert response.status_code == 409


def test_add_remove_contacts_in_group(user_client):
    contact_a = make_contact(user_client, "9876543210").json()
    contact_b = make_contact(user_client, "9876543211", "Amit").json()
    group = user_client.post("/api/groups", json={"name": "Leads"}).json()

    added = user_client.post(
        f"/api/groups/{group['id']}/contacts", json={"contact_ids": [contact_a["id"], contact_b["id"]]}
    )
    assert added.status_code == 200
    assert added.json()["contact_count"] == 2
    assert set(added.json()["contact_ids"]) == {contact_a["id"], contact_b["id"]}

    removed = user_client.post(
        f"/api/groups/{group['id']}/contacts/remove", json={"contact_ids": [contact_a["id"]]}
    )
    assert removed.json()["contact_count"] == 1

    # Contact list reflects the group through the membership.
    filtered = user_client.get("/api/contacts", params={"group_id": group["id"]}).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == contact_b["id"]


def test_group_isolation(client, user_client, second_user_client):
    group = user_client.post("/api/groups", json={"name": "VIP"}).json()
    assert second_user_client.get("/api/groups").json() == []
    assert second_user_client.put(
        f"/api/groups/{group['id']}", json={"name": "Hacked"}
    ).status_code == 404
    assert second_user_client.delete(f"/api/groups/{group['id']}").status_code == 404


def test_dashboard_stats_from_real_data(user_client):
    make_contact(user_client, "9876543210")
    make_contact(user_client, "9876543211", "Amit")
    user_client.post("/api/optouts", json={"phone": "9876543212"})
    user_client.post("/api/templates", json={"name": "T", "message": "Hi {{first_name}}"})

    response = user_client.get("/api/dashboard/stats")
    assert response.status_code == 200
    stats = response.json()["stats"]
    assert stats["total_contacts"] == 2
    assert stats["total_templates"] == 1
    assert stats["opt_outs"] == 1
    assert stats["messages_sent"] == 0  # nothing was ever sent (Phase 1)
    assert stats["failed_messages"] == 0
    assert stats["connected_devices"] == 0


def test_dashboard_recent_activity(user_client):
    make_contact(user_client, "9876543210")
    data = user_client.get("/api/dashboard/stats").json()
    actions = [a["action"] for a in data["recent_activity"]]
    assert "contact.created" in actions
    assert "auth.register" in actions


def test_dashboard_requires_auth(client):
    assert client.get("/api/dashboard/stats").status_code == 401
