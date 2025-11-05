#!/usr/bin/env python3
"""
Migration script to add citations_json column to test_runs table
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from api.db import DATABASE_URL

def migrate():
    """Add citations_json column to test_runs table"""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'test_runs'
            AND column_name = 'citations_json'
        """))

        if result.fetchone():
            print("✅ citations_json column already exists")
            return

        # Add the column
        print("Adding citations_json column to test_runs table...")
        conn.execute(text("""
            ALTER TABLE test_runs
            ADD COLUMN citations_json JSON
        """))
        conn.commit()
        print("✅ citations_json column added successfully")

if __name__ == "__main__":
    migrate()



