"""Campaign business logic: recipient resolution, personalization,
validation and status transitions.

Phase 1 deliberately never sends anything. The only records created are
real ones: personalized recipients and SKIPPED/OPTED_OUT message-log
entries produced by validation.
"""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Campaign,
    CampaignRecipient,
    Contact,
    ContactGroup,
    MessageLog,
    OptOut,
)
from app.schemas.campaign import RecipientTarget
from app.services.audit_service import log_action
from app.services.phone_service import normalize_phone
from app.services.sms_service import MAX_GSM_SEGMENTS, analyze_message
from app.services.template_service import extract_variables, personalize

MAX_PREVIEWS = 20


class CampaignError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def resolve_recipient_contacts(
    db: Session, user_id: int, target: RecipientTarget
) -> list[Contact]:
    """Return the Contact rows a campaign targets."""
    if target.scope == "all":
        return list(
            db.scalars(select(Contact).where(Contact.user_id == user_id)).all()
        )
    if target.scope == "group":
        group = db.scalar(
            select(ContactGroup).where(
                ContactGroup.id == target.group_id, ContactGroup.user_id == user_id
            )
        )
        if not group:
            raise CampaignError("Group not found.", 404)
        return list(group.contacts)
    if target.scope == "contacts":
        ids = list(dict.fromkeys(target.contact_ids))  # dedupe, keep order
        contacts = db.scalars(
            select(Contact).where(
                Contact.user_id == user_id, Contact.id.in_(ids)
            )
        ).all()
        by_id = {c.id: c for c in contacts}
        return [by_id[i] for i in ids if i in by_id]
    return []


def _contact_phone_set(db: Session, user_id: int) -> set[str]:
    return set(db.scalars(select(OptOut.phone).where(OptOut.user_id == user_id)).all())


