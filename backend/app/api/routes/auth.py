from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import ACCESS_COOKIE, REFRESH_COOKIE, get_current_user
from app.core.config import settings
from app.core.ratelimit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UpdateProfileRequest,
    UserOut,
)
from app.services.audit_service import log_action
from app.services.auth_service import AuthError, authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, user_id: int) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=create_access_token(str(user_id)),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=create_refresh_token(str(user_id)),
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/api/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def register(request: Request, payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    try:
        user = register_user(db, payload.name, payload.email, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    log_action(db, user.id, "auth.register", "user", user.id)
    db.commit()
    db.refresh(user)
    _set_auth_cookies(response, user.id)
    return user


@router.post("/login", response_model=UserOut)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login(request: Request, payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    try:
        user = authenticate_user(db, payload.email, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    log_action(db, user.id, "auth.login", "user", user.id)
    db.commit()
    _set_auth_cookies(response, user.id)
    return user


@router.post("/refresh", response_model=UserOut)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    mf_refresh: str | None = Cookie(default=None),
):
    payload = decode_token(mf_refresh or "", "refresh") if mf_refresh else None
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    _set_auth_cookies(response, user.id)
    return user


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    log_action(db, user.id, "auth.logout", "user", user.id)
    db.commit()
    _clear_auth_cookies(response)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.put("/me", response_model=UserOut)
def update_profile(
    payload: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.name = payload.name.strip()
    log_action(db, user.id, "profile.updated", "user", user.id)
    db.commit()
    db.refresh(user)
    return user


@router.put("/me/password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    log_action(db, user.id, "auth.password_changed", "user", user.id)
    db.commit()
    return MessageResponse(message="Password updated")
