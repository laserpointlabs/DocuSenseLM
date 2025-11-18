#!/usr/bin/env python3
"""
End-to-end email system test
Tests the complete flow: Create NDA → Send Email → Verify in MailHog → Test Parser
"""
import os
import sys
import asyncio
import uuid
import requests
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import NDARecord, EmailMessage, Document, DocumentStatus
from api.services.email_service import get_email_service
from api.services.email_parser import EmailParser
from api.services.service_registry import get_storage_service
from api.services.bootstrap import configure_services_from_env


API_BASE_URL = os.getenv("API_URL", "http://localhost:8000")
# Use service name when running in Docker, localhost when running locally
MAILHOG_HOST = os.getenv("MAILHOG_HOST", "mailhog")  # Default to service name for Docker
MAILHOG_API_URL = f"http://{MAILHOG_HOST}:8025/api/v2"


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def check_mailhog():
    """Check if MailHog is running"""
    try:
        response = requests.get(f"{MAILHOG_API_URL}/messages", timeout=2)
        if response.status_code == 200:
            return True
    except Exception:
        pass
    return False


def get_mailhog_messages():
    """Get all messages from MailHog"""
    try:
        response = requests.get(f"{MAILHOG_API_URL}/messages")
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching MailHog messages: {e}")
    return None


def find_email_by_subject(messages, subject):
    """Find an email by subject in MailHog messages"""
    if not messages or 'items' not in messages:
        return None
    
    for item in messages['items']:
        if 'Content' in item and 'Headers' in item['Content']:
            headers = item['Content']['Headers']
            if 'Subject' in headers:
                email_subject = headers['Subject'][0] if isinstance(headers['Subject'], list) else headers['Subject']
                if subject.lower() in email_subject.lower():
                    return item
    return None


