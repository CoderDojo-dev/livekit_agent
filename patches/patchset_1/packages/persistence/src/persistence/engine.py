"""Engine + session factory (spec Appendix B: DATABASE_URL, per-service role).

Synchronous SQLAlchemy: FastAPI runs sync path operations in a threadpool, which keeps DB code
simple and correct. The worker's hot voice path never blocks on this - it talks to services over
HTTP and persists conversation data through a non-blocking writer.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return the process-wide engine built from DATABASE_URL."""
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", "postgresql+psycopg://telecom:telecom@localhost:5432/telecom")
        _engine = create_engine(
            url,
            pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
            max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
            pool_timeout=float(os.environ.get("DB_POOL_TIMEOUT", "30.0")),
            pool_recycle=int(os.environ.get("DB_POOL_RECYCLE", "1800")),
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Return the process-wide session factory."""
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _Session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error, always close."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a read session (no implicit commit)."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()