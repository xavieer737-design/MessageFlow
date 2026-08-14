"""Template variables, personalization, and SMS counter tests."""

from app.services.sms_service import analyze_message
from app.services.template_service import extract_variables, personalize


class FakeContact:
    def __init__(self, **kwargs):
        self.first_name = kwargs.get("first_name", "")
        self.last_name = kwargs.get("last_name", "")
        self.phone = kwargs.get("phone", "")
        self.email = kwargs.get("email", "")
        self.company = kwargs.get("company", "")
        self.notes = kwargs.get("notes", "")


def test_extract_supported_variables():
    analysis = extract_variables("Hi {{first_name}}, order from {{company}} is ready")
    assert set(analysis.variables_found) == {"first_name", "company"}
    assert analysis.unsupported_variables == []


def test_extract_unsupported_variables():
    analysis = extract_variables("Hi {{first_name}} {{unknown_var}} {{Order_ID}}")
    assert analysis.variables_found == ["first_name"]
    assert analysis.unsupported_variables == ["unknown_var", "Order_ID"]


def test_personalize_message():
    contact = FakeContact(first_name="Rahul", company="ABC Ltd")
    message, missing = personalize("Hi {{first_name}}, your order from {{company}} is ready.", contact)
    assert message == "Hi Rahul, your order from ABC Ltd is ready."
    assert missing == []


def test_personalize_whitespace_tolerant():
    contact = FakeContact(first_name="Rahul")
    message, _ = personalize("Hi {{ first_name }}!", contact)
    assert message == "Hi Rahul!"


def test_personalize_case_insensitive():
    contact = FakeContact(first_name="Rahul")
    message, _ = personalize("Hi {{FIRST_NAME}}", contact)
    assert message == "Hi Rahul"


def test_missing_fields_reported():
    contact = FakeContact(first_name="Rahul")
    message, missing = personalize("Hi {{first_name}} from {{company}}", contact)
    assert message == "Hi Rahul from "
    assert missing == ["company"]


def test_unknown_variable_left_intact():
    contact = FakeContact(first_name="Rahul")
    message, missing = personalize("Hi {{first_name}} {{custom}}", contact)
    assert "{{custom}}" in message
    assert missing == []


def test_all_supported_variables():
    contact = FakeContact(
        first_name="Rahul", last_name="Sharma", phone="+919876543210",
        email="rahul@example.com", company="ABC Ltd", notes="priority",
    )
    message, missing = personalize(
        "{{first_name}}|{{last_name}}|{{phone}}|{{email}}|{{company}}|{{notes}}", contact
    )
    assert message == "Rahul|Sharma|+919876543210|rahul@example.com|ABC Ltd|priority"
    assert missing == []


def test_create_template_rejects_unsupported_variables(user_client):
    response = user_client.post(
        "/api/templates",
        json={"name": "Bad", "message": "Hi {{first_name}} {{order_id}}"},
    )
    assert response.status_code == 422


def test_template_preview_endpoint(user_client):
    response = user_client.post(
        "/api/templates/preview",
        json={
            "message": "Hi {{first_name}}, your order from {{company}} is ready.",
            "first_name": "Rahul",
            "company": "ABC Ltd",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["preview"] == "Hi Rahul, your order from ABC Ltd is ready."
    assert body["variables_found"] == ["first_name", "company"]


def test_sms_gsm_7bit_single_segment():
    analysis = analyze_message("Hello world! This is a short message.")
    assert analysis.encoding == "GSM-7"
    assert analysis.segments == 1
    assert not analysis.truncated


def test_sms_gsm_160_chars_single_segment():
    analysis = analyze_message("a" * 160)
    assert analysis.segments == 1
    assert analysis.characters == 160


def test_sms_gsm_161_chars_two_segments():
    analysis = analyze_message("a" * 161)
    assert analysis.segments == 2
    assert analysis.truncated


def test_sms_unicode_ucs2():
    analysis = analyze_message("Привет, мир! Это тестовое сообщение.")
    assert analysis.encoding == "UCS-2"
    assert analysis.segments == 1


def test_sms_ucs2_70_chars_limit():
    analysis = analyze_message("Ж" * 70)
    assert analysis.encoding == "UCS-2"
    assert analysis.segments == 1
    analysis = analyze_message("Ж" * 71)
    assert analysis.segments == 2


def test_sms_extension_table_counts_double():
    # "€" is a GSM extension character: counts as 2 chars, one segment.
    analysis = analyze_message("Cost: €50")
    assert analysis.encoding == "GSM-7"
    assert analysis.characters == 10
    assert analysis.segments == 1
