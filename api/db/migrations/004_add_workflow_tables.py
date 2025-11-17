#!/usr/bin/env python3
"""
Migration: Add NDA workflow automation tables

Adds the following tables to support NDA workflow system:
1. NDATemplate - Template definitions with versioning
2. NDAWorkflowInstance - Tracks Camunda workflow instances  
3. NDAWorkflowTask - Tracks workflow tasks for assignment
4. EmailConfig - Email server configuration
5. WorkflowConfig - Workflow configuration settings
6. EmailMessage - Track sent/received emails
7. NDAAuditLog - Audit trail for NDA actions

Also adds foreign key relationships from NDARecord to workflow tables.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text, create_engine
import os

def upgrade():
    """Add workflow tables"""
    # Get database URL from environment
    db_url = os.getenv("POSTGRES_URL", "postgresql://nda_user:nda_password@postgres:5432/nda_db")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        print("🔧 Adding NDA workflow tables...")
        
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
        
        # 1. Create NDA Templates table
        print("  - Creating nda_templates table...")
        conn.execute(text("""
            CREATE TABLE nda_templates (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                description TEXT,
                file_path VARCHAR(512) NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                template_key VARCHAR(255) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT true,
                is_current BOOLEAN NOT NULL DEFAULT true,
                created_by UUID REFERENCES users(id),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                change_notes TEXT,
                CONSTRAINT uq_template_key_version UNIQUE (template_key, version)
            )
        """))
        
        # Create indexes for NDA templates
        conn.execute(text("""
            CREATE INDEX idx_templates_name ON nda_templates(name);
            CREATE INDEX idx_templates_key ON nda_templates(template_key);
            CREATE INDEX idx_templates_active ON nda_templates(is_active);
            CREATE INDEX idx_templates_current ON nda_templates(is_current);
            CREATE INDEX idx_templates_created_at ON nda_templates(created_at);
        """))
        
        # 2. Create NDA Workflow Instances table
        print("  - Creating nda_workflow_instances table...")
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
        
        # Create indexes for workflow instances
        conn.execute(text("""
            CREATE INDEX idx_workflow_instances_nda_record ON nda_workflow_instances(nda_record_id);
            CREATE INDEX idx_workflow_instances_camunda_id ON nda_workflow_instances(camunda_process_instance_id);
            CREATE INDEX idx_workflow_instances_status ON nda_workflow_instances(current_status);
            CREATE INDEX idx_workflow_instances_started_at ON nda_workflow_instances(started_at);
        """))
        
        # 3. Create NDA Workflow Tasks table
        print("  - Creating nda_workflow_tasks table...")
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
        
        # Create indexes for workflow tasks
        conn.execute(text("""
            CREATE INDEX idx_workflow_tasks_instance ON nda_workflow_tasks(workflow_instance_id);
            CREATE INDEX idx_workflow_tasks_task_id ON nda_workflow_tasks(task_id);
            CREATE INDEX idx_workflow_tasks_assignee ON nda_workflow_tasks(assignee_user_id);
            CREATE INDEX idx_workflow_tasks_status ON nda_workflow_tasks(status);
            CREATE INDEX idx_workflow_tasks_due_date ON nda_workflow_tasks(due_date);
        """))
        
        # 4. Create Email Config table
        print("  - Creating email_config table...")
        conn.execute(text("""
            CREATE TABLE email_config (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(100) NOT NULL UNIQUE,
                smtp_host VARCHAR(255) NOT NULL,
                smtp_port INTEGER NOT NULL DEFAULT 587,
                smtp_user VARCHAR(255) NOT NULL,
                smtp_password_encrypted VARCHAR(512) NOT NULL,
                smtp_use_tls BOOLEAN NOT NULL DEFAULT true,
                imap_host VARCHAR(255),
                imap_port INTEGER DEFAULT 993,
                imap_user VARCHAR(255),
                imap_password_encrypted VARCHAR(512),
                imap_use_ssl BOOLEAN DEFAULT true,
                from_address VARCHAR(255) NOT NULL,
                from_name VARCHAR(255),
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        
        # Create indexes for email config
        conn.execute(text("""
            CREATE INDEX idx_email_config_name ON email_config(name);
            CREATE INDEX idx_email_config_active ON email_config(is_active);
        """))
        
        # 5. Create Workflow Config table
        print("  - Creating workflow_config table...")
        conn.execute(text("""
            CREATE TABLE workflow_config (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(100) NOT NULL UNIQUE,
                reviewer_user_ids JSONB NOT NULL DEFAULT '[]',
                approver_user_ids JSONB NOT NULL DEFAULT '[]',
                final_approver_user_id UUID REFERENCES users(id),
                llm_review_enabled BOOLEAN NOT NULL DEFAULT true,
                llm_review_threshold FLOAT DEFAULT 0.7,
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        
        # Create indexes for workflow config
        conn.execute(text("""
            CREATE INDEX idx_workflow_config_name ON workflow_config(name);
            CREATE INDEX idx_workflow_config_active ON workflow_config(is_active);
        """))
        
        # 6. Create Email Messages table
        print("  - Creating email_messages table...")
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
        
        # Create indexes for email messages
        conn.execute(text("""
            CREATE INDEX idx_email_messages_nda_record ON email_messages(nda_record_id);
            CREATE INDEX idx_email_messages_message_id ON email_messages(message_id);
            CREATE INDEX idx_email_messages_direction ON email_messages(direction);
            CREATE INDEX idx_email_messages_tracking_id ON email_messages(tracking_id);
            CREATE INDEX idx_email_messages_sent_at ON email_messages(sent_at);
            CREATE INDEX idx_email_messages_received_at ON email_messages(received_at);
        """))
        
        # 7. Create NDA Audit Log table
        print("  - Creating nda_audit_log table...")
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
        
        # Create indexes for audit log
        conn.execute(text("""
            CREATE INDEX idx_audit_log_nda_record ON nda_audit_log(nda_record_id);
            CREATE INDEX idx_audit_log_user ON nda_audit_log(user_id);
            CREATE INDEX idx_audit_log_action ON nda_audit_log(action);
            CREATE INDEX idx_audit_log_timestamp ON nda_audit_log(timestamp);
        """))
        
        # 8. Add foreign key columns to nda_records table
        print("  - Adding foreign keys to nda_records table...")
        conn.execute(text("""
            ALTER TABLE nda_records 
            ADD COLUMN IF NOT EXISTS workflow_instance_id UUID REFERENCES nda_workflow_instances(id),
            ADD COLUMN IF NOT EXISTS template_id UUID REFERENCES nda_templates(id),
            ADD COLUMN IF NOT EXISTS template_version INTEGER
        """))
        
        # Create index for new foreign keys
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_nda_records_workflow_instance 
            ON nda_records(workflow_instance_id);
            CREATE INDEX IF NOT EXISTS idx_nda_records_template 
            ON nda_records(template_id);
        """))
        
        # Commit transaction
        conn.commit()
        
        print("✅ NDA workflow tables created successfully!")
        print("\n📋 Added tables:")
        print("  - nda_templates (template definitions with versioning)")
        print("  - nda_workflow_instances (Camunda workflow tracking)")
        print("  - nda_workflow_tasks (workflow task assignments)")
        print("  - email_config (SMTP/IMAP configuration)")
        print("  - workflow_config (workflow settings)")
        print("  - email_messages (email tracking)")
        print("  - nda_audit_log (audit trail)")


def downgrade():
    """Remove workflow tables"""
    db_url = os.getenv("POSTGRES_URL", "postgresql://nda_user:nda_password@postgres:5432/nda_db")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        print("🔧 Removing NDA workflow tables...")
        
        # Remove foreign key columns from nda_records
        conn.execute(text("""
            ALTER TABLE nda_records 
            DROP COLUMN IF EXISTS workflow_instance_id,
            DROP COLUMN IF EXISTS template_id,
            DROP COLUMN IF EXISTS template_version
        """))
        
        # Drop tables in reverse order (due to foreign key dependencies)
        tables_to_drop = [
            'nda_audit_log',
            'email_messages', 
            'workflow_config',
            'email_config',
            'nda_workflow_tasks',
            'nda_workflow_instances',
            'nda_templates'
        ]
        
        for table in tables_to_drop:
            conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            print(f"  - Dropped {table}")
        
        conn.commit()
        print("✅ Workflow tables removed")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
