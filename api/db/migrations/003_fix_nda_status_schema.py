#!/usr/bin/env python3
"""
Migration: Fix NDA status schema for proper workflow support

Based on analysis in NDA_WORKFLOW_ANALYSIS.md, this migration:
1. Updates status constraint to include all workflow statuses
2. Changes default status from "signed" to "created" 
3. Increases status column size to handle longer status names
4. Adds proper workflow status support
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text, create_engine
import os

def upgrade():
    """Fix NDA status schema for workflow support"""
    # Get database URL from environment
    db_url = os.getenv("POSTGRES_URL", "postgresql://nda_user:nda_password@postgres:5432/nda_db")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        print("🔧 Fixing NDA status schema for workflow support...")
        
        # 1. Drop existing status constraint
        print("  - Dropping old status constraint...")
        conn.execute(text("""
            ALTER TABLE nda_records 
            DROP CONSTRAINT IF EXISTS chk_nda_records_status
        """))
        
        # 2. Increase status column size to handle longer status names
        print("  - Increasing status column size...")
        conn.execute(text("""
            ALTER TABLE nda_records 
            ALTER COLUMN status TYPE VARCHAR(30)
        """))
        
        # 3. Add comprehensive status constraint with all workflow statuses  
        print("  - Adding comprehensive status constraint...")
        conn.execute(text("""
            ALTER TABLE nda_records
            ADD CONSTRAINT chk_nda_records_status CHECK (
                status IN (
                    'created',              -- Initial state when NDA created from template
                    'draft',               -- Being edited internally  
                    'in_review',           -- Workflow started, under review
                    'pending_signature',   -- Sent to customer, waiting for signature
                    'customer_signed',     -- Customer returned signed copy
                    'llm_reviewed_approved', -- LLM approved (pre-send or post-signature)
                    'llm_reviewed_rejected', -- LLM rejected 
                    'reviewed',            -- Human reviewed (pre-send or post-signature)
                    'approved',            -- Approved internally
                    'rejected',            -- Rejected internally
                    'signed',              -- Fully executed (both parties signed)
                    'active',              -- Active and in effect
                    'expired',             -- Expired
                    'terminated',          -- Terminated early
                    'archived',            -- Archived/inactive
                    -- Legacy statuses (keep for backward compatibility)
                    'negotiating'          -- Legacy status from old system
                )
            )
        """))
        
        # 4. Update default status to "created" for new records
        print("  - Setting default status to 'created'...")
        conn.execute(text("""
            ALTER TABLE nda_records 
            ALTER COLUMN status SET DEFAULT 'created'
        """))
        
        # 5. Update any existing records with invalid default status
        print("  - Updating existing records with 'signed' status...")
        result = conn.execute(text("""
            UPDATE nda_records 
            SET status = 'active'
            WHERE status = 'signed'
            RETURNING id, counterparty_name
        """))
        
        updated_count = result.rowcount if hasattr(result, 'rowcount') else 0
        if updated_count > 0:
            print(f"  - Updated {updated_count} existing records from 'signed' to 'active'")
        
        # 6. Commit transaction
        conn.commit()
        
        print("✅ NDA status schema updated successfully!")
        print("\n📋 New status values supported:")
        print("  - Workflow: created → in_review → pending_signature → customer_signed → signed → active")
        print("  - Reviews: llm_reviewed_approved, llm_reviewed_rejected, reviewed") 
        print("  - Outcomes: approved, rejected, expired, terminated, archived")


def downgrade():
    """Revert NDA status schema changes"""
    db_url = os.getenv("POSTGRES_URL", "postgresql://nda_user:nda_password@postgres:5432/nda_db")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        print("🔧 Reverting NDA status schema changes...")
        
        # Drop new status constraint
        conn.execute(text("""
            ALTER TABLE nda_records 
            DROP CONSTRAINT IF EXISTS chk_nda_records_status
        """))
        
        # Revert status column size
        conn.execute(text("""
            ALTER TABLE nda_records 
            ALTER COLUMN status TYPE VARCHAR(20)
        """))
        
        # Restore old status constraint
        conn.execute(text("""
            ALTER TABLE nda_records
            ADD CONSTRAINT chk_nda_records_status CHECK (
                status IN ('draft','negotiating','approved','signed','expired','terminated')
            )
        """))
        
        # Revert default status
        conn.execute(text("""
            ALTER TABLE nda_records 
            ALTER COLUMN status SET DEFAULT 'signed'
        """))
        
        # Update any records back to 'signed' if they were 'active'
        conn.execute(text("""
            UPDATE nda_records 
            SET status = 'signed'
            WHERE status = 'active'
        """))
        
        conn.commit()
        print("✅ Status schema reverted to original state")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
