"""Opt-out list tests."""

import io


def test_add_optout_normalizes(user_client):
    response = user_client.post("/api/optouts", json={"phone": "9876543210", "reason": "STOP"})
    assert response.status_code == 201
    assert response.json()["phone"] == "+919876543210"


def test_add_optout_invalid_phone(user_client):
    response = user_client.post("/api/optouts", json={"phone": "nope"})
    assert response.status_code == 422


def test_add_duplicate_optout_conflict(user_client):
    user_client.post("/api/optouts", json={"phone": "9876543210"})
    response = user_client.post("/api/optouts", json={"phone": "+919876543210"})
    assert response.status_code == 409


def test_list_and_search(user_client):
    user_client.post("/api/optouts", json={"phone": "9876543210"})
    user_client.post("/api/optouts", json={"phone": "9876543211"})
    assert user_client.get("/api/optouts").json()["total"] == 2
    found = user_client.get("/api/optouts", params={"search": "3211"}).json()
    assert found["total"] == 1
    assert found["items"][0]["phone"] == "+919876543211"


def test_delete_optout(user_client):
    entry = user_client.post("/api/optouts", json={"phone": "9876543210"}).json()
    assert user_client.delete(f"/api/optouts/{entry['id']}").status_code == 204
    assert user_client.get("/api/optouts").json()["total"] == 0


def test_bulk_add(user_client):
    response = user_client.post(
        "/api/optouts/bulk",
        json={"phones": ["9876543210", "9876543211", "9876543210", "garbage"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 2
    assert body["duplicates"] == 1
    assert body["skipped_invalid"] == ["garbage"]


def test_import_optouts_from_csv(user_client):
    csv_content = "phone\n9876543210\n9876543211\nnot-a-number\n"
    response = user_client.post(
        "/api/optouts/import",
        files={"file": ("optouts.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 2
    assert len(body["skipped_invalid"]) == 1
    assert user_client.get("/api/optouts").json()["total"] == 2


def test_export_optouts(user_client):
    user_client.post("/api/optouts", json={"phone": "9876543210"})
    response = user_client.get("/api/optouts/export")
    assert response.status_code == 200
    assert "+919876543210" in response.text


def test_optout_isolation(client, user_client, second_user_client):
    entry = user_client.post("/api/optouts", json={"phone": "9876543210"}).json()
    assert second_user_client.get("/api/optouts").json()["total"] == 0
    assert second_user_client.delete(f"/api/optouts/{entry['id']}").status_code == 404