def build_validation_report(
    db: Session, user_id: int, campaign: Campaign
) -> dict:
    """Prepare recipients and produce a full validation report.

    Also (re)writes the real message-log entries for SKIPPED/OPTED_OUT
    recipients so the Message Logs page reflects actual operations.
    """
    if campaign.user_id != user_id:
        raise CampaignError("Campaign not found.", 404)

    template_analysis = extract_variables(campaign.message_template)
    unsupported = template_analysis.unsupported_variables
    sms = analyze_message(campaign.message_template)

    opt_out_phones = _contact_phone_set(db, user_id)
    seen_phones: dict[str, int] = {}

    # Resolve contacts by re-reading the stored target.
    target = RecipientTarget(
        scope=campaign.recipient_scope or "all",
        group_id=campaign.recipient_group_id,
        contact_ids=campaign.recipient_contact_ids or [],
    )
    contacts = resolve_recipient_contacts(db, user_id, target)

    recipients: list[CampaignRecipient] = []
    errors: list[dict] = []
    warnings: list[dict] = []
    infos: list[dict] = []
    previews: list[dict] = []

    counts = {
        "pending": 0,
        "invalid": 0,
        "duplicate": 0,
        "opted_out": 0,
        "empty": 0,
        "missing_fields": 0,
    }

    for contact in contacts:
        phone_result = normalize_phone(contact.phone)
        recipient = CampaignRecipient(campaign_id=campaign.id, contact_id=contact.id)

        if not phone_result.valid:
            recipient.status = "SKIPPED"
            recipient.error = "invalid phone number"
            counts["invalid"] += 1
        elif phone_result.normalized in opt_out_phones:
            recipient.status = "OPTED_OUT"
            recipient.error = "opted out"
            counts["opted_out"] += 1
        elif phone_result.normalized in seen_phones:
            recipient.status = "SKIPPED"
            recipient.error = f"duplicate phone (same as row for contact {seen_phones[phone_result.normalized]})"
            counts["duplicate"] += 1
        else:
            seen_phones[phone_result.normalized] = contact.id
            personalized, missing = personalize(campaign.message_template, contact)
            if not personalized.strip():
                recipient.status = "SKIPPED"
                recipient.error = "empty message after personalization"
                counts["empty"] += 1
            else:
                recipient.status = "PENDING"
                recipient.personalized_message = personalized
                counts["pending"] += 1
                if missing:
                    counts["missing_fields"] += 1

        recipients.append(recipient)

    if unsupported:
        errors.append(
            {
                "severity": "error",
                "category": "unsupported_variables",
                "message": (
                    "Unsupported template variables: "
                    + ", ".join(f"{{{{{v}}}}}" for v in unsupported)
                    + ". Supported variables are "
                    + ", ".join(f"{{{{{v}}}}}" for v in sorted(["first_name", "last_name", "phone", "email", "company", "notes"]))
                    + "."
                ),
                "count": len(unsupported),
            }
        )
    if counts["invalid"]:
        errors.append(
            {
                "severity": "error",
                "category": "invalid_phone",
                "message": f"{counts['invalid']} recipient(s) have invalid phone numbers and will be skipped.",
                "count": counts["invalid"],
            }
        )
    if counts["empty"]:
        errors.append(
            {
                "severity": "error",
                "category": "empty_message",
                "message": f"{counts['empty']} recipient(s) produced an empty message after personalization.",
                "count": counts["empty"],
            }
        )
    if sms.exceed_limit:
        errors.append(
            {
                "severity": "error",
                "category": "sms_length",
                "message": f"Message spans {sms.segments} SMS segments (limit {MAX_GSM_SEGMENTS}). Shorten the template.",
                "count": 1,
            }
        )

    if counts["opted_out"]:
        warnings.append(
            {
                "severity": "warning",
                "category": "opted_out",
                "message": f"{counts['opted_out']} recipient(s) will be skipped because they are opted out.",
                "count": counts["opted_out"],
            }
        )
    if counts["duplicate"]:
        warnings.append(
            {
                "severity": "warning",
                "category": "duplicate",
                "message": f"{counts['duplicate']} recipient(s) are duplicates within the campaign and will be skipped.",
                "count": counts["duplicate"],
            }
        )
    if counts["missing_fields"]:
        warnings.append(
            {
                "severity": "warning",
                "category": "missing_fields",
                "message": f"{counts['missing_fields']} recipient(s) are missing personalization fields (e.g. company); empty values are left blank.",
                "count": counts["missing_fields"],
            }
        )
    if sms.truncated:
        warnings.append(
            {
                "severity": "warning",
                "category": "sms_length",
                "message": f"Message uses {sms.segments} SMS segments ({sms.encoding}, {sms.characters} chars). Multiple segments may be charged separately.",
                "count": 1,
            }
        )

    for recipient in recipients:
        if len(previews) >= MAX_PREVIEWS:
            break
        contact = next((c for c in contacts if c.id == recipient.contact_id), None)
        if contact is None:
            continue
        previews.append(
            {
                "contact_id": contact.id,
                "name": f"{contact.first_name or ''} {contact.last_name or ''}".strip()
                or contact.phone,
                "phone": contact.phone,
                "preview": recipient.personalized_message,
                "status": recipient.status,
                "error": recipient.error,
            }
        )

    # Message logs reflect only real operations: skips and opt-outs.
    # Recipients/message-logs from a previous validation run are replaced.
    db.execute(delete(MessageLog).where(MessageLog.campaign_id == campaign.id))
    db.execute(
        delete(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign.id)
    )
    for recipient in recipients:
        db.add(recipient)
        if recipient.status in ("SKIPPED", "OPTED_OUT"):
            db.add(
                MessageLog(
                    user_id=user_id,
                    campaign_id=campaign.id,
                    contact_id=recipient.contact_id,
                    message=recipient.personalized_message,
                    status=recipient.status,
                    error=recipient.error,
                )
            )
    db.flush()

    report = {
        "campaign_id": campaign.id,
        "valid": not errors and not unsupported,
        "total_recipients": len(contacts),
        "pending": counts["pending"],
        "skipped_invalid_phone": counts["invalid"],
        "skipped_duplicate": counts["duplicate"],
        "skipped_opted_out": counts["opted_out"],
        "skipped_empty_message": counts["empty"],
        "skipped_missing_fields": counts["missing_fields"],
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "previews": previews,
    }

    log_action(
        db,
        user_id,
        "campaign.validated",
        "campaign",
        campaign.id,
        {"total": len(contacts), "pending": counts["pending"]},
    )
    return report


