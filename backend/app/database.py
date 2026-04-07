"""Database configuration and session management"""

import os
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator

from app.config import settings


def _clean_database_url(url: str) -> str:
    """Strip connection parameters that are meaningful to PgBouncer/Neon but
    invalid for psycopg2 (e.g. pgbouncer=true)."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params.pop("pgbouncer", None)
    clean_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=clean_query))

# On Lambda each container is short-lived; let Neon's PgBouncer handle pooling.
# On a long-running server, use SQLAlchemy's built-in pool.
_is_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

_is_sqlite = settings.database_url.startswith("sqlite")

_engine_kwargs = {
    "echo": settings.debug,
    "pool_pre_ping": True,
}
if _is_lambda or _is_sqlite:
    # Lambda: let Neon's PgBouncer manage pooling.
    # SQLite: doesn't support pool_size/max_overflow (also used in tests).
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

engine = create_engine(_clean_database_url(settings.database_url), **_engine_kwargs)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session.

    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database - create all tables"""
    Base.metadata.create_all(bind=engine)
