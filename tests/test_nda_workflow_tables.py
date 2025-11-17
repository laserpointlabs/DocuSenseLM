#!/usr/bin/env python3
"""
Test suite for NDA workflow database tables

Tests the workflow tables that support the NDA review and approval process:
1. NDAWorkflowInstance - tracks Camunda workflow instances 
2. NDAWorkflowTask - tracks workflow tasks for assignment and completion
3. NDATemplate - template definitions for generating unsigned NDAs  
4. EmailConfig - email server configuration
5. EmailMessage - track sent and received emails
6. NDAAuditLog - audit trail for all NDA actions

These tables work together with NDARecord (tested in test_nda_status_schema.py)
"""

import pytest
import uuid
from datetime import datetime, date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from api.db.schema import (
    Base, NDARecord, NDAWorkflowInstance, NDAWorkflowTask, NDATemplate,
    EmailConfig, EmailMessage, NDAAuditLog, User
)
import os

# Test database setup
TEST_DB_URL = os.getenv("TEST_POSTGRES_URL", "postgresql://nda_user:nda_password@localhost:5432/nda_test_db")


class TestWorkflowTableSchemas:
    """Test workflow table schema definitions (no database required)"""
    
    def test_nda_workflow_instance_table_definition(self):
        """Test NDAWorkflowInstance table schema"""
        table = NDAWorkflowInstance.__table__
        
        # Check table name
        assert table.name == 'nda_workflow_instances'
        
        # Check required columns exist
        required_columns = [
            'id', 'nda_record_id', 'camunda_process_instance_id', 
            'current_status', 'started_at', 'completed_at', 'created_at', 'updated_at'
        ]
        
        table_columns = list(table.columns.keys())
        for column in required_columns:
            assert column in table_columns, f"Required column '{column}' missing from NDAWorkflowInstance"
        
        # Check foreign key relationship to NDARecord
        nda_record_column = table.columns['nda_record_id']
        assert len(nda_record_column.foreign_keys) > 0, "nda_record_id should have foreign key"
        
        # Check unique constraints
        unique_columns = [col.name for col in table.columns if col.unique]
        expected_unique = ['camunda_process_instance_id']  # Should be unique per Camunda process
        for col in expected_unique:
            assert col in unique_columns, f"Column '{col}' should be unique"

    def test_nda_workflow_task_table_definition(self):
        """Test NDAWorkflowTask table schema"""
        table = NDAWorkflowTask.__table__
        
        # Check table name
        assert table.name == 'nda_workflow_tasks'
        
        # Check required columns
        required_columns = [
            'id', 'workflow_instance_id', 'task_id', 'task_name', 
            'assignee_user_id', 'status', 'due_date', 'completed_at',
            'comments', 'created_at', 'updated_at'
        ]
        
        table_columns = list(table.columns.keys())
        for column in required_columns:
            assert column in table_columns, f"Required column '{column}' missing from NDAWorkflowTask"
        
        # Check foreign key relationships
        workflow_instance_column = table.columns['workflow_instance_id']
        assert len(workflow_instance_column.foreign_keys) > 0, "workflow_instance_id should have foreign key"
        
        assignee_column = table.columns['assignee_user_id']
        assert len(assignee_column.foreign_keys) > 0, "assignee_user_id should have foreign key"
        
        # Check task_id uniqueness (each Camunda task ID should be unique)
        task_id_column = table.columns['task_id']
        # We'll check this in constraints

    def test_nda_template_table_definition(self):
        """Test NDATemplate table schema"""
        table = NDATemplate.__table__
        
        # Check table name  
        assert table.name == 'nda_templates'
        
        # Check required columns for template versioning
        required_columns = [
            'id', 'name', 'description', 'file_path', 'version', 'template_key',
            'is_active', 'is_current', 'created_by', 'created_at', 'updated_at', 'change_notes'
        ]
        
        table_columns = list(table.columns.keys())
        for column in required_columns:
            assert column in table_columns, f"Required column '{column}' missing from NDATemplate"
        
        # Check versioning columns
        version_column = table.columns['version']
        assert not version_column.nullable, "Version should not be nullable"
        
        template_key_column = table.columns['template_key']
        assert not template_key_column.nullable, "Template key should not be nullable"

    def test_email_config_table_definition(self):
        """Test EmailConfig table schema"""
        table = EmailConfig.__table__
        
        # Check table name
        assert table.name == 'email_config'
        
        # Check required columns for SMTP/IMAP configuration
        required_columns = [
            'id', 'name', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password_encrypted',
            'smtp_use_tls', 'imap_host', 'imap_port', 'imap_user', 'imap_password_encrypted',
            'imap_use_ssl', 'from_address', 'from_name', 'is_active', 'created_at', 'updated_at'
        ]
        
        table_columns = list(table.columns.keys())
        for column in required_columns:
            assert column in table_columns, f"Required column '{column}' missing from EmailConfig"
        
        # Check encrypted password columns are appropriately sized
        smtp_pwd_column = table.columns['smtp_password_encrypted']
        assert smtp_pwd_column.type.length >= 512, "SMTP password column should be large enough for encrypted data"

    def test_email_message_table_definition(self):
        """Test EmailMessage table schema"""
        table = EmailMessage.__table__
        
        # Check table name
        assert table.name == 'email_messages'
        
        # Check required columns for email tracking
        required_columns = [
            'id', 'nda_record_id', 'message_id', 'direction', 'subject', 'body', 'body_html',
            'from_address', 'to_addresses', 'cc_addresses', 'attachments', 'tracking_id',
            'sent_at', 'received_at', 'created_at'
        ]
        
        table_columns = list(table.columns.keys())
        for column in required_columns:
            assert column in table_columns, f"Required column '{column}' missing from EmailMessage"
        
        # Check JSON columns for arrays
        to_addresses_column = table.columns['to_addresses']
        # Should be JSON type for array of email addresses

    def test_nda_audit_log_table_definition(self):
        """Test NDAAuditLog table schema"""
        table = NDAAuditLog.__table__
        
        # Check table name
        assert table.name == 'nda_audit_log'
        
        # Check required columns for audit trail
        required_columns = [
            'id', 'nda_record_id', 'user_id', 'action', 'details', 
            'ip_address', 'user_agent', 'timestamp'
        ]
        
        table_columns = list(table.columns.keys())
        for column in required_columns:
            assert column in table_columns, f"Required column '{column}' missing from NDAAuditLog"
        
        # Check foreign key relationships
        nda_record_column = table.columns['nda_record_id']
        assert len(nda_record_column.foreign_keys) > 0, "nda_record_id should have foreign key"
        
        user_column = table.columns['user_id']
        assert len(user_column.foreign_keys) > 0, "user_id should have foreign key"


