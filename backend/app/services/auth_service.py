"""Authentication business logic: register, login, tokens."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import User


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def register_user(db: Session, name: str, email: str, password: str) -> User:
    email = email.lower().strip()
    if get_user_by_email(db, email):
        raise AuthError("An account with this email already exists.", 409)
    user = User(name=name.strip(), email=email, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password.", 401)
    return user
