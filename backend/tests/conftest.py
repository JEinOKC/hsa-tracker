"""Test fixtures for HSA Tracker backend tests.

Environment variables MUST be set before any app imports because
Settings (config.py:68) and database.py are instantiated at module level.
"""

import os

# Set test env vars before any app imports
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite:///")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_S3_BUCKET", "test-bucket")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-not-for-production")
os.environ.setdefault("WEBAUTHN_RP_ID", "localhost")
os.environ.setdefault("WEBAUTHN_RP_NAME", "HSA Tracker Test")
os.environ.setdefault("WEBAUTHN_ORIGIN", "http://localhost:3001")

import uuid as uuid_module

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Make PostgreSQL UUID type work with SQLite:
# 1) DDL: render as VARCHAR(36) instead of UUID
@compiles(PG_UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"

# 2) Query-time: convert UUID objects to/from strings for SQLite
_orig_bind_processor = PG_UUID.bind_processor
_orig_result_processor = PG_UUID.result_processor


def _patched_bind_processor(self, dialect):
    if dialect.name == "sqlite":
        def process(value):
            if value is not None:
                return str(value)
            return value
        return process
    return _orig_bind_processor(self, dialect)


def _patched_result_processor(self, dialect, coltype):
    if dialect.name == "sqlite":
        def process(value):
            if value is not None and self.as_uuid:
                return uuid_module.UUID(value) if not isinstance(value, uuid_module.UUID) else value
            return value
        return process
    return _orig_result_processor(self, dialect, coltype)


PG_UUID.bind_processor = _patched_bind_processor
PG_UUID.result_processor = _patched_result_processor

from app.database import Base, get_db
from app.main import app
from app.models.user import User, UserPasskey, RegistrationToken, FamilyInvite  # noqa: F401
from app.models.access import AccountRole, AccountAccess  # noqa: F401
from app.models.household import Household, HouseholdRole, HouseholdMembership  # noqa: F401
from app.utils.security import create_access_token


@pytest.fixture(scope="session")
def db_engine():
    """Create a SQLite in-memory engine shared across the test session."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign keys in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a new database session for each test with rollback isolation."""
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with test database session injected."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clear_passkey_challenges():
    """Clear the in-memory challenge store between tests."""
    from app.api.v1.endpoints.passkey import _challenges

    _challenges.clear()
    yield
    _challenges.clear()


@pytest.fixture
def test_user(db_session):
    """Create a basic passkey-only test user (no passkey credential attached)."""
    user = User(
        id=uuid_module.uuid4(),
        username="testuser",
        display_name="Test User",
        email=None,
        hashed_password=None,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_with_passkey(db_session):
    """Create a test user with a registered passkey credential."""
    user = User(
        id=uuid_module.uuid4(),
        username="passkeyuser",
        display_name="Passkey User",
        email=None,
        hashed_password=None,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()

    passkey = UserPasskey(
        user_id=user.id,
        credential_id="test-credential-id-base64url",
        public_key="ZmFrZS1wdWJsaWMta2V5LWZvci10ZXN0aW5n",  # valid base64url
        sign_count=0,
        aaguid="00000000-0000-0000-0000-000000000000",
        device_name="Test Device",
    )
    db_session.add(passkey)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Valid JWT Authorization headers for test_user."""
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}