def create_campaign(
    db: Session,
    user_id: int,
    name: str,
    message_template: str,
    target: RecipientTarget,
    status: str,
    scheduled_at=None,
) -> Campaign:
    contacts = resolve_recipient_contacts(db, user_id, target)
    campaign = Campaign(
        user_id=user_id,
        name=name,
        message_template=message_template,
        status=status,
        scheduled_at=scheduled_at,
        recipient_scope=target.scope,
        recipient_group_id=target.group_id if target.scope == "group" else None,
        recipient_contact_ids=(
            list(dict.fromkeys(target.contact_ids)) if target.scope == "contacts" else None
        ),
    )
    db.add(campaign)
    db.flush()

    for contact in contacts:
        db.add(CampaignRecipient(campaign_id=campaign.id, contact_id=contact.id, status="PENDING"))

    log_action(db, user_id, "campaign.created", "campaign", campaign.id, {"status": status})
    return campaign


def update_campaign(
    db: Session,
    user_id: int,
    campaign: Campaign,
    fields: dict,
) -> Campaign:
    if campaign.user_id != user_id:
        raise CampaignError("Campaign not found.", 404)

    editable_fields = fields.get("name") or fields.get("message_template") or fields.get("recipients")
    if editable_fields and campaign.status != "DRAFT":
        raise CampaignError(
            "Only DRAFT campaigns can be edited. Duplicate the campaign instead.",
            409,
        )

    if fields.get("status") and fields["status"] != campaign.status:
        new_status = fields["status"]
        allowed = _allowed_transitions(campaign.status)
        if new_status not in allowed:
            raise CampaignError(
                f"Cannot move campaign from {campaign.status} to {new_status}.",
                409,
            )
        if new_status == "READY":
            # READY is only reachable via explicit validation in Phase 1.
            raise CampaignError(
                "Validate the campaign first; validation sets it to READY when it passes.",
                409,
            )

    for key in ("name", "message_template", "scheduled_at"):
        if key in fields and fields[key] is not None:
            setattr(campaign, key, fields[key])

    if fields.get("recipients") is not None:
        target: RecipientTarget = fields["recipients"]
        campaign.recipient_scope = target.scope
        campaign.recipient_group_id = target.group_id if target.scope == "group" else None
        campaign.recipient_contact_ids = (
            list(dict.fromkeys(target.contact_ids)) if target.scope == "contacts" else None
        )
        # Any edit to recipients invalidates prepared recipients.
        db.execute(
            delete(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign.id)
        )
        contacts = resolve_recipient_contacts(db, user_id, target)
        for contact in contacts:
            db.add(CampaignRecipient(campaign_id=campaign.id, contact_id=contact.id, status="PENDING"))

    log_action(db, user_id, "campaign.updated", "campaign", campaign.id, {"status": campaign.status})
    return campaign


def mark_ready(db: Session, user_id: int, campaign: Campaign) -> Campaign:
    """Validate and promote a campaign to READY (nothing is sent)."""
    if campaign.user_id != user_id:
        raise CampaignError("Campaign not found.", 404)
    if campaign.status != "DRAFT":
        raise CampaignError("Only DRAFT campaigns can be marked READY.", 409)

    report = build_validation_report(db, user_id, campaign)
    if not report["valid"]:
        raise CampaignError(
            "Campaign validation failed. Fix the errors shown in the validation report.",
            422,
        )
    campaign.status = "READY"
    log_action(db, user_id, "campaign.ready", "campaign", campaign.id)
    return campaign


