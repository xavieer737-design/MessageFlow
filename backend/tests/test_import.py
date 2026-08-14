"""CSV / XLSX import flow tests."""

import io

from tests.conftest import register

CSV_SAMPLE = (
    "phone,name,company,email\n"
    "9876543210,Rahul,ABC Ltd,rahul@example.com\n"
    "9876543211,Amit,XYZ Ltd,amit@example.com\n"
)


def upload(client, filename="contacts.csv", content=CSV_SAMPLE):
    return client.post(
        "/api/contacts/import/upload",
        files={"file": (filename, io.BytesIO(content.encode()), "text/csv")},
    )


def test_upload_detects_columns_and_suggests_name_mapping(user_client):
    response = upload(user_client)
    assert response.status_code == 200
    body = response.json()
    assert body["columns"] == ["phone", "name", "company", "email"]
    # Combined "name" column is intelligently mapped to first_name.
    assert body["suggested_mapping"]["name"] == "first_name"
    assert body["total_rows"] == 2
    assert body["summary"]["valid"] == 2


def test_full_import_flow_counts(user_client):
    body = upload(user_client).json()
    confirmed = user_client.post(
        "/api/contacts/import/confirm",
        data={
            "file_id": body["file_id"],
            "mapping": '{"phone":"phone","name":"first_name","company":"company","email":"email"}',
        },
    )
    assert confirmed.status_code == 200
    result = confirmed.json()
    assert result == {
        "total": 2,
        "valid": 2,
        "invalid": 0,
        "duplicates": 0,
        "opted_out": 0,
        "imported": 2,
    }
    contacts = user_client.get("/api/contacts").json()
    assert contacts["total"] == 2
    phones = {c["phone"] for c in contacts["items"]}
    assert phones == {"+919876543210", "+919876543211"}


def test_import_detects_duplicates_and_invalid(user_client):
    # One number already in the address book.
    user_client.post(
        "/api/contacts", json={"phone": "9876543210", "first_name": "Existing"}
    )
    csv = (
        "phone,name\n"
        "9876543210,Duplicate\n"      # duplicate of existing contact
        "9876543212,New\n"            # valid
        "9876543210,In-file dup\n"    # duplicate within file
        "not-a-number,Bad\n"          # invalid
        ",NoPhone\n"                  # empty phone -> invalid
    )
    body = upload(user_client, content=csv).json()
    assert body["summary"] == {
        "valid": 1,
        "invalid": 2,
        "duplicates": 2,
        "opted_out": 0,
    }


def test_import_excludes_opted_out(user_client):
    user_client.post("/api/optouts", json={"phone": "9876543211"})
    csv = "phone,name\n9876543211,Opted\n9876543212,Ok\n"
    body = upload(user_client, content=csv).json()
    assert body["summary"]["opted_out"] == 1
    assert body["summary"]["valid"] == 1

    confirmed = user_client.post(
        "/api/contacts/import/confirm",
        data={
            "file_id": body["file_id"],
            "mapping": '{"phone":"phone","name":"first_name"}',
        },
    ).json()
    assert confirmed["imported"] == 1
    assert confirmed["opted_out"] == 1


def test_xlsx_import(user_client):
    import pandas as pd

    buffer = io.BytesIO()
    pd.DataFrame(
        [{"phone": "9876543210", "name": "Rahul", "company": "ABC Ltd"}]
    ).to_excel(buffer, index=False)
    buffer.seek(0)

    response = user_client.post(
        "/api/contacts/import/upload",
        files={"file": ("contacts.xlsx", buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "xlsx"
    assert body["suggested_mapping"]["name"] == "first_name"

    confirmed = user_client.post(
        "/api/contacts/import/confirm",
        data={
            "file_id": body["file_id"],
            "mapping": '{"phone":"phone","name":"first_name","company":"company"}',
        },
    ).json()
    assert confirmed["imported"] == 1
    assert user_client.get("/api/contacts").json()["total"] == 1


def test_import_rejects_bad_file_type(user_client):
    response = user_client.post(
        "/api/contacts/import/upload",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


def test_import_requires_auth(client):
    assert upload(client).status_code == 401


def test_import_upload_not_shared_between_users(client, user_client, second_user_client):
    body = upload(user_client).json()
    # User B cannot confirm user A's staged upload.
    response = second_user_client.post(
        "/api/contacts/import/confirm",
        data={
            "file_id": body["file_id"],
            "mapping": '{"phone":"phone","name":"first_name"}',
        },
    )
    assert response.status_code == 404
