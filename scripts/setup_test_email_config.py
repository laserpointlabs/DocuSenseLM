#!/usr/bin/env python3
"""
Quick script to set up test email configuration for MailHog
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import EmailConfig
from api.services.email_service import _encrypt_password


def main():
    """Set up test email config"""
    db = get_db_session()
    try:
        # Check if config already exists
        existing = db.query(EmailConfig).filter(EmailConfig.name == "test_mailhog").first()
        if existing:
            print(f"✓ Test email config already exists: {existing.id}")
            print(f"  SMTP: {existing.smtp_host}:{existing.smtp_port}")
            print(f"  From: {existing.from_address}")
            return
        
        # Create test config for MailHog
        config = EmailConfig(
            name="test_mailhog",
            smtp_host="mailhog",  # Use service name in docker-compose
            smtp_port=1025,
            smtp_user="test@example.com",
            smtp_password_encrypted=_encrypt_password("test"),
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
        print(f"  SMTP: {config.smtp_host}:{config.smtp_port}")
        print(f"  From: {config.from_address}")
        print(f"\nMailHog UI: http://localhost:8025")
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()








