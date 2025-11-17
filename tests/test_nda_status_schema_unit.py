#!/usr/bin/env python3
"""
Unit tests for NDA status schema definition (no database required)

Tests the schema definition itself to ensure:
1. Default status is 'created' 
2. Status column is appropriately sized
3. All workflow statuses are defined in constraint
"""

import pytest
import re
from api.db.schema import NDARecord


class TestNDAStatusSchemaDefinition:
    """Unit tests for NDA status schema definition"""
    
    def test_default_status_is_created(self):
        """Test that NDARecord default status is 'created'"""
        # Check the column definition directly
        status_column = NDARecord.__table__.columns['status']
        
        assert status_column.default.arg == "created", \
            f"Expected default status 'created', got '{status_column.default.arg}'"
    
    def test_status_column_size_sufficient(self):
        """Test that status column can handle longest status names"""
        status_column = NDARecord.__table__.columns['status']
        column_length = status_column.type.length
        
        # Our longest status is 'llm_reviewed_approved' (20 chars)
        longest_status = "llm_reviewed_approved"
        assert column_length >= len(longest_status), \
            f"Status column length {column_length} too small for '{longest_status}' ({len(longest_status)} chars)"
        
        # Should be reasonable size (not too big)
        assert column_length <= 50, \
            f"Status column length {column_length} seems unnecessarily large"
    
    def test_status_constraint_includes_workflow_statuses(self):
        """Test that status constraint includes all required workflow statuses"""
        
        # Expected statuses from our workflow analysis
        expected_statuses = {
            'created',              # Initial state when NDA created from template
            'draft',               # Being edited internally  
            'in_review',           # Workflow started, under review
            'pending_signature',   # Sent to customer, waiting for signature
            'customer_signed',     # Customer returned signed copy
            'llm_reviewed_approved', # LLM approved (pre-send or post-signature)
            'llm_reviewed_rejected', # LLM rejected 
            'reviewed',            # Human reviewed (pre-send or post-signature)
            'approved',            # Approved internally
            'rejected',            # Rejected internally
            'signed',              # Fully executed (both parties signed)
            'active',              # Active and in effect
            'expired',             # Expired
            'terminated',          # Terminated early
            'archived',            # Archived/inactive
            'negotiating'          # Legacy status (backward compatibility)
        }
        
        # Find the status constraint
        status_constraint = None
        for constraint in NDARecord.__table__.constraints:
            if hasattr(constraint, 'sqltext') and 'status IN' in str(constraint.sqltext):
                status_constraint = str(constraint.sqltext)
                break
        
        assert status_constraint is not None, "Status constraint not found in schema"
        
        # Extract statuses from constraint using regex
        # Pattern matches 'status_name' from "status IN ('status1','status2',...)"
        status_pattern = r"'([^']+)'"
        constraint_statuses = set(re.findall(status_pattern, status_constraint))
        
        # Check all expected statuses are in constraint
        missing_statuses = expected_statuses - constraint_statuses
        assert not missing_statuses, \
            f"Missing statuses in constraint: {missing_statuses}"
        
        # Check for unexpected statuses (helpful for debugging)
        extra_statuses = constraint_statuses - expected_statuses
        if extra_statuses:
            print(f"Note: Extra statuses in constraint (might be legacy): {extra_statuses}")
    
    def test_workflow_status_flow_completeness(self):
        """Test that we have all statuses needed for complete workflow"""
        
        # Critical workflow path statuses
        critical_statuses = [
            'created',           # Starting point
            'in_review',         # Workflow started
            'pending_signature', # Sent to customer
            'customer_signed',   # Customer returned it
            'signed',           # Fully executed
            'active'           # Active and in effect
        ]
        
        # Review statuses  
        review_statuses = [
            'llm_reviewed_approved',
            'llm_reviewed_rejected', 
            'reviewed'
        ]
        
        # Terminal statuses
        terminal_statuses = [
            'approved', 'rejected', 'expired', 'terminated', 'archived'
        ]
        
        # Get constraint statuses (reuse logic from previous test)
        status_constraint = None
        for constraint in NDARecord.__table__.constraints:
            if hasattr(constraint, 'sqltext') and 'status IN' in str(constraint.sqltext):
                status_constraint = str(constraint.sqltext)
                break
        
        constraint_statuses = set(re.findall(r"'([^']+)'", status_constraint))
        
        # Check each category
        for status in critical_statuses:
            assert status in constraint_statuses, \
                f"Critical workflow status '{status}' missing from constraint"
        
        for status in review_statuses:
            assert status in constraint_statuses, \
                f"Review status '{status}' missing from constraint"
        
        for status in terminal_statuses:
            assert status in constraint_statuses, \
                f"Terminal status '{status}' missing from constraint"


class TestNDAStatusSchemaIntegrity:
    """Test schema integrity and relationships"""
    
    def test_nda_record_table_exists(self):
        """Test that NDARecord table is properly defined"""
        assert hasattr(NDARecord, '__tablename__')
        assert NDARecord.__tablename__ == 'nda_records'
    
    def test_required_columns_exist(self):
        """Test that all required columns exist"""
        required_columns = [
            'id', 'status', 'counterparty_name', 'file_uri', 'file_sha256',
            'created_at', 'updated_at'
        ]
        
        table_columns = list(NDARecord.__table__.columns.keys())
        
        for column in required_columns:
            assert column in table_columns, \
                f"Required column '{column}' missing from NDARecord table"
    
    def test_status_column_is_not_nullable(self):
        """Test that status column cannot be NULL"""
        status_column = NDARecord.__table__.columns['status']
        assert not status_column.nullable, "Status column should not be nullable"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