class TestWorkflowTableRelationships:
    """Test relationships between workflow tables (unit tests)"""
    
    def test_workflow_instance_to_nda_record_relationship(self):
        """Test that workflow instance correctly references NDA record"""
        # This tests the foreign key setup
        workflow_table = NDAWorkflowInstance.__table__
        nda_record_column = workflow_table.columns['nda_record_id']
        
        # Should have exactly one foreign key to nda_records.id
        foreign_keys = list(nda_record_column.foreign_keys)
        assert len(foreign_keys) == 1, "nda_record_id should have exactly one foreign key"
        
        fk = foreign_keys[0]
        assert fk.column.table.name == 'nda_records', "Should reference nda_records table"
        assert fk.column.name == 'id', "Should reference id column"

    def test_workflow_task_to_workflow_instance_relationship(self):
        """Test that workflow task correctly references workflow instance"""
        task_table = NDAWorkflowTask.__table__
        workflow_instance_column = task_table.columns['workflow_instance_id']
        
        # Should reference nda_workflow_instances.id
        foreign_keys = list(workflow_instance_column.foreign_keys)
        assert len(foreign_keys) == 1, "workflow_instance_id should have exactly one foreign key"
        
        fk = foreign_keys[0]
        assert fk.column.table.name == 'nda_workflow_instances', "Should reference nda_workflow_instances table"
        assert fk.column.name == 'id', "Should reference id column"

    def test_workflow_task_to_user_relationship(self):
        """Test that workflow task correctly references user for assignee"""
        task_table = NDAWorkflowTask.__table__
        assignee_column = task_table.columns['assignee_user_id']
        
        # Should reference users.id
        foreign_keys = list(assignee_column.foreign_keys)
        assert len(foreign_keys) == 1, "assignee_user_id should have exactly one foreign key"
        
        fk = foreign_keys[0]
        assert fk.column.table.name == 'users', "Should reference users table"
        assert fk.column.name == 'id', "Should reference id column"

    def test_email_message_to_nda_record_relationship(self):
        """Test that email message correctly references NDA record"""
        email_table = EmailMessage.__table__
        nda_record_column = email_table.columns['nda_record_id']
        
        # Should reference nda_records.id (nullable for general emails)
        foreign_keys = list(nda_record_column.foreign_keys)
        assert len(foreign_keys) == 1, "nda_record_id should have exactly one foreign key"
        
        fk = foreign_keys[0]
        assert fk.column.table.name == 'nda_records', "Should reference nda_records table"

    def test_audit_log_relationships(self):
        """Test that audit log correctly references NDA record and user"""
        audit_table = NDAAuditLog.__table__
        
        # Check NDA record relationship
        nda_record_column = audit_table.columns['nda_record_id']
        nda_foreign_keys = list(nda_record_column.foreign_keys)
        assert len(nda_foreign_keys) == 1, "nda_record_id should have foreign key"
        assert nda_foreign_keys[0].column.table.name == 'nda_records'
        
        # Check user relationship
        user_column = audit_table.columns['user_id']
        user_foreign_keys = list(user_column.foreign_keys)
        assert len(user_foreign_keys) == 1, "user_id should have foreign key"
        assert user_foreign_keys[0].column.table.name == 'users'


