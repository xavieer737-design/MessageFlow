import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories.optout_repo import OptOutRepository
from app.schemas.optout import (
    OptOutBulkCreate,
    OptOutBulkResult,
    OptOutCreate,
    OptOutListOut,
    OptOutOut,
)
from app.services.audit_service import log_action
from app.services.import_service import ImportError, parse_upload
from app.services.phone_service import normalize_phone

router = APIRouter(prefix="/optouts", tags=["opt-outs"])


def _normalize_or_422(phone: str) -> str:
    result = normalize_phone(phone)
    if not result.valid:
        raise HTTPException(status_code=422, detail=f"Invalid phone number: {result.reason}")
    return result.normalized


@router.get("", response_model=OptOutListOut)
def list_optouts(
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = OptOutRepository(db).list(user.id, search, page, page_size)
    pages = max(1, -(-total // page_size))
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


@router.post("", response_model=OptOutOut, status_code=201)
def create_optout(
    payload: OptOutCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    phone = _normalize_or_422(payload.phone)
    repo = OptOutRepository(db)
    if repo.get_by_phone(user.id, phone):
        raise HTTPException(status_code=409, detail="This number is already on the opt-out list")
    entry = repo.create(user.id, phone, payload.reason)
    log_action(db, user.id, "optout.created", "optout", entry.id, {"phone": phone})
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/bulk", response_model=OptOutBulkResult)
def bulk_create_optouts(
    payload: OptOutBulkCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = OptOutRepository(db)
    existing = {entry.phone for entry in repo.list(user.id, page_size=100_000)[0]}
    imported = 0
    duplicates = 0
    skipped_invalid: list[str] = []
    for raw in payload.phones:
        result = normalize_phone(raw)
        if not result.valid:
            skipped_invalid.append(raw)
            continue
        if result.normalized in existing:
            duplicates += 1
            continue
        repo.create(user.id, result.normalized)
        existing.add(result.normalized)
        imported += 1
    log_action(db, user.id, "optout.bulk_created", details={"imported": imported})
    db.commit()
    return OptOutBulkResult(imported=imported, skipped_invalid=skipped_invalid, duplicates=duplicates)


@router.post("/import")
def import_optouts(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import opt-out numbers from CSV/XLSX (first column = phone)."""
    try:
        staged = parse_upload(file.file.read(), file.filename or "upload", user.id)
    except ImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    repo = OptOutRepository(db)
    existing = {entry.phone for entry in repo.list(user.id, page_size=100_000)[0]}
    imported = 0
    duplicates = 0
    skipped_invalid: list[str] = []
    for row in staged.rows:
        raw = next(iter(row.values()), "")
        result = normalize_phone(raw)
        if not result.valid:
            skipped_invalid.append(raw or "(empty)")
            continue
        if result.normalized in existing:
            duplicates += 1
            continue
        repo.create(user.id, result.normalized, reason="imported list")
        existing.add(result.normalized)
        imported += 1
    log_action(db, user.id, "optout.imported", details={"imported": imported})
    db.commit()
    return OptOutBulkResult(imported=imported, skipped_invalid=skipped_invalid, duplicates=duplicates)


@router.get("/export")
def export_optouts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entries = OptOutRepository(db).list(user.id, page_size=100_000)[0]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["phone", "reason", "created_at"])
    for entry in entries:
        writer.writerow([entry.phone, entry.reason or "", entry.created_at.isoformat()])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="opt-outs.csv"'},
    )


@router.delete("/{optout_id}", status_code=204)
def delete_optout(
    optout_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = OptOutRepository(db)
    entry = repo.get(user.id, optout_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Opt-out entry not found")
    repo.delete(entry)
    log_action(db, user.id, "optout.deleted", "optout", optout_id)
    db.commit()
