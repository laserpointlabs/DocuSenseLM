#!/usr/bin/env python3
"""
Test script for email system functionality
Tests email sending and receiving with MailHog
"""
import os
import sys
import asyncio
import uuid
from datetime import date

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import EmailConfig, NDARecord, User
from api.services.email_service import get_email_service, _encrypt_password
from api.services.email_parser import EmailParser
from api.services.registry_service import registry_service
from api.services.service_registry import get_storage_service
from api.services.bootstrap import configure_services_from_env


def setup_test_email_config():
    """Set up test email configuration for MailHog"""
    db = get_db_session()
    try:
        # Check if config already exists
        existing = db.query(EmailConfig).filter(EmailConfig.name == "test_mailhog").first()
        if existing:
            print("✓ Test email config already exists")
            return existing.id
        
        # Create test config for MailHog
        # MailHog SMTP: localhost:1025 (no auth)
        # MailHog IMAP: Not supported, but we can simulate receiving
        config = EmailConfig(
            name="test_mailhog",
            smtp_host="mailhog",  # Use service name in docker-compose
            smtp_port=1025,
            smtp_user="test@example.com",
            smtp_password_encrypted=_encrypt_password("test"),  # Not used by MailHog
            smtp_use_tls=False,
            imap_host=None,  # MailHog doesn't support IMAP
            imap_port=None,
            imap_user=None,
            imap_password_encrypted=None,
            imap_use_ssl=False,
            from_address="nda-system@example.com",
            from_name="NDA Management System",
            is_active=True,
        )
        
        db.add(config)
        db.commit()
        db.refresh(config)
        
        print(f"✓ Created test email config: {config.id}")
        return config.id
    except Exception as e:
        print(f"✗ Failed to create email config: {e}")
        db.rollback()
        return None
    finally:
        db.close()