class TestWorkflowTableConstraints:
    """Test table constraints and indexes"""
    
    def test_workflow_instance_constraints(self):
        """Test NDAWorkflowInstance constraints"""
        table = NDAWorkflowInstance.__table__
        
        # Check for unique constraints
        unique_constraint_columns = []
        for constraint in table.constraints:
            if hasattr(constraint, 'columns') and len(constraint.columns) == 1:
                col = list(constraint.columns)[0]
                if hasattr(constraint, 'unique') or 'unique' in str(type(constraint)).lower():
                    unique_constraint_columns.append(col.name)
        
        # nda_record_id should be unique (one workflow instance per NDA)
        # camunda_process_instance_id should be unique (one-to-one mapping)
        expected_unique = ['nda_record_id', 'camunda_process_instance_id']
        
        # Check that these constraints exist in table definition
        # (Implementation may vary - some might be column-level unique=True)
        nda_record_col = table.columns['nda_record_id']
        camunda_col = table.columns['camunda_process_instance_id']
        
        # At least one should be unique at column or table level
        assert nda_record_col.unique or 'nda_record_id' in unique_constraint_columns, \
            "nda_record_id should be unique (one workflow per NDA)"

    def test_workflow_task_constraints(self):
        """Test NDAWorkflowTask constraints"""
        table = NDAWorkflowTask.__table__
        
        # task_id should be unique (Camunda task IDs are globally unique)
        task_id_col = table.columns['task_id']
        
        # Check if task_id has unique constraint
        unique_constraint_columns = []
        for constraint in table.constraints:
            if hasattr(constraint, 'columns'):
                for col in constraint.columns:
                    if hasattr(constraint, 'unique') or 'unique' in str(type(constraint)).lower():
                        unique_constraint_columns.append(col.name)
        
        assert task_id_col.unique or 'task_id' in unique_constraint_columns, \
            "task_id should be unique (Camunda task IDs are globally unique)"

    def test_template_version_constraints(self):
        """Test NDATemplate versioning constraints"""
        table = NDATemplate.__table__
        
        # Should have unique constraint on (template_key, version)
        # This ensures each template version is unique within a template family
        
        # Look for composite unique constraints
        composite_constraints = []
        for constraint in table.constraints:
            if hasattr(constraint, 'columns') and len(constraint.columns) > 1:
                col_names = [col.name for col in constraint.columns]
                composite_constraints.append(col_names)
        
        # Check if (template_key, version) constraint exists
        template_version_constraint = ['template_key', 'version']
        constraint_exists = any(
            set(template_version_constraint).issubset(set(constraint)) 
            for constraint in composite_constraints
        )
        
        assert constraint_exists, \
            "Should have unique constraint on (template_key, version) to prevent duplicate template versions"

    def test_email_message_constraints(self):
        """Test EmailMessage constraints"""
        table = EmailMessage.__table__
        
        # message_id should be unique (email Message-ID header is globally unique)
        message_id_col = table.columns['message_id']
        
        assert message_id_col.unique, \
            "message_id should be unique (email Message-ID headers are globally unique)"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
