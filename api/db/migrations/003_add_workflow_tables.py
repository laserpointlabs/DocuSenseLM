#!/usr/bin/env python3
"""
Migration: Add workflow automation tables and update NDARecord status constraint
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text, create_engine
import os

def upgrade():
    """Add workflow tables and update NDARecord status constraint"""
    # Get database URL from environment
    db_url = os.getenv("POSTGRES_URL", "postgresql://nda_user:nda_password@postgres:5432/nda_db")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Check if tables already exist
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'nda_templates'
        """))

        if result.fetchone():
            print("✓ Workflow tables already exist, skipping migration")
            return

        # Drop old status constraint
        conn.execute(text("""
            ALTER TABLE nda_records
            DROP CONSTRAINT IF EXISTS chk_nda_records_status
        """))

        # Add new status constraint with expanded statuses
        conn.execute(text("""
            ALTER TABLE nda_records
            ADD CONSTRAINT chk_nda_records_status CHECK (
                status IN (
                    'created', 'draft', 'negotiating', 'customer_signed',
                    'llm_reviewed_approved', 'llm_reviewed_rejected',
                    'reviewed', 'approved', 'rejected', 'signed',
                    'archived', 'expired', 'active', 'terminated'
                )
            )
        """))

        # Add workflow_instance_id column to nda_records
        conn.execute(text("""
            ALTER TABLE nda_records
            ADD COLUMN IF NOT EXISTS workflow_instance_id UUID
        """))

        # Create nda_templates table
        conn.execute(text("""
            CREATE TABLE nda_templates (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                description TEXT,
                file_path VARCHAR(512) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_by UUID REFERENCES users(id),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE INDEX idx_templates_name ON nda_templates(name)
        """))

        conn.execute(text("""
            CREATE INDEX idx_templates_active ON nda_templates(is_active)
        """))

        conn.execute(text("""
            CREATE INDEX idx_templates_created_at ON nda_templates(created_at)
        """))

        # Create nda_workflow_instances table
        conn.execute(text("""
            CREATE TABLE nda_workflow_instances (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                nda_record_id UUID NOT NULL UNIQUE REFERENCES nda_records(id),
                camunda_process_instance_id VARCHAR(100) NOT NULL UNIQUE,
                current_status VARCHAR(50) NOT NULL,
                started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                completed_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE INDEX idx_workflow_instances_nda_record ON nda_workflow_instances(nda_record_id)
        """))

        conn.execute(text("""
            CREATE INDEX idx_workflow_instances_camunda_id ON nda_workflow_instances(camunda_process_instance_id)
        """))

        conn.execute(text("""
            CREATE INDEX idx_workflow_instances_status ON nda_workflow_instances(current_status)
        """))

        conn.execute(text("""
            CREATE INDEX idx_workflow_instances_started_at ON nda_workflow_instances(started_at)
        """))

        # Add foreign key constraint for workflow_instance_id
        conn.execute(text("""
            ALTER TABLE nda_records
            ADD CONSTRAINT fk_nda_records_workflow_instance
            FOREIGN KEY (workflow_instance_id) REFERENCES nda_workflow_instances(id)
        """))

        conn.execute(text("""
            CREATE INDEX idx_nda_records_workflow_instance ON nda_records(workflow_instance_id)
        """))

        conn.execute(text("""
            CREATE INDEX idx_nda_records_status ON nda_records(status)
        """))

        # Create nda_workflow_tasks table
        conn.execute(text("""
            CREATE TABLE nda_workflow_tasks (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                workflow_instance_id UUID NOT NULL REFERENCES nda_workflow_instances(id),
                task_id VARCHAR(100) NOT NULL UNIQUE,
                task_name VARCHAR(255) NOT NULL,
                assignee_user_id UUID REFERENCES users(id),
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                due_date TIMESTAMP WITH TIME ZONE,
                completed_at TIMESTAMP WITH TIME ZONE,
                comments TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE INDEX idx_workflow_tasks_instance ON nda_workflow_tasks(workflow_instance_id)
        """))

        conn.execute(text("""
            CREATE INDEX idx_workflow_tasks_task_id ON nda_workflow_tasks(task_id)
        """))

        conn.execute(text("""
            CREATE INDEX idx_workflow_tasks_assignee ON nda_workflow_tasks(assignee_user_id)
        """))

        conn.execute(text("""
            CREATE INDEX idx_workflow_tasks_status ON nda_workflow_tasks(status)
        """))

        conn.execute(text("""
            CREATE INDEX idx_workflow_tasks_due_date ON nda_workflow_tasks(due_date)
        """))

        # Create email_config table
        conn.execute(text("""
            CREATE TABLE email_config (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(100) NOT NULL UNIQUE,
                smtp_host VARCHAR(255) NOT NULL,
                smtp_port INTEGER NOT NULL DEFAULT 587,
                smtp_user VARCHAR(255) NOT NULL,
                smtp_password_encrypted VARCHAR(512) NOT NULL,
                smtp_use_tls BOOLEAN NOT NULL DEFAULT TRUE,
                imap_host VARCHAR(255),
                imap_port INTEGER DEFAULT 993,
                imap_user VARCHAR(255),
                imap_password_encrypted VARCHAR(512),
                imap_use_ssl BOOLEAN DEFAULT TRUE,
                from_address VARCHAR(255) NOT NULL,
                from_name VARCHAR(255),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE INDEX idx_email_config_name ON email_config(name)
        """))

        conn.execute(text("""
            CREATE INDEX idx_email_config_active ON email_config(is_active)
        """))

        # Create workflow_config table
        conn.execute(text("""
            CREATE TABLE workflow_config (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(100) NOT NULL UNIQUE,
                reviewer_user_ids JSONB NOT NULL DEFAULT '[]',
                approver_user_ids JSONB NOT NULL DEFAULT '[]',
                final_approver_user_id UUID REFERENCES users(id),
                llm_review_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                llm_review_threshold REAL DEFAULT 0.7,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE INDEX idx_workflow_config_name ON workflow_config(name)
        """))

        conn.execute(text("""
            CREATE INDEX idx_workflow_config_active ON workflow_config(is_active)
        """))

        # Create email_messages table
        conn.execute(text("""
            CREATE TABLE email_messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                nda_record_id UUID REFERENCES nda_records(id),
                message_id VARCHAR(255) NOT NULL UNIQUE,
                direction VARCHAR(20) NOT NULL,
                subject VARCHAR(512) NOT NULL,
                body TEXT,
                body_html TEXT,
                from_address VARCHAR(255) NOT NULL,
                to_addresses JSONB NOT NULL,
                cc_addresses JSONB,
                attachments JSONB,
                tracking_id VARCHAR(100),
                sent_at TIMESTAMP WITH TIME ZONE,
                received_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE INDEX idx_email_messages_nda_record ON email_messages(nda_record_id)
        """))

        conn.execute(text("""
            CREATE INDEX idx_email_messages_message_id ON email_messages(message_id)
        """))

        conn.execute(text("""
            CREATE INDEX idx_email_messages_direction ON email_messages(direction)
        """))

        conn.execute(text("""
            CREATE INDEX idx_email_messages_tracking_id ON email_messages(tracking_id)
        """))

        conn.execute(text("""
            CREATE INDEX idx_email_messages_sent_at ON email_messages(sent_at)
        """))

        conn.execute(text("""
            CREATE INDEX idx_email_messages_received_at ON email_messages(received_at)
        """))

        # Create nda_audit_log table
        conn.execute(text("""
            CREATE TABLE nda_audit_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                nda_record_id UUID NOT NULL REFERENCES nda_records(id),
                user_id UUID REFERENCES users(id),
                action VARCHAR(100) NOT NULL,
                details JSONB,
                ip_address VARCHAR(45),
                user_agent VARCHAR(512),
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE INDEX idx_audit_log_nda_record ON nda_audit_log(nda_record_id)
        """))

        conn.execute(text("""
            CREATE INDEX idx_audit_log_user ON nda_audit_log(user_id)
        """))

        conn.execute(text("""
            CREATE INDEX idx_audit_log_action ON nda_audit_log(action)
        """))

        conn.execute(text("""
            CREATE INDEX idx_audit_log_timestamp ON nda_audit_log(timestamp)
        """))

        conn.commit()
        print("✓ Added workflow automation tables and updated NDARecord status constraint")


if __name__ == "__main__":
    upgrade()

