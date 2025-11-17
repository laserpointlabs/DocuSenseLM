"""
Email service for sending and receiving emails via SMTP/IMAP

Handles:
- SMTP email sending (NDAs to customers)
- IMAP email receiving (signed NDAs from customers)  
- Email configuration (SMTP/IMAP settings with encrypted passwords)
- Email tracking (tracking_id linking emails to NDAs)
- Email security (password encryption, content sanitization)
- Email parsing (attachments, message linking)
"""

import aiosmtplib
import aioimaplib
import asyncio
import re
import uuid
import logging
import os
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.message import EmailMessage as StdEmailMessage
from typing import List, Optional, Dict, Any
from datetime import datetime
from cryptography.fernet import Fernet

from api.db import get_db_session
from api.db.schema import EmailConfig, EmailMessage, NDARecord

logger = logging.getLogger(__name__)


class EmailConfigurationError(Exception):
    """Raised when email configuration is invalid or missing"""
    pass


class EmailSendError(Exception):
    """Raised when email sending fails"""
    pass


class EmailReceiveError(Exception):
    """Raised when email receiving fails"""
    pass


def _get_encryption_key() -> bytes:
    """Get or generate encryption key for passwords"""
    key_env = os.getenv("EMAIL_ENCRYPTION_KEY")
    if key_env:
        try:
            # Key might be base64 encoded string, decode to bytes
            if isinstance(key_env, str):
                decoded = base64.urlsafe_b64decode(key_env.encode())
                return decoded
            return key_env
        except Exception:
            logger.warning("Invalid EMAIL_ENCRYPTION_KEY format, generating new key")
            return Fernet.generate_key()
    
    # Generate a key if not set (for development/testing only)  
    key = Fernet.generate_key()
    logger.warning("EMAIL_ENCRYPTION_KEY not set, using generated key (not persistent)")
    return key


def _encrypt_password(password: str) -> str:
    """Encrypt password for storage"""
    key = _get_encryption_key()
    # Ensure key is in the right format for Fernet
    if len(key) == 32:
        # Raw 32 bytes, need to base64 encode for Fernet
        key = base64.urlsafe_b64encode(key)
    fernet = Fernet(key)
    return fernet.encrypt(password.encode()).decode()


def _decrypt_password(encrypted_password: str) -> str:
    """Decrypt password from storage"""
    key = _get_encryption_key()
    # Ensure key is in the right format for Fernet
    if len(key) == 32:
        # Raw 32 bytes, need to base64 encode for Fernet
        key = base64.urlsafe_b64encode(key)
    fernet = Fernet(key)
    return fernet.decrypt(encrypted_password.encode()).decode()


