#!/usr/bin/env python3
"""
Test suite for NDA Email Service

Tests the email service that handles:
1. SMTP email sending (NDAs to customers)
2. IMAP email receiving (signed NDAs from customers) 
3. Email configuration management (SMTP/IMAP settings)
4. Email tracking (tracking_id linking emails to NDAs)
5. Email security (encrypted passwords, validation)
6. Email parsing (extract attachments, link to NDAs)
7. Error handling and edge cases

Following TDD approach - comprehensive tests before implementation.
"""

import pytest
import uuid
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import List, Dict, Any

# We'll create these as we implement
from api.services.email_service import (
    EmailService, EmailConfigurationError, EmailSendError, 
    EmailReceiveError, EmailParser, get_email_service, create_email_service
)
from api.db.schema import EmailConfig, EmailMessage, NDARecord


class TestEmailServiceConfiguration:
    """Test email service configuration and initialization"""
    
    def test_email_service_initializes(self):
        """Test that EmailService can be created"""
        service = EmailService()
        assert service is not None
        assert hasattr(service, '_config_cache')

    @patch('api.services.email_service.get_db_session')
    def test_get_active_config_from_database(self, mock_db_session):
        """Test retrieving email config from database"""
        # Mock email config
        mock_config = Mock(spec=EmailConfig)
        mock_config.smtp_host = "smtp.example.com"
        mock_config.smtp_port = 587
        mock_config.smtp_user = "nda@example.com"
        mock_config.from_address = "nda@example.com"
        mock_config.is_active = True
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_config
        
        service = EmailService()
        config = service._get_active_config()
        
        assert config == mock_config
        assert config.smtp_host == "smtp.example.com"
        mock_db.close.assert_called()

    def test_get_active_config_from_env_vars(self):
        """Test retrieving email config from environment variables"""
        with patch.dict('os.environ', {
            'EMAIL_SMTP_HOST': 'smtp.test.com',
            'EMAIL_SMTP_PORT': '587',
            'EMAIL_SMTP_USER': 'test@test.com',
            'EMAIL_SMTP_PASSWORD': 'testpassword',
            'EMAIL_FROM_ADDRESS': 'nda@test.com'
        }):
            service = EmailService()
            config = service._get_active_config()
            
            assert config is not None
            assert config.smtp_host == 'smtp.test.com'
            assert config.smtp_port == 587
            assert config.from_address == 'nda@test.com'
            assert config.is_active is True

    def test_no_config_available(self):
        """Test behavior when no email config is available"""
        with patch('api.services.email_service.get_db_session') as mock_db_session:
            mock_db = Mock()
            mock_db_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None
            
            with patch.dict('os.environ', {}, clear=True):
                service = EmailService()
                config = service._get_active_config()
                
                assert config is None


