#!/usr/bin/env python3
"""
Test suite for NDA status schema and workflow status transitions

Tests the correct NDA status flow identified in our architecture analysis:
1. Create NDA → "created"  
2. Start workflow → "in_review"
3. LLM review (unsigned) → "llm_reviewed_approved" or "llm_reviewed_rejected"
4. Human review (unsigned) → "reviewed" 
5. Send to customer → "pending_signature"
6. Customer signs → "customer_signed"
7. LLM review (signed) → "llm_reviewed_approved" or "llm_reviewed_rejected" 
8. Human review (signed) → "reviewed"
9. Internal signature → "signed" or "active"
10. Final states → "expired", "terminated", "archived"
"""

import pytest
import uuid
from datetime import date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from api.db.schema import Base, NDARecord
import os

# Test database setup
TEST_DB_URL = os.getenv("TEST_POSTGRES_URL", "postgresql://nda_user:nda_password@localhost:5432/nda_test_db")


class TestNDAStatusSchema:
    """Test NDA status schema constraints and transitions"""

    @pytest.fixture(scope="class")
    def db_engine(self):
        """Create test database engine"""
        engine = create_engine(TEST_DB_URL)
        Base.metadata.create_all(engine)
        yield engine
        Base.metadata.drop_all(engine)

    @pytest.fixture
    def db_session(self, db_engine):
        """Create test database session"""
        Session = sessionmaker(bind=db_engine)
        session = Session()
        yield session
        session.rollback()
        session.close()

    def test_default_status_is_created(self, db_session):
        """Test that new NDA records default to 'created' status"""
        nda = NDARecord(
            counterparty_name="Test Company",
            file_uri="test://file",
            file_sha256=b"test_hash_123456789012345678901234567890"
        )
        db_session.add(nda)
        db_session.flush()
        
        assert nda.status == "created", f"Expected 'created', got '{nda.status}'"

    def test_all_workflow_statuses_allowed(self, db_session):
        """Test that all workflow statuses are allowed by schema constraint"""
        
        # Define all valid statuses in correct workflow order
        valid_statuses = [
            "created",              # Initial state when NDA created from template
            "draft",               # Being edited internally  
            "in_review",           # Workflow started, under review
            "pending_signature",   # Sent to customer, waiting for signature
            "customer_signed",     # Customer returned signed copy
            "llm_reviewed_approved", # LLM approved (can happen pre-send or post-signature)
            "llm_reviewed_rejected", # LLM rejected 
            "reviewed",            # Human reviewed (can happen pre-send or post-signature)
            "approved",            # Approved internally
            "rejected",            # Rejected internally
            "signed",              # Fully executed (both parties signed)
            "active",              # Active and in effect
            "expired",             # Expired
            "terminated",          # Terminated early
            "archived"             # Archived/inactive
        ]
        
        # Test each status can be set without constraint violation
        for status in valid_statuses:
            nda = NDARecord(
                counterparty_name=f"Test Company {status}",
                status=status,
                file_uri=f"test://file/{status}",
                file_sha256=f"test_hash_{status}".encode().ljust(32, b'0')[:32]
            )
            db_session.add(nda)
            db_session.flush()  # This will trigger constraint check
            
            assert nda.status == status, f"Status '{status}' should be allowed"
            
        db_session.rollback()  # Clean up for next test

    def test_invalid_status_rejected(self, db_session):
        """Test that invalid statuses are rejected by schema constraint"""
        
        invalid_statuses = [
            "invalid_status",
            "pending", 
            "processing",
            "unknown",
            ""
        ]
        
        for invalid_status in invalid_statuses:
            with pytest.raises((IntegrityError, Exception)) as exc_info:
                nda = NDARecord(
                    counterparty_name=f"Test Company {invalid_status}",
                    status=invalid_status,
                    file_uri=f"test://file/{invalid_status}",
                    file_sha256=f"test_hash_{invalid_status}".encode().ljust(32, b'0')[:32]
                )
                db_session.add(nda)
                db_session.flush()  # This should trigger constraint violation
                
            db_session.rollback()  # Clean up after each failed attempt

    def test_status_column_size_sufficient(self, db_session):
        """Test that status column can handle longest status names"""
        
        longest_status = "llm_reviewed_approved"  # 20 characters
        very_long_status = "llm_reviewed_approved_with_conditions"  # 35 characters
        
        # Test longest expected status works
        nda = NDARecord(
            counterparty_name="Test Company Long Status",
            status=longest_status,
            file_uri="test://file/long",
            file_sha256=b"test_hash_long_status_1234567890"
        )
        db_session.add(nda)
        db_session.flush()
        
        assert nda.status == longest_status
        
        # Test that extremely long status is handled appropriately
        # (Either works if column is big enough, or fails gracefully)
        try:
            nda2 = NDARecord(
                counterparty_name="Test Company Very Long Status",
                status=very_long_status,
                file_uri="test://file/verylong",
                file_sha256=b"test_hash_very_long_status_123456"
            )
            db_session.add(nda2)
            db_session.flush()
            # If this works, column is appropriately sized
            assert nda2.status == very_long_status
        except Exception:
            # If this fails, that's expected - just ensure our longest real status works
            pass
            
        db_session.rollback()


