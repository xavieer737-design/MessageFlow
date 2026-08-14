"""Shared pytest fixtures.

Tests run against an in-memory SQLite database (fast, isolated) while
the application itself targets PostgreSQL; the SQLAlchemy models are
portable across both.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("RATE_LIMIT_AUTH", "1000/minute")
os.environ.setdefault("RATE_LIMIT_IMPORT", "1000/minute")
os.environ.setdefault("UPLOAD_DIR", "uploads-test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _make_client(db_session):
    """A fresh TestClient whose API calls use the given session."""
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def client(db):
    """An unauthenticated TestClient."""
    with _make_client(db) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(client: TestClient, email: str = "user@example.com", password: str = "passw0rd1") -> dict:
    response = client.post(
        "/api/auth/register",
        json={"name": "Test User", "email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def user_client(db):
    """An authenticated TestClient for user A (fresh cookie jar)."""
    with _make_client(db) as test_client:
        register(test_client)
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def second_user_client(db):
    """An authenticated TestClient for user B (fresh cookie jar)."""
    with _make_client(db) as test_client:
        register(test_client, email="other@example.com")
        yield test_client
    app.dependency_overrides.clear()