class TestEmailServiceSending:
    """Test email sending functionality (SMTP)"""
    
    @pytest.mark.asyncio
    @patch('api.services.email_service.aiosmtplib.send')
    @patch('api.services.email_service.get_db_session') 
    async def test_send_email_success(self, mock_db_session, mock_smtp_send):
        """Test successful email sending"""
        # Mock email config
        service = EmailService()
        service._config_cache = Mock(spec=EmailConfig)
        service._config_cache.smtp_host = "smtp.test.com"
        service._config_cache.smtp_port = 587
        service._config_cache.from_address = "nda@test.com"
        service._config_cache.from_name = "NDA System"
        service._config_cache.smtp_password_encrypted = "encrypted_password"
        service._config_cache.smtp_use_tls = True
        
        # Mock SMTP send
        mock_smtp_send.return_value = None
        
        # Mock database for email message storage
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        
        # Mock password decryption
        with patch('api.services.email_service._decrypt_password', return_value='decrypted_password'):
            message_id = await service.send_email(
                to_addresses=["customer@example.com"],
                subject="NDA for Review",
                body="Please review the attached NDA.",
                attachments=[{
                    'filename': 'NDA.pdf',
                    'content': b'fake_pdf_content'
                }],
                tracking_id="NDA-12345678"
            )
        
        # Should return a message ID
        assert isinstance(message_id, str)
        assert len(message_id) > 0
        
        # Should have called SMTP send
        mock_smtp_send.assert_called_once()
        
        # Should have stored email message in database
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_send_email_no_config_error(self):
        """Test sending email when no configuration is available"""
        service = EmailService()
        service._config_cache = None
        
        with patch.object(service, '_get_active_config', return_value=None):
            with pytest.raises(EmailConfigurationError) as exc_info:
                await service.send_email(
                    to_addresses=["test@example.com"],
                    subject="Test",
                    body="Test body"
                )
        
        assert "configuration" in str(exc_info.value).lower()

    @pytest.mark.asyncio  
    @patch('api.services.email_service.aiosmtplib.send')
    async def test_send_email_smtp_failure(self, mock_smtp_send):
        """Test handling SMTP failures"""
        # Mock config
        service = EmailService()
        service._config_cache = Mock(spec=EmailConfig)
        service._config_cache.smtp_host = "smtp.test.com"
        service._config_cache.from_address = "nda@test.com"
        
        # Mock SMTP failure
        mock_smtp_send.side_effect = Exception("SMTP server unavailable")
        
        with patch('api.services.email_service._decrypt_password', return_value='password'):
            with pytest.raises(EmailSendError) as exc_info:
                await service.send_email(
                    to_addresses=["test@example.com"],
                    subject="Test",
                    body="Test body"
                )
        
        assert "smtp" in str(exc_info.value).lower() or "send" in str(exc_info.value).lower()

    def test_email_validation(self):
        """Test email address validation"""
        service = EmailService()
        
        # Test valid emails
        valid_emails = [
            "test@example.com",
            "user.name@company.co.uk", 
            "nda+tracking@domain.org"
        ]
        
        for email in valid_emails:
            assert service._validate_email_address(email) is True
        
        # Test invalid emails
        invalid_emails = [
            "invalid-email",
            "@domain.com",
            "user@", 
            "user space@domain.com",
            ""
        ]
        
        for email in invalid_emails:
            assert service._validate_email_address(email) is False


class TestEmailServiceReceiving:
    """Test email receiving functionality (IMAP)"""
    
    @pytest.mark.asyncio
    @patch('api.services.email_service.aioimaplib.IMAP4_SSL')
    async def test_check_for_new_emails_success(self, mock_imap):
        """Test successful email checking and retrieval"""
        # Mock IMAP client
        mock_imap_client = AsyncMock()
        mock_imap.return_value = mock_imap_client
        
        # Mock IMAP responses
        mock_imap_client.login.return_value = ('OK', [b'LOGIN completed'])
        mock_imap_client.select.return_value = ('OK', [b'10'])  # 10 messages
        mock_imap_client.search.return_value = ('OK', [b'1 2 3'])  # 3 unseen
        
        # Mock email fetch
        mock_email_data = b"""From: customer@example.com
To: nda@test.com
Subject: Re: NDA for Review 
Message-ID: <test123@example.com>

Please find the signed NDA attached.
"""
        mock_imap_client.fetch.return_value = ('OK', [(b'1', mock_email_data)])
        
        # Mock config
        service = EmailService()
        service._config_cache = Mock(spec=EmailConfig)
        service._config_cache.imap_host = "imap.test.com"
        service._config_cache.imap_port = 993
        service._config_cache.imap_user = "nda@test.com"
        service._config_cache.imap_password_encrypted = "encrypted_password"
        service._config_cache.imap_use_ssl = True
        
        with patch('api.services.email_service._decrypt_password', return_value='password'):
            emails = await service.check_for_new_emails()
        
        # Should return list of email data
        assert isinstance(emails, list)
        mock_imap_client.login.assert_called()
        mock_imap_client.select.assert_called()

    @pytest.mark.asyncio
    async def test_check_emails_no_imap_config(self):
        """Test checking emails when IMAP is not configured"""
        service = EmailService()
        service._config_cache = Mock(spec=EmailConfig)
        service._config_cache.imap_host = None  # No IMAP configured
        
        with pytest.raises(EmailConfigurationError) as exc_info:
            await service.check_for_new_emails()
        
        assert "imap" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    @patch('api.services.email_service.aioimaplib.IMAP4_SSL')
    async def test_check_emails_imap_failure(self, mock_imap):
        """Test handling IMAP connection failures"""
        # Mock IMAP connection failure
        mock_imap.side_effect = Exception("IMAP server unavailable")
        
        service = EmailService()
        service._config_cache = Mock(spec=EmailConfig)
        service._config_cache.imap_host = "imap.test.com"
        
        with pytest.raises(EmailReceiveError) as exc_info:
            await service.check_for_new_emails()
        
        assert "imap" in str(exc_info.value).lower() or "receive" in str(exc_info.value).lower()


