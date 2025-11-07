from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import os
from sqlalchemy.pool import StaticPool

from .schema import Base

# Database URL from environment
DATABASE_URL = os.getenv("POSTGRES_URL", "postgresql+psycopg://nda_user:nda_password@localhost:5432/nda_db")

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
