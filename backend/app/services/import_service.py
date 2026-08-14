"""CSV / XLSX contact import pipeline.

Flow: upload -> parse -> detect columns -> map -> validate -> confirm.

- Files are parsed with pandas (openpyxl for XLSX).
- Every row is validated (phone normalization, duplicates, opt-outs);
  nothing is silently discarded - the UI shows full breakdowns.
- Uploaded files are staged on disk under UPLOAD_DIR keyed by a random
  file id bound to the owning user, then removed after confirm.
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Contact, OptOut
from app.services.phone_service import PhoneValidationResult, normalize_phone

ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
MAX_ROWS = 50_000

# Canonical field names a source column can map to.
CANONICAL_FIELDS = {
    "phone": "phone",
    "first_name": "first_name",
    "last_name": "last_name",
    "email": "email",
    "company": "company",
    "notes": "notes",
}

# Known aliases -> canonical field. Detection is case/space/underscore
# insensitive ("First Name" -> first_name).
COLUMN_ALIASES: dict[str, str] = {
    "phone": "phone",
    "phonenumber": "phone",
    "phonenumber1": "phone",
    "mobile": "phone",
    "mobilenumber": "phone",
    "mobilephone": "phone",
    "cell": "phone",
    "cellphone": "phone",
    "tel": "phone",
    "telephone": "phone",
    "contactnumber": "phone",
    "firstname": "first_name",
    "first": "first_name",
    "fname": "first_name",
    "givenname": "first_name",
    "lastname": "last_name",
    "last": "last_name",
    "lname": "last_name",
    "surname": "last_name",
    "familyname": "last_name",
    "email": "email",
    "emailaddress": "email",
    "e-mail": "email",
    "mail": "email",
    "company": "company",
    "organization": "company",
    "organisation": "company",
    "business": "company",
    "firm": "company",
    "notes": "notes",
    "note": "notes",
    "remarks": "notes",
    "comment": "notes",
    "comments": "notes",
    # Combined name columns are special-cased (see detect_columns).
    "name": "__name__",
    "fullname": "__name__",
    "fullname1": "__name__",
    "contactname": "__name__",
}

SKIP = "__skip__"

NAME_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z'.\- ]+$")


@dataclass
class ParsedFile:
    file_id: str
    filename: str
    source: str  # csv | xlsx
    columns: list[str]
    rows: list[dict]  # raw string values keyed by original column name
    total_rows: int
    staged_at: datetime


@dataclass
class RowValidation:
    row_number: int
    values: dict
    phone: str = ""
    normalized_phone: str | None = None
    status: str = "valid"  # valid | invalid | duplicate | opted_out
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ValidationSummary:
    rows: list[RowValidation]
    total: int
    valid: int
    invalid: int
    duplicates: int
    opted_out: int


class ImportError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _upload_root() -> Path:
    root = Path(settings.UPLOAD_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def parse_upload(file_bytes: bytes, filename: str, user_id: int) -> ParsedFile:
    """Parse an uploaded CSV or XLSX file into a staged ParsedFile."""
    name = (filename or "upload").lower()
    ext = Path(name).suffix
    if ext not in ALLOWED_EXTENSIONS:
        raise ImportError("Unsupported file type. Upload a .csv or .xlsx file.")

    if len(file_bytes) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise ImportError(f"File exceeds the {settings.MAX_UPLOAD_MB} MB size limit.")

    try:
        if ext == ".csv":
            df = pd.read_csv(pd.io.common.BytesIO(file_bytes), dtype=str, keep_default_na=False)
            source = "csv"
        else:
            df = pd.read_excel(pd.io.common.BytesIO(file_bytes), dtype=str, keep_default_na=False)
            source = "xlsx"
    except Exception as exc:  # noqa: BLE001 - surface a friendly message
        raise ImportError(f"Could not parse file: {exc}") from exc

    df = df.dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]

    if df.empty or len(df.columns) == 0:
        raise ImportError("The file contains no columns or data.")

    if len(df) > MAX_ROWS:
        raise ImportError(f"File has {len(df)} rows; the limit is {MAX_ROWS}.")

    rows = [
        {col: "" if pd.isna(v) else str(v).strip() for col, v in record.items()}
        for record in df.to_dict(orient="records")
    ]

    file_id = uuid.uuid4().hex
    staged = ParsedFile(
        file_id=file_id,
        filename=filename or "upload",
        source=source,
        columns=list(df.columns),
        rows=rows,
        total_rows=len(rows),
        staged_at=datetime.now(timezone.utc),
    )

    payload = {
        "file_id": file_id,
        "filename": staged.filename,
        "source": source,
        "columns": staged.columns,
        "rows": staged.rows,
        "total_rows": staged.total_rows,
        "staged_at": staged.staged_at.isoformat(),
        "user_id": user_id,
    }
    ( _upload_root() / f"{user_id}_{file_id}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return staged


def load_upload(user_id: int, file_id: str) -> dict:
    path = _upload_root() / f"{user_id}_{file_id}.json"
    if not path.exists():
        raise ImportError("Upload session expired or not found. Please upload the file again.", 404)
    return json.loads(path.read_text(encoding="utf-8"))


def delete_upload(user_id: int, file_id: str) -> None:
    path = _upload_root() / f"{user_id}_{file_id}.json"
    if path.exists():
        path.unlink()


def detect_columns(columns: list[str]) -> dict[str, str]:
    """Suggest a mapping from source columns to canonical fields.

    Combined "name" columns are mapped to first_name when the values
    actually look like names (alpha tokens); users can always override.
    """
    mapping: dict[str, str] = {}
    for col in columns:
        key = re.sub(r"[^a-zA-Z0-9]", "", col).lower()
        target = COLUMN_ALIASES.get(key, SKIP)
        mapping[col] = target
    return mapping


def _looks_like_name(rows: list[dict], col: str, sample: int = 20) -> bool:
    values = [r.get(col, "") for r in rows[:sample] if r.get(col, "").strip()]
    if not values:
        return False
    named = sum(1 for v in values if NAME_TOKEN_RE.match(v.strip()))
    return named / len(values) >= 0.8


def suggested_mapping(columns: list[str], rows: list[dict]) -> dict[str, str]:
    """Like detect_columns, but resolves __name__ using the row content."""
    mapping = detect_columns(columns)
    for col, target in list(mapping.items()):
        if target == "__name__":
            mapping[col] = "first_name" if _looks_like_name(rows, col) else SKIP
    return mapping


def _source_for(mapping: dict[str, str]) -> dict[str, str]:
    """Reverse the mapping: canonical target -> source column name."""
    return {tgt: src for src, tgt in mapping.items() if tgt != SKIP}


def validate_rows(
    db: Session,
    user_id: int,
    rows: list[dict],
    mapping: dict[str, str],
) -> ValidationSummary:
    """Validate every row: phone, duplicates (in-file + existing), opt-outs.

    Rows are marked but never silently dropped.
    """
    existing_phones = set(
        db.scalars(select(Contact.phone).where(Contact.user_id == user_id)).all()
    )
    opt_out_phones = set(
        db.scalars(select(OptOut.phone).where(OptOut.user_id == user_id)).all()
    )
    source_for = _source_for(mapping)

    summary = ValidationSummary(rows=[], total=len(rows), valid=0, invalid=0, duplicates=0, opted_out=0)
    seen_in_file: dict[str, int] = {}

    for idx, raw_row in enumerate(rows, start=2):  # row 1 is the header
        validation = RowValidation(row_number=idx, values=raw_row)

        phone_raw = raw_row.get(source_for.get("phone", ""), "").strip()

        if not phone_raw:
            validation.status = "invalid"
            validation.errors.append("missing phone number")
            summary.invalid += 1
            summary.rows.append(validation)
            continue

        result: PhoneValidationResult = normalize_phone(phone_raw)
        validation.phone = phone_raw
        if not result.valid:
            validation.status = "invalid"
            validation.errors.append(result.reason or "invalid phone number")
            summary.invalid += 1
            summary.rows.append(validation)
            continue

        validation.normalized_phone = result.normalized
        duplicate_of = seen_in_file.get(result.normalized)
        if duplicate_of is not None:
            validation.status = "duplicate"
            validation.errors.append(f"duplicate of row {duplicate_of}")
            summary.duplicates += 1
            summary.rows.append(validation)
            continue
        if result.normalized in existing_phones:
            validation.status = "duplicate"
            validation.errors.append("already in your contacts")
            summary.duplicates += 1
            summary.rows.append(validation)
            continue
        if result.normalized in opt_out_phones:
            validation.status = "opted_out"
            validation.errors.append("number is on your opt-out list")
            summary.opted_out += 1
            summary.rows.append(validation)
            continue

        seen_in_file[result.normalized] = idx

        email = raw_row.get(source_for.get("email", ""), "").strip()
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            validation.warnings.append(f"email '{email}' does not look valid")

        validation.status = "valid"
        summary.valid += 1
        summary.rows.append(validation)

    return summary


def confirm_import(db: Session, user_id: int, file_id: str, mapping: dict[str, str]) -> dict:
    """Import the valid rows of a staged upload. Returns result counts."""
    payload = load_upload(user_id, file_id)
    rows = payload["rows"]

    unknown = [c for c in mapping if c not in payload["columns"]]
    if unknown:
        raise ImportError(f"Mapping references unknown columns: {', '.join(unknown)}")

    summary = validate_rows(db, user_id, rows, mapping)
    source_for = _source_for(mapping)

    def cell(validation: RowValidation, target: str) -> str | None:
        value = validation.values.get(source_for.get(target, ""), "")
        return value.strip() or None

    created = 0
    for validation in summary.rows:
        if validation.status != "valid" or not validation.normalized_phone:
            continue
        contact = Contact(
            user_id=user_id,
            phone=validation.normalized_phone,
            first_name=cell(validation, "first_name"),
            last_name=cell(validation, "last_name"),
            email=cell(validation, "email"),
            company=cell(validation, "company"),
            notes=cell(validation, "notes"),
        )
        db.add(contact)
        created += 1

    db.flush()
    delete_upload(user_id, file_id)

    return {
        "total": summary.total,
        "valid": summary.valid,
        "invalid": summary.invalid,
        "duplicates": summary.duplicates,
        "opted_out": summary.opted_out,
        "imported": created,
    }