class TestEmailServiceTracking:
    """Test email tracking and linking functionality"""
    
    @pytest.mark.asyncio
    @patch('api.services.email_service.get_db_session')
    async def test_store_sent_email_with_tracking(self, mock_db_session):
        """Test storing sent email with tracking ID"""
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        
        service = EmailService()
        
        email_data = {
            'message_id': '<test123@example.com>',
            'to_addresses': ['customer@example.com'],
            'subject': 'NDA for Review',
            'body': 'Please review attached NDA',
            'tracking_id': 'NDA-ABCD1234',
            'nda_record_id': str(uuid.uuid4())
        }
        
        await service._store_sent_email(email_data)
        
        # Should store EmailMessage record
        mock_db.add.assert_called()
        mock_db.commit.assert_called()
        
        # Check EmailMessage fields
        stored_email = mock_db.add.call_args[0][0]
        assert stored_email.direction == 'sent'
        assert stored_email.tracking_id == 'NDA-ABCD1234'

    @pytest.mark.asyncio
    @patch('api.services.email_service.get_db_session')
    async def test_store_received_email_with_linking(self, mock_db_session):
        """Test storing received email and linking to NDA"""
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        
        # Mock finding existing sent email by tracking ID
        mock_sent_email = Mock(spec=EmailMessage)
        mock_sent_email.nda_record_id = str(uuid.uuid4())
        mock_db.query.return_value.filter.return_value.first.return_value = mock_sent_email
        
        service = EmailService()
        
        email_data = {
            'message_id': '<reply456@example.com>',
            'from_address': 'customer@example.com',
            'to_addresses': ['nda@test.com'],
            'subject': 'Re: NDA for Review',
            'body': 'Signed NDA attached',
            'tracking_id': 'NDA-ABCD1234',  # Links to sent email
            'attachments': [{
                'filename': 'Signed_NDA.pdf',
                'content': b'fake_signed_pdf_content'
            }]
        }
        
        linked_nda_id = await service._store_received_email(email_data)
        
        # Should find and link to NDA
        assert linked_nda_id == mock_sent_email.nda_record_id
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_generate_tracking_id(self):
        """Test tracking ID generation"""
        service = EmailService()
        
        nda_id = str(uuid.uuid4())
        tracking_id = service._generate_tracking_id(nda_id)
        
        # Should be properly formatted
        assert tracking_id.startswith('NDA-')
        assert len(tracking_id) >= 12  # NDA- + 8 chars + - + more chars
        assert nda_id[:8].upper() in tracking_id  # Should include NDA ID prefix

    def test_extract_tracking_id_from_email(self):
        """Test extracting tracking ID from email content"""
        service = EmailService()
        
        # Test extraction from subject
        subject_with_tracking = "Re: NDA for Review [NDA-ABCD1234]"
        tracking_id = service._extract_tracking_id(subject_with_tracking, "")
        assert tracking_id == "NDA-ABCD1234"
        
        # Test extraction from body
        body_with_tracking = """
        Dear Client,
        
        Thank you for your response.
        Tracking ID: NDA-EFGH5678
        
        Best regards
        """
        tracking_id = service._extract_tracking_id("", body_with_tracking)
        assert tracking_id == "NDA-EFGH5678"
        
        # Test no tracking ID found
        tracking_id = service._extract_tracking_id("No tracking", "No tracking here")
        assert tracking_id is None


