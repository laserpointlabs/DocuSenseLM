from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import os
import sys
from sqlalchemy.pool import StaticPool

from .schema import Base

# Database URL from environment
# Use psycopg2 for Python < 3.13, psycopg for Python >= 3.13
_default_db_url = (
    "postgresql+psycopg://nda_user:nda_password@localhost:5432/nda_db"
    if sys.version_info >= (3, 13)
    else "postgresql+psycopg2://nda_user:nda_password@localhost:5432/nda_db"
)
DATABASE_URL = os.getenv("POSTGRES_URL", _default_db_url)

# Create engine with sensible defaults for Postgres and SQLite
engine_kwargs = {
    "pool_pre_ping": True,
}

if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs["poolclass"] = StaticPool
else:
    engine_kwargs.update({"pool_size": 10, "max_overflow": 20})

engine = create_engine(
    DATABASE_URL,
    **engine_kwargs,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db():
    """Get database session context manager"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """Get database session (for dependency injection)"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Session will be closed by dependency
