"""Database connection and session management.

Reads ``DATABASE_URL`` from environment (via python-dotenv) and provides a
SQLAlchemy engine and session factory.  When ``DATABASE_URL`` is not set the
module falls back to an **in-memory SQLite** engine — suitable for quick local
development without a PostgreSQL instance.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Generator
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv(override=False)

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None
_lock = threading.Lock()


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///:memory:")


def _build_engine() -> Engine:
    url = get_database_url()
    pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))

    if url.startswith("sqlite"):
        engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(
            url,
            echo=False,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
        )

    logger.info("Database engine created", extra={"url": url.split("@")[-1] if "@" in url else url})
    return engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                _engine = _build_engine()
    return _engine


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        with _lock:
            if _SessionLocal is None:
                _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def session_dependency() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and closes it after use.

    Note: This dependency does NOT manage transactions. Services are responsible
    for calling session.commit() or session.rollback() as needed.
    """
    session = get_session()
    try:
        yield session
    finally:
        session.close()
