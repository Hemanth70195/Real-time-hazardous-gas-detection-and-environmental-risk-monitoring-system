# -*- coding: utf-8 -*-
"""
SafeEdge HazardGuard - Database Engine & Connection Lifecycle (Phase 3).
Supports PostgreSQL for cloud deployments with automatic SQLite fallback
for zero-dependency local development and automated testing.
"""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.models import Base

# Database URL from environment variable or SQLite fallback
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "safeedge_iot.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# Normalize legacy postgres:// to postgresql:// for SQLAlchemy compatibility (e.g., Render, Heroku)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configure SQLite-specific vs PostgreSQL arguments
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # Handles broken connections and reconnects gracefully
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initializes tables and indexes in the configured database."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic commit/rollback."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