class TestEmailServiceSecurity:
    """Test email security features"""
    
    def test_password_encryption_decryption(self):
        """Test password encryption and decryption"""
        from api.services.email_service import _encrypt_password, _decrypt_password
        from cryptography.fernet import Fernet
        import base64
        
        # Use consistent key for test
        test_key = Fernet.generate_key()
        test_key_b64 = base64.urlsafe_b64encode(test_key).decode()
        
        with patch.dict('os.environ', {'EMAIL_ENCRYPTION_KEY': test_key_b64}):
            original_password = "test_smtp_password_123"
            
            # Encrypt password
            encrypted = _encrypt_password(original_password)
            
            # Should be encrypted (different from original)
            assert encrypted != original_password
            assert len(encrypted) > len(original_password)
            
            # Decrypt password
            decrypted = _decrypt_password(encrypted)
            
            # Should match original
            assert decrypted == original_password

    def test_password_encryption_key_handling(self):
        """Test encryption key generation and handling"""
        from api.services.email_service import _get_encryption_key
        
        # Test key generation when no env var set
        with patch.dict('os.environ', {}, clear=True):
            key1 = _get_encryption_key()
            # Fernet.generate_key() returns base64-encoded key (44 bytes)
            assert len(key1) == 44  # Base64-encoded key length
        
        # Test key from environment
        import base64
        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key()  # This is already base64-encoded (44 bytes)
        
        with patch.dict('os.environ', {'EMAIL_ENCRYPTION_KEY': test_key.decode()}):
            key2 = _get_encryption_key()
            assert len(key2) == 32  # Should be decoded to raw 32 bytes

    @pytest.mark.asyncio
    async def test_email_content_sanitization(self):
        """Test that email content is properly sanitized"""
        service = EmailService()
        service._config_cache = Mock(spec=EmailConfig)
        service._config_cache.from_address = "nda@test.com"
        
        # Test with potentially malicious content
        unsafe_subject = "NDA <script>alert('hack')</script>"
        unsafe_body = "Dear Client,\n\n${system.exit(1)}\n\nBest regards"
        
        with patch('api.services.email_service.aiosmtplib.send'):
            with patch('api.services.email_service.get_db_session'):
                with patch('api.services.email_service._decrypt_password', return_value='password'):
                    try:
                        await service.send_email(
                            to_addresses=["test@example.com"],
                            subject=unsafe_subject,
                            body=unsafe_body
                        )
                        # Should not crash - content should be sanitized
                    except Exception as e:
                        # If it fails, should not be due to injection
                        assert "script" not in str(e).lower()
                        assert "system.exit" not in str(e)


class TestEmailServiceAttachments:
    """Test email attachment handling"""
    
    @pytest.mark.asyncio
    async def test_send_email_with_pdf_attachment(self):
        """Test sending email with PDF attachment"""
        service = EmailService()
        service._config_cache = Mock(spec=EmailConfig)
        service._config_cache.smtp_host = "smtp.test.com"
        service._config_cache.from_address = "nda@test.com"
        
        pdf_content = b'%PDF-1.4\n%fake_pdf_content'
        attachments = [{
            'filename': 'NDA_Agreement.pdf',
            'content': pdf_content
        }]
        
        with patch('api.services.email_service.aiosmtplib.send') as mock_send:
            with patch('api.services.email_service.get_db_session'):
                with patch('api.services.email_service._decrypt_password', return_value='password'):
                    await service.send_email(
                        to_addresses=["customer@example.com"],
                        subject="NDA for Review",
                        body="Please review attached NDA.",
                        attachments=attachments
                    )
        
        # Should have called SMTP with attachment
        mock_send.assert_called_once()
        send_args = mock_send.call_args[1]
        
        # Should have been called (attachment handling happens in send_email)
        assert mock_send.called

    def test_parse_email_attachments(self):
        """Test parsing attachments from received emails"""
        service = EmailService()
        
        # Mock email message with attachment
        mock_email_msg = Mock()
        mock_email_msg.is_multipart.return_value = True
        
        # Mock attachment part
        mock_attachment = Mock()
        mock_attachment.get_content_disposition.return_value = 'attachment'
        mock_attachment.get_filename.return_value = 'Signed_NDA.pdf'
        mock_attachment.get_payload.return_value = b'%PDF-signed_content'
        mock_attachment.get_content_type.return_value = 'application/pdf'
        
        mock_email_msg.get_payload.return_value = [Mock(), mock_attachment]  # Text + attachment
        
        attachments = service._parse_attachments(mock_email_msg)
        
        assert len(attachments) == 1
        assert attachments[0]['filename'] == 'Signed_NDA.pdf'
        assert attachments[0]['content'] == b'%PDF-signed_content'
        assert attachments[0]['content_type'] == 'application/pdf'