class TestNDAStatusTransitions:
    """Test logical status transitions for NDA workflow"""

    @pytest.fixture(scope="class") 
    def db_engine(self):
        engine = create_engine(TEST_DB_URL)
        Base.metadata.create_all(engine)
        yield engine
        Base.metadata.drop_all(engine)

    @pytest.fixture
    def db_session(self, db_engine):
        Session = sessionmaker(bind=db_engine)
        session = Session()
        yield session
        session.rollback()
        session.close()

    def test_typical_workflow_status_progression(self, db_session):
        """Test typical NDA workflow status progression"""
        
        # Create NDA
        nda = NDARecord(
            counterparty_name="Acme Corp",
            file_uri="test://nda/acme",
            file_sha256=b"acme_nda_hash_123456789012345678"
        )
        db_session.add(nda)
        db_session.flush()
        
        # Verify starts as "created"
        assert nda.status == "created"
        
        # Start workflow - move to in_review
        nda.status = "in_review"
        db_session.flush()
        assert nda.status == "in_review"
        
        # LLM review (unsigned) - approve
        nda.status = "llm_reviewed_approved"
        db_session.flush()
        assert nda.status == "llm_reviewed_approved"
        
        # Human review (unsigned) - approve  
        nda.status = "reviewed"
        db_session.flush()
        assert nda.status == "reviewed"
        
        # Send to customer
        nda.status = "pending_signature"
        db_session.flush()
        assert nda.status == "pending_signature"
        
        # Customer signs and returns
        nda.status = "customer_signed"
        db_session.flush()
        assert nda.status == "customer_signed"
        
        # LLM review (signed) - approve
        nda.status = "llm_reviewed_approved"
        db_session.flush()
        assert nda.status == "llm_reviewed_approved"
        
        # Human review (signed) - approve
        nda.status = "reviewed"  
        db_session.flush()
        assert nda.status == "reviewed"
        
        # Internal signature 
        nda.status = "signed"
        db_session.flush()
        assert nda.status == "signed"
        
        # Activate
        nda.status = "active"
        db_session.flush()
        assert nda.status == "active"

    def test_rejection_workflow_paths(self, db_session):
        """Test workflow rejection paths"""
        
        # Test LLM rejection path
        nda1 = NDARecord(
            counterparty_name="Rejected Corp 1",
            file_uri="test://nda/rejected1", 
            file_sha256=b"rejected1_hash_123456789012345678",
            status="in_review"
        )
        db_session.add(nda1)
        db_session.flush()
        
        # LLM rejects
        nda1.status = "llm_reviewed_rejected"
        db_session.flush()
        assert nda1.status == "llm_reviewed_rejected"
        
        # End workflow
        nda1.status = "rejected"
        db_session.flush()
        assert nda1.status == "rejected"
        
        # Test human rejection path
        nda2 = NDARecord(
            counterparty_name="Rejected Corp 2",
            file_uri="test://nda/rejected2",
            file_sha256=b"rejected2_hash_123456789012345678", 
            status="llm_reviewed_approved"
        )
        db_session.add(nda2)
        db_session.flush()
        
        # Human rejects
        nda2.status = "rejected"
        db_session.flush()
        assert nda2.status == "rejected"

    def test_terminal_states(self, db_session):
        """Test terminal states (expired, terminated, archived)"""
        
        nda = NDARecord(
            counterparty_name="Terminal Corp",
            file_uri="test://nda/terminal",
            file_sha256=b"terminal_hash_123456789012345678",
            status="active"
        )
        db_session.add(nda)
        db_session.flush()
        
        # Test expiration
        nda.status = "expired"
        db_session.flush()
        assert nda.status == "expired"
        
        # Test archiving
        nda.status = "archived"
        db_session.flush()
        assert nda.status == "archived"
        
        # Test termination (create new NDA since we can't un-archive)
        nda2 = NDARecord(
            counterparty_name="Terminated Corp",
            file_uri="test://nda/terminated",
            file_sha256=b"terminated_hash_12345678901234567",
            status="active"
        )
        db_session.add(nda2)
        db_session.flush()
        
        nda2.status = "terminated"
        db_session.flush()
        assert nda2.status == "terminated"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