class EmailService:
    """Email service for sending and receiving emails"""

    def __init__(self):
        self._config_cache: Optional[EmailConfig] = None

    def _get_active_config(self) -> Optional[EmailConfig]:
        """Get active email configuration from env vars or database"""
        # Check if config is provided via environment variables
        smtp_host = os.getenv("EMAIL_SMTP_HOST")
        if smtp_host:
            # Create config from environment variables
            config = EmailConfig(
                smtp_host=smtp_host,
                smtp_port=int(os.getenv("EMAIL_SMTP_PORT", "587")),
                smtp_user=os.getenv("EMAIL_SMTP_USER", ""),
                smtp_password_encrypted=_encrypt_password(os.getenv("EMAIL_SMTP_PASSWORD", "")) if os.getenv("EMAIL_SMTP_PASSWORD") else "",
                smtp_use_tls=os.getenv("EMAIL_SMTP_USE_TLS", "true").lower() == "true",
                imap_host=os.getenv("EMAIL_IMAP_HOST"),
                imap_port=int(os.getenv("EMAIL_IMAP_PORT", "993")) if os.getenv("EMAIL_IMAP_PORT") else None,
                imap_user=os.getenv("EMAIL_IMAP_USER"),
                imap_password_encrypted=_encrypt_password(os.getenv("EMAIL_IMAP_PASSWORD", "")) if os.getenv("EMAIL_IMAP_PASSWORD") else None,
                imap_use_ssl=os.getenv("EMAIL_IMAP_USE_SSL", "true").lower() == "true" if os.getenv("EMAIL_IMAP_USE_SSL") else None,
                from_address=os.getenv("EMAIL_FROM_ADDRESS", "nda-system@example.com"),
                from_name=os.getenv("EMAIL_FROM_NAME", "NDA Management System"),
                is_active=True,
            )
            return config
        
        # Fall back to database config
        if self._config_cache and self._config_cache.is_active:
            return self._config_cache

        db = get_db_session()
        try:
            config = db.query(EmailConfig).filter(EmailConfig.is_active == True).first()
            if config:
                self._config_cache = config
            return config
        finally:
            db.close()

    async def send_email(
        self,
        to_addresses: List[str],
        subject: str,
        body: str,
        body_html: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        tracking_id: Optional[str] = None,
        nda_record_id: Optional[str] = None,
    ) -> str:
        """
        Send email via SMTP
        
        Returns:
            Message ID of sent email
        """
        config = self._get_active_config()
        if not config:
            raise EmailConfigurationError("No active email configuration found")

        # Validate recipients
        if not to_addresses:
            raise EmailSendError("At least one recipient email address is required")
        
        for email in to_addresses:
            if not self._validate_email_address(email):
                raise EmailSendError(f"Invalid email address: {email}")

        # Decrypt SMTP password
        smtp_password = None
        if config.smtp_password_encrypted:
            try:
                smtp_password = _decrypt_password(config.smtp_password_encrypted)
            except Exception as e:
                logger.warning(f"Failed to decrypt SMTP password: {e}")

        # Create email message
        message = MIMEMultipart()
        message['From'] = f"{config.from_name} <{config.from_address}>" if config.from_name else config.from_address
        message['To'] = ', '.join(to_addresses)
        message['Subject'] = self._sanitize_email_content(subject)
        
        if cc_addresses:
            message['CC'] = ', '.join(cc_addresses)
        
        if tracking_id:
            message['X-NDA-Tracking-ID'] = tracking_id

        # Add body
        sanitized_body = self._sanitize_email_content(body)
        message.attach(MIMEText(sanitized_body, 'plain'))
        
        if body_html:
            sanitized_html = self._sanitize_email_content(body_html)
            message.attach(MIMEText(sanitized_html, 'html'))

        # Add attachments
        if attachments:
            for attachment in attachments:
                self._add_attachment(message, attachment)

        # Generate message ID
        message_id = f"<{uuid.uuid4()}@{config.smtp_host}>"
        message['Message-ID'] = message_id

        # Send via SMTP
        try:
            await aiosmtplib.send(
                message,
                hostname=config.smtp_host,
                port=config.smtp_port,
                start_tls=config.smtp_use_tls,
                username=config.smtp_user if config.smtp_user else None,
                password=smtp_password,
            )
            
            logger.info(f"Sent email {message_id} to {to_addresses}")
            
            # Store sent email record
            await self._store_sent_email({
                'message_id': message_id,
                'to_addresses': to_addresses,
                'cc_addresses': cc_addresses or [],
                'subject': subject,
                'body': body,
                'tracking_id': tracking_id,
                'nda_record_id': nda_record_id,
            })
            
            return message_id

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise EmailSendError(f"Failed to send email: {str(e)}")

    async def check_for_new_emails(self) -> List[Dict[str, Any]]:
        """Check for new emails via IMAP"""
        config = self._get_active_config()
        if not config or not config.imap_host:
            raise EmailConfigurationError("IMAP configuration not available")

        # Decrypt IMAP password
        imap_password = None
        if config.imap_password_encrypted:
            try:
                imap_password = _decrypt_password(config.imap_password_encrypted)
            except Exception as e:
                logger.warning(f"Failed to decrypt IMAP password: {e}")

        try:
            # Connect to IMAP
            if config.imap_use_ssl:
                imap = aioimaplib.IMAP4_SSL(
                    host=config.imap_host,
                    port=config.imap_port or 993
                )
            else:
                imap = aioimaplib.IMAP4(
                    host=config.imap_host,
                    port=config.imap_port or 143
                )

            await imap.wait_hello_from_server()
            
            # Login
            await imap.login(config.imap_user, imap_password)
            
            # Select inbox
            await imap.select('INBOX')
            
            # Search for unseen emails
            search_response = await imap.search('UNSEEN')
            
            if search_response[0] != 'OK':
                logger.warning("IMAP search failed")
                return []
            
            message_ids = search_response[1][0].decode().split() if search_response[1][0] else []
            
            emails = []
            for msg_id in message_ids:
                try:
                    fetch_response = await imap.fetch(msg_id, '(RFC822)')
                    if fetch_response[0] == 'OK':
                        email_data = self._parse_email_message(fetch_response[1][0][1])
                        if email_data:
                            emails.append(email_data)
                            
                            # Store received email
                            await self._store_received_email(email_data)
                            
                except Exception as e:
                    logger.error(f"Failed to process email {msg_id}: {e}")
            
            await imap.logout()
            return emails

        except Exception as e:
            logger.error(f"Failed to check emails: {e}")
            raise EmailReceiveError(f"Failed to check emails: {str(e)}")

    def _parse_email_message(self, raw_email: bytes) -> Optional[Dict[str, Any]]:
        """Parse raw email message into structured data"""
        try:
            from email import message_from_bytes
            msg = message_from_bytes(raw_email)
            
            # Extract basic fields
            email_data = {
                'message_id': msg.get('Message-ID', ''),
                'from_address': msg.get('From', ''),
                'to_addresses': [addr.strip() for addr in msg.get('To', '').split(',')],
                'subject': msg.get('Subject', ''),
                'date': msg.get('Date', ''),
                'body': '',
                'body_html': '',
                'attachments': [],
            }
            
            # Extract tracking ID
            tracking_id = self._extract_tracking_id(email_data['subject'], '')
            if not tracking_id:
                tracking_id = msg.get('X-NDA-Tracking-ID')
            email_data['tracking_id'] = tracking_id
            
            # Parse message content
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == 'text/plain':
                        email_data['body'] = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    elif content_type == 'text/html':
                        email_data['body_html'] = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    elif part.get_content_disposition() == 'attachment':
                        attachment = {
                            'filename': part.get_filename() or 'attachment',
                            'content': part.get_payload(decode=True),
                            'content_type': content_type
                        }
                        email_data['attachments'].append(attachment)
            else:
                email_data['body'] = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            return email_data
            
        except Exception as e:
            logger.error(f"Failed to parse email: {e}")
            return None

    def _extract_tracking_id(self, subject: str, body: str) -> Optional[str]:
        """Extract NDA tracking ID from email content"""
        # Look for tracking ID patterns: NDA-XXXXXXXX-XXXXXXXX or NDA-XXXXXXXX  
        patterns = [
            r'NDA-[A-Z0-9]{8}-[A-Z0-9]{8}',  # Full format
            r'NDA-[A-Z0-9]{8}',              # Short format
            r'\[NDA-[A-Z0-9]{8}\]',          # Bracketed format
        ]
        
        # Check subject first
        for pattern in patterns:
            match = re.search(pattern, subject)
            if match:
                # Remove brackets if present
                tracking_id = match.group(0).strip('[]')
                return tracking_id
        
        # Check body
        for pattern in patterns:
            match = re.search(pattern, body)
            if match:
                tracking_id = match.group(0).strip('[]')
                return tracking_id
        
        return None

    def _generate_tracking_id(self, nda_id: str) -> str:
        """Generate tracking ID for NDA email"""
        nda_prefix = nda_id[:8].upper()
        random_suffix = uuid.uuid4().hex[:8].upper()
        return f"NDA-{nda_prefix}-{random_suffix}"

    async def _store_sent_email(self, email_data: Dict[str, Any]):
        """Store sent email record in database"""
        await self._store_email_record({
            **email_data,
            'direction': 'sent',
            'sent_at': datetime.utcnow()
        })

    async def _store_received_email(self, email_data: Dict[str, Any]) -> Optional[str]:
        """Store received email and link to NDA if possible"""
        linked_nda_id = await self._link_email_to_nda(email_data)
        
        await self._store_email_record({
            **email_data,
            'direction': 'received',
            'received_at': datetime.utcnow(),
            'nda_record_id': linked_nda_id
        })
        
        return linked_nda_id

    async def _link_email_to_nda(self, email_data: Dict[str, Any]) -> Optional[str]:
        """Link received email to NDA record via tracking ID"""
        tracking_id = email_data.get('tracking_id')
        if not tracking_id:
            return None
        
        db = get_db_session()
        try:
            # Find sent email with this tracking ID
            sent_email = db.query(EmailMessage).filter(
                EmailMessage.tracking_id == tracking_id,
                EmailMessage.direction == 'sent'
            ).first()
            
            if sent_email:
                return str(sent_email.nda_record_id)
        finally:
            db.close()
        
        return None

    async def _store_email_record(self, email_data: Dict[str, Any]):
        """Store email record in database"""
        db = get_db_session()
        try:
            email_record = EmailMessage(
                message_id=email_data['message_id'],
                nda_record_id=uuid.UUID(email_data['nda_record_id']) if email_data.get('nda_record_id') else None,
                direction=email_data['direction'],
                subject=email_data['subject'],
                body=email_data.get('body'),
                body_html=email_data.get('body_html'),
                from_address=email_data.get('from_address', ''),
                to_addresses=email_data.get('to_addresses', []),
                cc_addresses=email_data.get('cc_addresses', []),
                tracking_id=email_data.get('tracking_id'),
                sent_at=email_data.get('sent_at'),
                received_at=email_data.get('received_at'),
            )
            
            db.add(email_record)
            db.commit()
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to store email record: {e}")
            raise
        finally:
            db.close()

    def _validate_email_address(self, email: str) -> bool:
        """Validate email address format"""
        if not email or not isinstance(email, str):
            return False
        
        # Basic email validation regex
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def _sanitize_email_content(self, content: str) -> str:
        """Sanitize email content to prevent injection attacks"""
        if not isinstance(content, str):
            return str(content)
        
        # Remove potential script tags and dangerous content
        cleaned = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r'\$\{[^}]*\}', '', cleaned)  # Remove template injection
        
        return cleaned

    def _add_attachment(self, message: MIMEMultipart, attachment: Dict[str, Any]):
        """Add attachment to email message"""
        filename = attachment.get('filename', 'attachment')
        content = attachment.get('content', b'')
        
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(content)
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= {filename}',
        )
        message.attach(part)

    def _parse_attachments(self, email_msg) -> List[Dict[str, Any]]:
        """Parse attachments from email message"""
        attachments = []
        
        if hasattr(email_msg, 'is_multipart') and email_msg.is_multipart():
            for part in email_msg.get_payload():
                if hasattr(part, 'get_content_disposition') and part.get_content_disposition() == 'attachment':
                    attachments.append({
                        'filename': part.get_filename() or 'attachment',
                        'content': part.get_payload(decode=True),
                        'content_type': part.get_content_type()
                    })
        
        return attachments


# Global service instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get or create email service instance (singleton)"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service


def create_email_service() -> EmailService:
    """Create new email service instance (for testing)"""
    return EmailService()


class EmailParser:
    """Email parser for processing incoming emails and linking to NDAs"""
    
    def __init__(self):
        self.email_service = get_email_service()

    async def process_incoming_email(self, email_data: Dict[str, Any]) -> Optional[str]:
        """Process incoming email and link to NDA if applicable"""
        return await self.email_service._link_email_to_nda(email_data)

    def parse_email(self, raw_email: bytes) -> Optional[Dict[str, Any]]:
        """Parse raw email into structured data"""
        return self.email_service._parse_email_message(raw_email)