class TestEmailServiceIntegration:
    """Test email service integration with NDA records"""
    
    @pytest.mark.asyncio
    @patch('api.services.email_service.get_db_session')
    async def test_link_received_email_to_nda(self, mock_db_session):
        """Test linking received email to existing NDA record"""
        nda_uuid = str(uuid.uuid4())
        
        # Mock finding NDA by tracking ID
        mock_sent_email = Mock(spec=EmailMessage)
        mock_sent_email.nda_record_id = nda_uuid
        
        mock_db = Mock() 
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_sent_email
        
        service = EmailService()
        
        email_data = {
            'message_id': '<reply@example.com>',
            'tracking_id': 'NDA-ABCD1234',
            'from_address': 'customer@example.com',
            'subject': 'Re: NDA for Review',
            'attachments': [{
                'filename': 'Signed_NDA.pdf',
                'content': b'%PDF-signed_content'
            }]
        }
        
        linked_nda_id = await service._link_email_to_nda(email_data)
        
        assert linked_nda_id == nda_uuid

    def test_email_parser_integration(self):
        """Test integration with EmailParser for processing"""
        service = EmailService()
        parser = EmailParser()
        
        # Test that service can work with parser
        assert hasattr(parser, 'process_incoming_email') or hasattr(parser, 'parse_email')
        
        # Should be able to create both services
        assert service is not None
        assert parser is not None


class TestEmailServiceErrorHandling:
    """Test email service error handling"""
    
    @pytest.mark.asyncio
    async def test_malformed_email_handling(self):
        """Test handling of malformed email data"""
        service = EmailService()
        
        # Test with missing required fields 
        with pytest.raises((EmailSendError, EmailConfigurationError, ValueError, TypeError)) as exc_info:
            # Call with missing required arguments
            await service.send_email(
                to_addresses=[],  # Empty list should fail
                subject="Test", 
                body="Test body"
            )
        
        error_msg = str(exc_info.value).lower()
        # Should fail due to no config or empty address list
        assert "address" in error_msg or "required" in error_msg or "configuration" in error_msg

    @pytest.mark.asyncio  
    @patch('api.services.email_service.get_db_session')
    async def test_database_failure_during_email_storage(self, mock_db_session):
        """Test handling database failures when storing email records"""
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.commit.side_effect = Exception("Database unavailable")
        
        service = EmailService()
        
        email_data = {
            'message_id': '<test@example.com>',
            'direction': 'sent',
            'to_addresses': ['customer@example.com'],
            'subject': 'Test',
            'body': 'Test body'
        }
        
        # Should handle database failure gracefully
        try:
            await service._store_email_record(email_data)
        except Exception as e:
            # Should rollback on failure
            mock_db.rollback.assert_called()
            assert "database" in str(e).lower()

    def test_concurrent_access_safety(self):
        """Test that email service handles concurrent access safely"""
        service = EmailService()
        
        # Multiple instances should not interfere
        service1 = EmailService()
        service2 = EmailService()
        
        assert service1 is not service2
        assert hasattr(service1, '_config_cache')
        assert hasattr(service2, '_config_cache')
        
        # Global service should be singleton
        global_service1 = get_email_service()
        global_service2 = get_email_service()
        assert global_service1 is global_service2


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
