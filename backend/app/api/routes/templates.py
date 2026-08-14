from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.repositories.template_repo import TemplateRepository
from app.schemas.template import (
    TemplateCreate,
    TemplateOut,
    TemplatePreviewOut,
    TemplatePreviewRequest,
    TemplateUpdate,
)
from app.services.audit_service import log_action
from app.services.template_service import extract_variables, preview

router = APIRouter(prefix="/templates", tags=["templates"])


def _get_template_or_404(db: Session, user_id: int, template_id: int):
    template = TemplateRepository(db).get(user_id, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.get("", response_model=list[TemplateOut])
def list_templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return TemplateRepository(db).list(user.id)


@router.post("", response_model=TemplateOut, status_code=201)
def create_template(
    payload: TemplateCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    unsupported = extract_variables(payload.message).unsupported_variables
    if unsupported:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported variables: {', '.join(f'{{{{{v}}}}}' for v in unsupported)}",
        )
    template = TemplateRepository(db).create(user.id, payload.name.strip(), payload.message)
    log_action(db, user.id, "template.created", "template", template.id)
    db.commit()
    db.refresh(template)
    return template


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(
    template_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_template_or_404(db, user.id, template_id)


@router.put("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: int,
    payload: TemplateUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = _get_template_or_404(db, user.id, template_id)
    unsupported = extract_variables(payload.message).unsupported_variables
    if unsupported:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported variables: {', '.join(f'{{{{{v}}}}}' for v in unsupported)}",
        )
    template = TemplateRepository(db).update(template, payload.name.strip(), payload.message)
    log_action(db, user.id, "template.updated", "template", template.id)
    db.commit()
    db.refresh(template)
    return template


@router.post("/{template_id}/duplicate", response_model=TemplateOut, status_code=201)
def duplicate_template(
    template_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = _get_template_or_404(db, user.id, template_id)
    copy = TemplateRepository(db).create(user.id, f"{template.name} (copy)", template.message)
    log_action(db, user.id, "template.duplicated", "template", copy.id, {"from": template.id})
    db.commit()
    db.refresh(copy)
    return copy


@router.post("/preview", response_model=TemplatePreviewOut)
def preview_template(
    payload: TemplatePreviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del user, db  # preview is stateless; kept auth-protected
    values = {
        "first_name": payload.first_name or "",
        "last_name": payload.last_name or "",
        "phone": payload.phone or "",
        "email": payload.email or "",
        "company": payload.company or "",
        "notes": payload.notes or "",
    }
    personalized, missing = preview(payload.message, values)
    analysis = extract_variables(payload.message)
    return TemplatePreviewOut(
        preview=personalized,
        variables_found=analysis.variables_found,
        variables_missing=list(dict.fromkeys(missing)),
    )


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = _get_template_or_404(db, user.id, template_id)
    TemplateRepository(db).delete(template)
    log_action(db, user.id, "template.deleted", "template", template_id)
    db.commit()
