from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config.settings import settings


class Base(DeclarativeBase):
    """Declarative base for all GRaC ORM models."""


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        database_url = settings.DATABASE_URL

        # Ensure SQLite directory exists
        if database_url.startswith("sqlite"):
            db_path = database_url.replace("sqlite:///", "")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        _engine = create_engine(
            database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            echo=False,
        )

    return _engine


def get_session_local() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def create_tables() -> None:
    """Create all tables that don't yet exist."""
    import database.models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=get_engine())


def drop_tables() -> None:
    """Drop all GRaC tables (use with caution)."""
    import database.models  # noqa: F401
    Base.metadata.drop_all(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a DB session and close it after the request."""
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """Standalone session factory for scripts and agent use."""
    return get_session_local()()


def init_db() -> None:
    """Idempotent initialisation: create engine + tables."""
    get_engine()
    create_tables()
