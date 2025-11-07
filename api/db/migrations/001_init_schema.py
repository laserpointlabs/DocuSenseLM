"""
Initial database schema migration
Run this to create all tables in a fresh database
"""
from sqlalchemy import create_engine
import os
from ..schema import Base

DATABASE_URL = os.getenv("POSTGRES_URL", "postgresql+psycopg://nda_user:nda_password@localhost:5432/nda_db")

if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    print("Database schema created successfully!")
