"""Contact CRUD, normalization, duplicates, and user isolation tests."""

from tests.conftest import register


def make_contact(client, phone="9876543210", **extra):
    payload = {"phone": phone, "first_name": "Rahul", "company": "ABC Ltd", **extra}
    return client.post("/api/contacts", json=payload)


def test_create_contact_normalizes_phone(user_client):
    response = make_contact(user_client, phone="9876543210")
    assert response.status_code == 201
    assert response.json()["phone"] == "+919876543210"


def test_create_contact_international_format(user_client):
    response = make_contact(user_client, phone="+44 20 7946 0958")
    assert response.status_code == 201
    assert response.json()["phone"] == "+442079460958"


def test_create_contact_rejects_invalid_phone(user_client):
    response = make_contact(user_client, phone="not-a-number")
    assert response.status_code == 422


def test_create_contact_duplicate_phone_conflict(user_client):
    assert make_contact(user_client, phone="9876543210").status_code == 201
    assert make_contact(user_client, phone="+919876543210").status_code == 409


def test_contact_requires_auth(client):
    assert client.post("/api/contacts", json={"phone": "9876543210"}).status_code == 401


def test_update_contact(user_client):
    contact_id = make_contact(user_client).json()["id"]
    response = user_client.put(
        f"/api/contacts/{contact_id}",
        json={"phone": "9876543210", "first_name": "Rahul", "last_name": "Sharma", "company": "XYZ"},
    )
    assert response.status_code == 200
    assert response.json()["last_name"] == "Sharma"


def test_delete_contact(user_client):
    contact_id = make_contact(user_client).json()["id"]
    assert user_client.delete(f"/api/contacts/{contact_id}").status_code == 204
    assert user_client.get(f"/api/contacts/{contact_id}").status_code == 404


def test_search_contacts(user_client):
    make_contact(user_client, phone="9876543210", first_name="Rahul")
    make_contact(user_client, phone="9876543211", first_name="Amit", company="XYZ Ltd")
    response = user_client.get("/api/contacts", params={"search": "amit"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["first_name"] == "Amit"


def test_pagination(user_client):
    for i in range(5):
        make_contact(user_client, phone=f"98765432{i:02d}")
    page = user_client.get("/api/contacts", params={"page": 2, "page_size": 2}).json()
    assert page["total"] == 5
    assert page["pages"] == 3
    assert len(page["items"]) == 2


def test_bulk_delete(user_client):
    id1 = make_contact(user_client, phone="9876543210").json()["id"]
    id2 = make_contact(user_client, phone="9876543211").json()["id"]
    response = user_client.post("/api/contacts/bulk-delete", json=[id1, id2])
    assert response.status_code == 204
    assert user_client.get("/api/contacts").json()["total"] == 0


def test_export_contacts_csv(user_client):
    make_contact(user_client, phone="9876543210", first_name="Rahul")
    response = user_client.get("/api/contacts/export")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "Rahul" in response.text
    assert "+919876543210" in response.text


def test_user_isolation(client, user_client, second_user_client):
    """User B must not see or touch User A's contacts."""
    contact_id = make_contact(user_client, phone="9876543210").json()["id"]

    assert second_user_client.get("/api/contacts").json()["total"] == 0
    assert second_user_client.get(f"/api/contacts/{contact_id}").status_code == 404
    assert second_user_client.put(
        f"/api/contacts/{contact_id}",
        json={"phone": "9876543210", "first_name": "Hacked"},
    ).status_code == 404
    assert second_user_client.delete(f"/api/contacts/{contact_id}").status_code == 404
