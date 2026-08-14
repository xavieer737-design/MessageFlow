"""Shared FastAPI dependencies."""

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import User

ACCESS_COOKIE = "mf_access"
REFRESH_COOKIE = "mf_refresh"


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    mf_access: str | None = Cookie(default=None),
) -> User:
    """Resolve the authenticated user from cookie or Bearer token."""
    token = mf_access or _bearer_token(request)
    payload = decode_token(token, "access") if token else None
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
