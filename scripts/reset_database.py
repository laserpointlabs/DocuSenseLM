#!/usr/bin/env python3
"""
Reset database - drops all tables and leaves database empty
WARNING: This will delete ALL data!
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text, inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reset_database():
    """Drop all tables and leave database empty"""
    
    # Get database URL from environment
    db_url = os.getenv("POSTGRES_URL", "postgresql://nda_user:nda_password@localhost:5432/nda_db")
    
    logger.info(f"Connecting to database: {db_url.split('@')[1] if '@' in db_url else 'unknown'}")
    
    # Create engine
    engine = create_engine(db_url)
    
    # Get inspector to list all tables
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()
    
    if not all_tables:
        logger.info("Database is already empty")
        return True
    
    logger.warning(f"Found {len(all_tables)} tables. This will DELETE ALL DATA!")
    logger.info(f"Tables: {', '.join(all_tables)}")
    
    # Drop all tables
    logger.info("Dropping all tables...")
    with engine.connect() as conn:
        # Drop all tables (CASCADE to handle foreign keys)
        for table_name in all_tables:
            try:
                conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
                logger.info(f"  Dropped table: {table_name}")
            except Exception as e:
                logger.warning(f"  Failed to drop {table_name}: {e}")
        
        # Drop all sequences
        conn.execute(text("DROP SEQUENCE IF EXISTS alembic_version_seq CASCADE"))
        
        # Drop all types/enums
        try:
            conn.execute(text("DROP TYPE IF EXISTS documentstatus CASCADE"))
        except:
            pass
        
        # Commit the transaction
        conn.commit()
    
    logger.info("All tables dropped successfully")
    
    # Verify database is empty
    inspector = inspect(engine)
    remaining_tables = inspector.get_table_names()
    
    if remaining_tables:
        logger.warning(f"Warning: Some tables still exist: {remaining_tables}")
        return False
    
    logger.info("✓ Database is now empty")
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Reset database - drops all tables")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt"
    )
    args = parser.parse_args()
    
    print("=" * 60)
    print("DATABASE RESET SCRIPT")
    print("=" * 60)
    print()
    print("WARNING: This will DELETE ALL DATA in the database!")
    print("This includes:")
    print("  - All documents")
    print("  - All NDAs")
    print("  - All templates")
    print("  - All users")
    print("  - All workflow instances")
    print("  - All email configurations")
    print()
    print("The database will be left EMPTY (no migrations will be run).")
    print()
    
    if not args.yes:
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            sys.exit(0)
    
    print()
    success = reset_database()
    
    if success:
        print()
        print("=" * 60)
        print("✓ Database reset complete!")
        print("=" * 60)
        print()
        print("Database is now empty. You can test from scratch via the UI.")
        sys.exit(0)
    else:
        print()
        print("=" * 60)
        print("✗ Database reset failed!")
        print("=" * 60)
        sys.exit(1)