def duplicate_campaign(db: Session, user_id: int, campaign: Campaign) -> Campaign:
    if campaign.user_id != user_id:
        raise CampaignError("Campaign not found.", 404)
    copy = Campaign(
        user_id=user_id,
        name=f"{campaign.name} (copy)",
        message_template=campaign.message_template,
        status="DRAFT",
        recipient_scope=campaign.recipient_scope,
        recipient_group_id=campaign.recipient_group_id,
        recipient_contact_ids=campaign.recipient_contact_ids,
    )
    db.add(copy)
    db.flush()
    contacts = resolve_recipient_contacts(
        db,
        user_id,
        RecipientTarget(
            scope=copy.recipient_scope or "all",
            group_id=copy.recipient_group_id,
            contact_ids=copy.recipient_contact_ids or [],
        ),
    )
    for contact in contacts:
        db.add(CampaignRecipient(campaign_id=copy.id, contact_id=contact.id, status="PENDING"))
    log_action(db, user_id, "campaign.duplicated", "campaign", copy.id, {"from": campaign.id})
    return copy


def pause_campaign(db: Session, user_id: int, campaign: Campaign) -> Campaign:
    if campaign.user_id != user_id:
        raise CampaignError("Campaign not found.", 404)
    if campaign.status not in ("READY", "RUNNING", "SCHEDULED"):
        raise CampaignError(f"Cannot pause a campaign in status {campaign.status}.", 409)
    campaign.status = "PAUSED"
    log_action(db, user_id, "campaign.paused", "campaign", campaign.id)
    return campaign


def resume_campaign(db: Session, user_id: int, campaign: Campaign) -> Campaign:
    if campaign.user_id != user_id:
        raise CampaignError("Campaign not found.", 404)
    if campaign.status != "PAUSED":
        raise CampaignError(f"Cannot resume a campaign in status {campaign.status}.", 409)
    campaign.status = "READY"
    log_action(db, user_id, "campaign.resumed", "campaign", campaign.id)
    return campaign


def cancel_campaign(db: Session, user_id: int, campaign: Campaign) -> Campaign:
    if campaign.user_id != user_id:
        raise CampaignError("Campaign not found.", 404)
    if campaign.status in ("COMPLETED", "CANCELLED"):
        raise CampaignError(f"Cannot cancel a campaign in status {campaign.status}.", 409)
    campaign.status = "CANCELLED"
    log_action(db, user_id, "campaign.cancelled", "campaign", campaign.id)
    return campaign


def _allowed_transitions(current: str) -> set[str]:
    transitions = {
        "DRAFT": {"READY", "CANCELLED"},
        "READY": {"PAUSED", "CANCELLED"},
        "SCHEDULED": {"PAUSED", "CANCELLED"},
        "RUNNING": {"PAUSED", "CANCELLED"},
        "PAUSED": {"READY", "CANCELLED"},
        "COMPLETED": set(),
        "CANCELLED": set(),
    }
    return transitions.get(current, set())


def campaign_summary(db: Session, campaign: Campaign) -> dict:
    """Aggregate recipient counts for a campaign."""
    rows = db.execute(
        select(CampaignRecipient.status, func.count())
        .where(CampaignRecipient.campaign_id == campaign.id)
        .group_by(CampaignRecipient.status)
    ).all()
    counts = {status: n for status, n in rows}
    return {
        "recipient_count": sum(counts.values()),
        "sent_count": counts.get("SENT", 0),
        "failed_count": counts.get("FAILED", 0),
        "pending_count": counts.get("PENDING", 0),
        "skipped_count": counts.get("SKIPPED", 0),
        "opted_out_count": counts.get("OPTED_OUT", 0),
    }
