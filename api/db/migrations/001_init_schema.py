"""
Initial database schema migration
Run this to create all tables in a fresh database
"""
from sqlalchemy import create_engine
import os
import sys
from ..schema import Base

# Use psycopg2 for Python < 3.13, psycopg for Python >= 3.13
_default_db_url = (
    "postgresql+psycopg://nda_user:nda_password@localhost:5432/nda_db"
    if sys.version_info >= (3, 13)
    else "postgresql+psycopg2://nda_user:nda_password@localhost:5432/nda_db"
)
DATABASE_URL = os.getenv("POSTGRES_URL", _default_db_url)

if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    print("Database schema created successfully!")
