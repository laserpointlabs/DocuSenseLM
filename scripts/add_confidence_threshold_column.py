#!/usr/bin/env python3
"""
Migration script to add confidence_threshold column to competency_questions table
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from api.db.database import get_database_url

def migrate():
    """Add confidence_threshold column to competency_questions table"""
    engine = create_engine(get_database_url())

    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'competency_questions'
            AND column_name = 'confidence_threshold'
        """))

        if result.fetchone():
            print("✅ confidence_threshold column already exists")
            return

        # Add the column
        print("Adding confidence_threshold column...")
        conn.execute(text("""
            ALTER TABLE competency_questions
            ADD COLUMN confidence_threshold FLOAT DEFAULT 0.7
        """))
        conn.commit()
        print("✅ confidence_threshold column added successfully")

        # Update existing rows to have default value
        conn.execute(text("""
            UPDATE competency_questions
            SET confidence_threshold = 0.7
            WHERE confidence_threshold IS NULL
        """))
        conn.commit()
        print("✅ Existing questions updated with default confidence threshold")

if __name__ == "__main__":
    migrate()
