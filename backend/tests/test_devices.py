"""Device registration / heartbeat tests (Phase 1: metadata only)."""


def test_register_device(user_client):
    response = user_client.post(
        "/api/devices/register",
        json={
            "device_name": "Pixel 8",
            "device_identifier": "android-id-1234567890",
            "platform": "android",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["connection_status"] == "DISCONNECTED"  # never faked as connected
    assert body["last_seen"] is None


def test_register_duplicate_identifier_conflict(user_client):
    user_client.post(
        "/api/devices/register",
        json={"device_name": "Pixel", "device_identifier": "android-id-1234567890"},
    )
    response = user_client.post(
        "/api/devices/register",
        json={"device_name": "Pixel 2", "device_identifier": "android-id-1234567890"},
    )
    assert response.status_code == 409


def test_heartbeat_updates_last_seen(user_client):
    device = user_client.post(
        "/api/devices/register",
        json={"device_name": "Pixel 8", "device_identifier": "android-id-1234567890"},
    ).json()
    response = user_client.post(
        f"/api/devices/{device['id']}/heartbeat",
        json={"device_identifier": "android-id-1234567890"},
    )
    assert response.status_code == 200
    assert response.json()["last_seen"] is not None
    # Phase 1 never claims a connection was established.
    assert response.json()["connection_status"] == "DISCONNECTED"


def test_heartbeat_identifier_mismatch_forbidden(user_client):
    device = user_client.post(
        "/api/devices/register",
        json={"device_name": "Pixel 8", "device_identifier": "android-id-1234567890"},
    ).json()
    response = user_client.post(
        f"/api/devices/{device['id']}/heartbeat",
        json={"device_identifier": "someone-elses-device"},
    )
    assert response.status_code == 403


def test_delete_device(user_client):
    device = user_client.post(
        "/api/devices/register",
        json={"device_name": "Pixel 8", "device_identifier": "android-id-1234567890"},
    ).json()
    assert user_client.delete(f"/api/devices/{device['id']}").status_code == 204
    assert user_client.get("/api/devices").json() == []


def test_device_isolation(client, user_client, second_user_client):
    device = user_client.post(
        "/api/devices/register",
        json={"device_name": "Pixel 8", "device_identifier": "android-id-1234567890"},
    ).json()
    assert second_user_client.get("/api/devices").json() == []
    assert second_user_client.delete(f"/api/devices/{device['id']}").status_code == 404
    assert (
        second_user_client.post(
            f"/api/devices/{device['id']}/heartbeat",
            json={"device_identifier": "android-id-1234567890"},
        ).status_code
        == 404
    )
