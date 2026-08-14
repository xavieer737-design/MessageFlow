import io
import csv
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.ratelimit import limiter
from app.db.session import get_db
from app.models import Contact, OptOut, User
from app.repositories.contact_repo import ContactRepository
from app.schemas.contact import ContactCreate, ContactListOut, ContactOut, ContactUpdate
from app.services.audit_service import log_action
from app.services.import_service import (
    ImportError,
    confirm_import,
    load_upload,
    parse_upload,
    suggested_mapping,
    validate_rows,
)
from app.services.phone_service import normalize_phone

router = APIRouter(prefix="/contacts", tags=["contacts"])

PAGE_SIZE_LIMIT = 200


def _get_contact_or_404(db: Session, user_id: int, contact_id: int) -> Contact:
    contact = ContactRepository(db).get(user_id, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


def _opted_out_phones(db: Session, user_id: int) -> set[str]:
    return set(db.scalars(select(OptOut.phone).where(OptOut.user_id == user_id)).all())


def _with_optout_flag(db: Session, user_id: int, contacts: list[Contact]) -> list[dict]:
    opted_out = _opted_out_phones(db, user_id)
    return [
        {
            **{c: getattr(contact, c) for c in (
                "id", "user_id", "phone", "first_name", "last_name", "email",
                "company", "notes", "custom_fields", "groups", "created_at", "updated_at",
            )},
            "opted_out": contact.phone in opted_out,
        }
        for contact in contacts
    ]


@router.get("", response_model=ContactListOut)
def list_contacts(
    search: str = "",
    group_id: int | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=PAGE_SIZE_LIMIT),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = ContactRepository(db).list(
        user.id, search, group_id, sort_by, sort_dir, page, page_size
    )
    pages = max(1, -(-total // page_size))
    return {
        "items": _with_optout_flag(db, user.id, items),
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.post("", response_model=ContactOut, status_code=201)
def create_contact(
    payload: ContactCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = normalize_phone(payload.phone)
    if not result.valid:
        raise HTTPException(status_code=422, detail=f"Invalid phone number: {result.reason}")
    repo = ContactRepository(db)
    if repo.get_by_phone(user.id, result.normalized):
        raise HTTPException(status_code=409, detail="A contact with this phone already exists")
    contact = repo.create(
        user.id,
        result.normalized,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        company=payload.company,
        notes=payload.notes,
        custom_fields=payload.custom_fields,
        group_ids=payload.group_ids,
    )
    log_action(db, user.id, "contact.created", "contact", contact.id)
    db.commit()
    db.refresh(contact)
    return contact


@router.get("/export")
def export_contacts(
    export_format: str = Query("csv", alias="format", pattern="^(csv|xlsx)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contacts, _ = ContactRepository(db).list(user.id, page_size=100_000)
    rows = [
        [c.phone, c.first_name or "", c.last_name or "", c.email or "", c.company or "", c.notes or ""]
        for c in contacts
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if export_format == "xlsx":
        import pandas as pd

        buffer = io.BytesIO()
        pd.DataFrame(
            rows, columns=["phone", "first_name", "last_name", "email", "company", "notes"]
        ).to_excel(buffer, index=False)
        buffer.seek(0)
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="contacts-{stamp}.xlsx"'},
        )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["phone", "first_name", "last_name", "email", "company", "notes"])
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="contacts-{stamp}.csv"'},
    )


@router.post("/bulk-delete", status_code=204)
def bulk_delete_contacts(
    contact_ids: list[int],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not contact_ids:
        raise HTTPException(status_code=422, detail="No contacts selected")
    repo = ContactRepository(db)
    for contact_id in contact_ids:
        contact = repo.get(user.id, contact_id)
        if contact:
            repo.delete(contact)
    log_action(db, user.id, "contact.bulk_deleted", details={"count": len(contact_ids)})
    db.commit()


# --- Import ---


@router.post("/import/upload")
@limiter.limit(settings.RATE_LIMIT_IMPORT)
def import_upload(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Step 1: upload + parse. Returns detected columns and suggested mapping."""
    content = file.file.read()
    try:
        staged = parse_upload(content, file.filename or "upload", user.id)
    except ImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    mapping = suggested_mapping(staged.columns, staged.rows)
    rows_with_status = validate_rows(db, user.id, staged.rows, mapping)
    sample_rows = [
        {**r.values, "_status": r.status, "_errors": r.errors, "_warnings": r.warnings}
        for r in rows_with_status.rows[:10]
    ]
    return {
        "file_id": staged.file_id,
        "filename": staged.filename,
        "source": staged.source,
        "columns": staged.columns,
        "suggested_mapping": mapping,
        "total_rows": staged.total_rows,
        "summary": {
            "valid": rows_with_status.valid,
            "invalid": rows_with_status.invalid,
            "duplicates": rows_with_status.duplicates,
            "opted_out": rows_with_status.opted_out,
        },
        "sample_rows": sample_rows,
    }


@router.post("/import/validate")
def import_validate(
    file_id: str = Form(...),
    mapping: str = Form(...),  # JSON object: {source_column: target}
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Step 2: re-validate with the user-chosen column mapping."""
    import json

    try:
        mapping_dict = json.loads(mapping)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid mapping payload")

    try:
        payload = load_upload(user.id, file_id)
    except ImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    summary = validate_rows(db, user.id, payload["rows"], mapping_dict)
    return {
        "file_id": file_id,
        "summary": {
            "total": summary.total,
            "valid": summary.valid,
            "invalid": summary.invalid,
            "duplicates": summary.duplicates,
            "opted_out": summary.opted_out,
        },
        "rows": [
            {
                "row_number": r.row_number,
                "values": r.values,
                "status": r.status,
                "errors": r.errors,
                "warnings": r.warnings,
            }
            for r in summary.rows
        ],
    }


@router.post("/import/confirm")
def import_confirm(
    file_id: str = Form(...),
    mapping: str = Form(...),  # JSON object: {source_column: target}
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Step 3: import the valid rows and report what happened."""
    import json

    try:
        mapping_dict = json.loads(mapping)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid mapping payload")

    try:
        result = confirm_import(db, user.id, file_id, mapping_dict)
    except ImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    log_action(
        db,
        user.id,
        "contact.imported",
        details={"imported": result["imported"], "total": result["total"]},
    )
    db.commit()
    return result


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contact = _get_contact_or_404(db, user.id, contact_id)
    return _with_optout_flag(db, user.id, [contact])[0]


@router.put("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contact = _get_contact_or_404(db, user.id, contact_id)
    result = normalize_phone(payload.phone)
    if not result.valid:
        raise HTTPException(status_code=422, detail=f"Invalid phone number: {result.reason}")
    repo = ContactRepository(db)
    existing = repo.get_by_phone(user.id, result.normalized)
    if existing and existing.id != contact.id:
        raise HTTPException(status_code=409, detail="A contact with this phone already exists")
    payload.phone = result.normalized
    contact = repo.update(user.id, contact, payload)
    log_action(db, user.id, "contact.updated", "contact", contact.id)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=204)
def delete_contact(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contact = _get_contact_or_404(db, user.id, contact_id)
    ContactRepository(db).delete(contact)
    log_action(db, user.id, "contact.deleted", "contact", contact_id)
    db.commit()