async def test_send_email():
    """Test sending an email via MailHog"""
    print("\n=== Testing Email Sending ===")
    
    email_service = get_email_service()
    
    try:
        message_id = await email_service.send_email(
            to_addresses=["customer@example.com"],
            subject="Test NDA Email",
            body="This is a test email with an NDA attachment.",
            body_html="<p>This is a <strong>test email</strong> with an NDA attachment.</p>",
            attachments=[{
                'filename': 'test_nda.docx',
                'content': b'Fake NDA content for testing',
            }],
            tracking_id=f"TEST-{uuid.uuid4().hex[:8].upper()}",
        )
        
        print(f"✓ Email sent successfully!")
        print(f"  Message ID: {message_id}")
        print(f"  Check MailHog UI at http://localhost:8025")
        return True
    except Exception as e:
        print(f"✗ Failed to send email: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_create_test_nda():
    """Create a test NDA record for testing"""
    print("\n=== Creating Test NDA ===")
    
    db = get_db_session()
    try:
        # Create a dummy NDA record with unique hash
        import hashlib
        unique_hash = hashlib.sha256(f"test_nda_{uuid.uuid4()}".encode()).digest()
        
        test_nda = NDARecord(
            counterparty_name="Test Company Inc.",
            counterparty_domain="testcompany.com",
            status="created",
            file_uri=f"test/nda_test_{uuid.uuid4().hex[:8]}.docx",
            file_sha256=unique_hash,
        )
        
        db.add(test_nda)
        db.commit()
        db.refresh(test_nda)
        
        print(f"✓ Created test NDA: {test_nda.id}")
        print(f"  Counterparty: {test_nda.counterparty_name}")
        print(f"  Status: {test_nda.status}")
        return str(test_nda.id)
    except Exception as e:
        print(f"✗ Failed to create test NDA: {e}")
        db.rollback()
        return None
    finally:
        db.close()


async def test_send_nda_email(nda_id: str):
    """Test sending NDA via email"""
    print("\n=== Testing NDA Email Sending ===")
    
    from api.services.service_registry import get_storage_service
    
    # Create a dummy file in storage
    storage = get_storage_service()
    test_content = b"Fake NDA document content for testing"
    
    try:
        # Upload test file
        s3_path = storage.upload_file(
            bucket="nda-raw",
            object_name=f"{nda_id}/test_nda.docx",
            file_data=test_content,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        print(f"✓ Uploaded test file: {s3_path}")
        
        # Get email service
        email_service = get_email_service()
        
        # Send email
        tracking_id = f"NDA-{nda_id[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"
        message_id = await email_service.send_email(
            to_addresses=["customer@testcompany.com"],
            subject="Non-Disclosure Agreement - Test Company Inc.",
            body="Please find attached the NDA for your review and signature.",
            body_html="<p>Please find attached the <strong>NDA</strong> for your review and signature.</p>",
            attachments=[{
                'filename': 'NDA_Test_Company_Inc.docx',
                'content': test_content,
            }],
            tracking_id=tracking_id,
            nda_record_id=nda_id,
        )
        
        print(f"✓ NDA email sent successfully!")
        print(f"  Message ID: {message_id}")
        print(f"  Tracking ID: {tracking_id}")
        print(f"  Check MailHog UI at http://localhost:8025")
        return True
    except Exception as e:
        print(f"✗ Failed to send NDA email: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_email_parser():
    """Test email parser functionality"""
    print("\n=== Testing Email Parser ===")
    
    parser = EmailParser()
    
    # Simulate email data
    test_email = {
        'message_id': f'<test-{uuid.uuid4()}@example.com>',
        'subject': 'Re: Non-Disclosure Agreement - Test Company Inc.',
        'from_address': 'customer@testcompany.com',
        'to_addresses': ['nda-system@example.com'],
        'body': 'Here is the signed NDA.',
        'attachments': [{
            'filename': 'NDA_Signed.pdf',
            'content': b'Fake signed PDF content',
            'content_type': 'application/pdf',
        }],
        'tracking_id': None,  # Will try to find by content
    }
    
    try:
        nda_id = parser.process_incoming_email_sync(test_email)
        print(f"✓ Email parsed successfully")
        print(f"  Linked to NDA: {nda_id or 'None (not linked)'}")
        print(f"  Has NDA attachment: {parser.has_nda_attachment(test_email)}")
        return True
    except Exception as e:
        print(f"✗ Failed to parse email: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all email system tests"""
    print("=" * 60)
    print("Email System Test Suite")
    print("=" * 60)
    print("\nPrerequisites:")
    print("  1. MailHog should be running (docker-compose up mailhog)")
    print("  2. Database should be accessible")
    print("  3. Storage service should be configured")
    print()
    
    # Bootstrap services
    print("=== Bootstrapping Services ===")
    try:
        configure_services_from_env()
        print("✓ Services configured")
    except Exception as e:
        print(f"⚠ Warning: Service bootstrap failed: {e}")
        print("  Continuing anyway...")
    
    # Setup
    print("\n=== Setup ===")
    config_id = setup_test_email_config()
    if not config_id:
        print("✗ Failed to set up email config. Exiting.")
        return
    
    # Test 1: Basic email sending
    success1 = await test_send_email()
    
    # Test 2: Create test NDA
    nda_id = test_create_test_nda()
    if not nda_id:
        print("✗ Failed to create test NDA. Skipping NDA email test.")
    else:
        # Test 3: Send NDA email
        success2 = await test_send_nda_email(nda_id)
    
    # Test 4: Email parser
    success3 = test_email_parser()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Email sending: {'✓ PASS' if success1 else '✗ FAIL'}")
    if nda_id:
        print(f"NDA email sending: {'✓ PASS' if success2 else '✗ FAIL'}")
    print(f"Email parsing: {'✓ PASS' if success3 else '✗ FAIL'}")
    print("\nNext steps:")
    print("  1. Check MailHog UI at http://localhost:8025 to see sent emails")
    print("  2. Test receiving emails by manually adding to MailHog")
    print("  3. Verify email poller is running (check API logs)")


if __name__ == "__main__":
    asyncio.run(main())

