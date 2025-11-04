#!/usr/bin/env python3
"""
Migration: Add document association fields to competency_questions table
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text, create_engine
from api.db import get_db_session
import os

def upgrade():
    """Add document_id, verification_hint, expected_clause, expected_page columns"""
    # Get database URL from environment
    db_url = os.getenv("DATABASE_URL", "postgresql://nda_user:nda_password@postgres:5432/nda_db")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'competency_questions'
            AND column_name = 'document_id'
        """))

        if result.fetchone():
            print("✓ Columns already exist, skipping migration")
            return

        # Add document_id column
        conn.execute(text("""
            ALTER TABLE competency_questions
            ADD COLUMN document_id UUID REFERENCES documents(id)
        """))

        # Add verification_hint column
        conn.execute(text("""
            ALTER TABLE competency_questions
            ADD COLUMN verification_hint TEXT
        """))

        # Add expected_clause column
        conn.execute(text("""
            ALTER TABLE competency_questions
            ADD COLUMN expected_clause VARCHAR(200)
        """))

        # Add expected_page column
        conn.execute(text("""
            ALTER TABLE competency_questions
            ADD COLUMN expected_page INTEGER
        """))

        # Add index for document_id
        conn.execute(text("""
            CREATE INDEX idx_competency_questions_document
            ON competency_questions(document_id)
        """))

        conn.commit()
        print("✓ Added document association fields to competency_questions table")


if __name__ == "__main__":
    upgrade()
