"""Shared persistence layer: one PostgreSQL database, one schema per bounded context (spec section 2.1)."""
from persistence.base import Base
from persistence.engine import get_engine, get_session, get_sessionmaker, session_scope

__all__ = ["Base", "get_engine", "get_sessionmaker", "get_session", "session_scope"]