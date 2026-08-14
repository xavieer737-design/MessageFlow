"""Optional demo seed: creates a demo user with sample data.

Run from /backend:

    ../.venv/bin/python scripts/seed.py

Creates (idempotently, only when the email is free):
- demo@messageflow.dev / demo1234
- sample contacts, groups, a template, and a READY demo campaign.

No message logs or delivery records are fabricated.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Campaign, CampaignRecipient, Contact, ContactGroup, MessageTemplate, User
from app.services.campaign_service import build_validation_report, create_campaign
from app.schemas.campaign import RecipientTarget

DEMO_EMAIL = os.environ.get("SEED_EMAIL", "demo@messageflow.dev")
DEMO_PASSWORD = os.environ.get("SEED_PASSWORD", "demo1234")


def main() -> None:
    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing:
            print(f"Demo user already exists ({DEMO_EMAIL}); skipping.")
            return

        user = User(name="Demo User", email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        db.flush()

        contacts_data = [
            ("+919876543210", "Rahul", "Sharma", "ABC Ltd", "rahul@example.com"),
            ("+919876543211", "Amit", "Verma", "XYZ Ltd", "amit@example.com"),
            ("+919876543212", "Neha", "Gupta", "ABC Ltd", "neha@example.com"),
            ("+919876543213", "Priya", "Singh", "PQR Corp", "priya@example.com"),
            ("+919876543214", "Vikram", "Rao", "XYZ Ltd", "vikram@example.com"),
        ]
        contacts = []
        for phone, first, last, company, email in contacts_data:
            contact = Contact(
                user_id=user.id, phone=phone, first_name=first, last_name=last,
                company=company, email=email,
            )
            db.add(contact)
            contacts.append(contact)
        db.flush()

        group_customers = ContactGroup(user_id=user.id, name="Customers", description="Active customers")
        group_leads = ContactGroup(user_id=user.id, name="Leads", description="Interested prospects")
        db.add_all([group_customers, group_leads])
        db.flush()
        group_customers.contacts = contacts[:3]
        group_leads.contacts = contacts[3:]

        template = MessageTemplate(
            user_id=user.id,
            name="Order update",
            message="Hi {{first_name}}, your order from {{company}} is ready for pickup. Thank you for choosing us!",
        )
        db.add(template)
        db.flush()

        campaign = create_campaign(
            db,
            user.id,
            "Order update — customers",
            template.message,
            RecipientTarget(scope="group", group_id=group_customers.id),
            "DRAFT",
        )
        report = build_validation_report(db, user.id, campaign)
        if report["valid"]:
            campaign.status = "READY"

        db.commit()
        print(f"Seeded demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print(f"Contacts: {len(contacts)} | Groups: 2 | Templates: 1 | Campaign: READY (validated)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