def create_test_template():
    """Create a test NDA template"""
    print_section("Step 1: Create Test Template")
    
    db = get_db_session()
    try:
        from api.db.schema import NDATemplate
        
        # Check if template already exists
        existing = db.query(NDATemplate).filter(NDATemplate.name == "Test NDA Template").first()
        if existing:
            print(f"✓ Test template already exists: {existing.id}")
            return str(existing.id)
        
        # Create a simple test template
        # In a real scenario, we'd upload a DOCX file, but for testing we'll create a minimal record
        template = NDATemplate(
            name="Test NDA Template",
            description="Test template for E2E email testing",
            file_path="test/template_test.docx",
            is_active=True,
        )
        
        db.add(template)
        db.commit()
        db.refresh(template)
        
        print(f"✓ Created test template: {template.id}")
        return str(template.id)
    except Exception as e:
        print(f"✗ Failed to create template: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return None
    finally:
        db.close()


async def test_create_and_send_nda():
    """Test creating an NDA and sending it via email"""
    print_section("Step 2: Create NDA and Send Email")
    
    # Bootstrap services
    configure_services_from_env()
    
    # Get template ID
    template_id = create_test_template()
    if not template_id:
        print("✗ Cannot proceed without template")
        return None
    
    # Create a simple NDA document first
    db = get_db_session()
    try:
        # Create document
        test_content = b"Test NDA Document Content for E2E Testing"
        document = Document(
            filename="test_nda_e2e.docx",
            status=DocumentStatus.UPLOADED,
        )
        db.add(document)
        db.flush()
        document_id = str(document.id)
        
        # Upload to storage
        storage = get_storage_service()
        s3_path = storage.upload_file(
            bucket="nda-raw",
            object_name=f"{document_id}/test_nda_e2e.docx",
            file_data=test_content,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        document.s3_path = s3_path
        db.commit()
        
        # Create NDA record
        import hashlib
        unique_hash = hashlib.sha256(f"e2e_test_{uuid.uuid4()}".encode()).digest()
        
        nda_record = NDARecord(
            document_id=document.id,
            counterparty_name="E2E Test Company",
            counterparty_domain="e2etest.com",
            status="created",
            file_uri=s3_path,
            file_sha256=unique_hash,
        )
        db.add(nda_record)
        db.commit()
        db.refresh(nda_record)
        
        nda_id = str(nda_record.id)
        print(f"✓ Created NDA record: {nda_id}")
        print(f"  Counterparty: {nda_record.counterparty_name}")
        print(f"  Status: {nda_record.status}")
        
    except Exception as e:
        print(f"✗ Failed to create NDA: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return None
    finally:
        db.close()
    
    # Send email
    try:
        email_service = get_email_service()
        
        tracking_id = f"E2E-{nda_id[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"
        subject = f"E2E Test: Non-Disclosure Agreement - {nda_record.counterparty_name}"
        
        message_id = await email_service.send_email(
            to_addresses=["customer@e2etest.com"],
            subject=subject,
            body=f"Please find attached the NDA for {nda_record.counterparty_name}.",
            body_html=f"<p>Please find attached the <strong>NDA</strong> for {nda_record.counterparty_name}.</p>",
            attachments=[{
                'filename': 'NDA_E2E_Test.docx',
                'content': test_content,
            }],
            tracking_id=tracking_id,
            nda_record_id=nda_id,
        )
        
        print(f"✓ Email sent successfully!")
        print(f"  Message ID: {message_id}")
        print(f"  Tracking ID: {tracking_id}")
        print(f"  Subject: {subject}")
        
        return {
            'nda_id': nda_id,
            'message_id': message_id,
            'tracking_id': tracking_id,
            'subject': subject,
        }
        
    except Exception as e:
        print(f"✗ Failed to send email: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_mailhog_verification(email_info):
    """Verify email appears in MailHog"""
    print_section("Step 3: Verify Email in MailHog")
    
    if not email_info:
        print("✗ No email info to verify")
        return False
    
    if not check_mailhog():
        print("✗ MailHog is not running or not accessible")
        print(f"  Check: {MAILHOG_API_URL}")
        return False
    
    print("✓ MailHog is accessible")
    
    # Wait a moment for email to appear
    import time
    time.sleep(2)
    
    messages = get_mailhog_messages()
    if not messages:
        print("✗ Could not fetch messages from MailHog")
        return False
    
    print(f"✓ Found {messages.get('total', 0)} total emails in MailHog")
    
    # Find our email
    email_found = find_email_by_subject(messages, email_info['subject'])
    if email_found:
        print(f"✓ Found email with subject: {email_info['subject']}")
        
        # Check email details
        content = email_found.get('Content', {})
        headers = content.get('Headers', {})
        
        print(f"  From: {headers.get('From', ['Unknown'])[0]}")
        print(f"  To: {headers.get('To', ['Unknown'])[0]}")
        
        # Check for attachment
        if 'MIME' in email_found:
            mime_parts = email_found['MIME'].get('Parts', [])
            attachments = [p for p in mime_parts if p.get('FileName')]
            if attachments:
                print(f"  ✓ Found {len(attachments)} attachment(s)")
                for att in attachments:
                    print(f"    - {att.get('FileName', 'Unknown')}")
            else:
                print("  ⚠ No attachments found")
        
        return True
    else:
        print(f"✗ Could not find email with subject: {email_info['subject']}")
        print("  Available subjects:")
        for item in messages.get('items', [])[:5]:
            if 'Content' in item and 'Headers' in item['Content']:
                subj = item['Content']['Headers'].get('Subject', ['Unknown'])[0]
                print(f"    - {subj}")
        return False


def test_email_parser(email_info):
    """Test email parser linking"""
    print_section("Step 4: Test Email Parser")
    
    if not email_info:
        print("✗ No email info to test")
        return False
    
    # Simulate receiving an email reply
    parser = EmailParser()
    
    test_email = {
        'message_id': f'<e2e-test-{uuid.uuid4()}@e2etest.com>',
        'subject': f'Re: {email_info["subject"]}',
        'from_address': 'customer@e2etest.com',
        'to_addresses': ['nda-system@example.com'],
        'body': 'Here is the signed NDA.',
        'attachments': [{
            'filename': 'NDA_Signed_E2E.pdf',
            'content': b'Fake signed PDF content',
            'content_type': 'application/pdf',
        }],
        'tracking_id': email_info.get('tracking_id'),
    }
    
    try:
        # Test parser
        nda_id = parser.process_incoming_email_sync(test_email)
        
        if nda_id:
            print(f"✓ Email parser linked email to NDA: {nda_id}")
            
            # Verify it matches our created NDA
            if nda_id == email_info['nda_id']:
                print(f"✓ Parser correctly linked to our test NDA!")
            else:
                print(f"⚠ Parser linked to different NDA (expected: {email_info['nda_id']})")
            
            # Check attachment detection
            has_attachment = parser.has_nda_attachment(test_email)
            print(f"✓ Attachment detection: {has_attachment}")
            
            return True
        else:
            print("✗ Email parser did not link email to any NDA")
            print("  This might be expected if tracking ID matching isn't working")
            return False
            
    except Exception as e:
        print(f"✗ Email parser test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_email_record(email_info):
    """Verify email was stored in database"""
    print_section("Step 5: Verify Database Email Record")
    
    if not email_info:
        print("✗ No email info to verify")
        return False
    
    db = get_db_session()
    try:
        # Find email message by tracking ID
        email_msg = db.query(EmailMessage).filter(
            EmailMessage.tracking_id == email_info['tracking_id']
        ).first()
        
        if email_msg:
            print(f"✓ Found email message in database")
            print(f"  Message ID: {email_msg.message_id}")
            print(f"  Direction: {email_msg.direction}")
            print(f"  Subject: {email_msg.subject}")
            print(f"  NDA Record ID: {email_msg.nda_record_id}")
            print(f"  Sent at: {email_msg.sent_at}")
            
            if str(email_msg.nda_record_id) == email_info['nda_id']:
                print(f"✓ Email correctly linked to NDA record")
                return True
            else:
                print(f"⚠ Email linked to different NDA")
                return False
        else:
            print(f"✗ Email message not found in database")
            print(f"  Looking for tracking ID: {email_info['tracking_id']}")
            return False
            
    except Exception as e:
        print(f"✗ Database verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


async def main():
    """Run end-to-end email test"""
    print("\n" + "=" * 70)
    print("  END-TO-END EMAIL SYSTEM TEST")
    print("=" * 70)
    print("\nThis test verifies the complete email workflow:")
    print("  1. Create NDA")
    print("  2. Send email with attachment")
    print("  3. Verify in MailHog")
    print("  4. Test email parser")
    print("  5. Verify database records")
    print()
    
    # Check MailHog
    if not check_mailhog():
        print("⚠ WARNING: MailHog is not accessible")
        print(f"  Expected at: {MAILHOG_API_URL}")
        print("  Continuing anyway...")
    
    # Run tests
    email_info = await test_create_and_send_nda()
    
    if not email_info:
        print("\n✗ Failed to create and send NDA. Cannot continue.")
        return
    
    mailhog_ok = test_mailhog_verification(email_info)
    parser_ok = test_email_parser(email_info)
    db_ok = test_database_email_record(email_info)
    
    # Summary
    print_section("Test Summary")
    
    results = {
        "NDA Creation & Email Sending": "✓ PASS" if email_info else "✗ FAIL",
        "MailHog Verification": "✓ PASS" if mailhog_ok else "✗ FAIL",
        "Email Parser": "✓ PASS" if parser_ok else "✗ FAIL",
        "Database Record": "✓ PASS" if db_ok else "✗ FAIL",
    }
    
    for test_name, result in results.items():
        print(f"{test_name}: {result}")
    
    all_passed = all("PASS" in r for r in results.values())
    
    print("\n" + "=" * 70)
    if all_passed:
        print("  ✓ ALL TESTS PASSED")
    else:
        print("  ⚠ SOME TESTS FAILED")
    print("=" * 70)
    
    print("\nNext steps:")
    print("  1. Check MailHog UI: http://localhost:8025")
    print("  2. Verify email content and attachments")
    print("  3. Check database email_messages table")
    print("  4. Proceed with Camunda integration")


if __name__ == "__main__":
    asyncio.run(main())

