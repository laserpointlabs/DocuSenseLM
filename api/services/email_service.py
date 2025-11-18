"""
Email service for sending and receiving emails via SMTP/IMAP
"""
import aiosmtplib
import aioimaplib
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import logging
from cryptography.fernet import Fernet
import base64
import os

from api.db import get_db_session
from api.db.schema import EmailConfig, EmailMessage, NDARecord
from api.services.service_registry import register_service, get_service, EMAIL_SERVICE

logger = logging.getLogger(__name__)


def _get_encryption_key() -> bytes:
    """Get or generate encryption key for passwords"""
    key_env = os.getenv("EMAIL_ENCRYPTION_KEY")
    if key_env:
        try:
            return base64.urlsafe_b64decode(key_env.encode())
        except Exception:
            # If decoding fails, generate a new key
            logger.warning("Invalid EMAIL_ENCRYPTION_KEY format, generating new key")
            return Fernet.generate_key()
    # Generate a key if not set (for development only)
    key = Fernet.generate_key()
    logger.warning("EMAIL_ENCRYPTION_KEY not set, using generated key (not persistent)")
    return key


def _encrypt_password(password: str) -> str:
    """Encrypt password for storage"""
    key = _get_encryption_key()
    # Fernet.generate_key() already returns a URL-safe base64-encoded key
    # If we got it from env, it's already decoded bytes, so encode it back
    if isinstance(key, bytes) and len(key) == 32:
        # It's raw bytes, encode it
        fernet = Fernet(base64.urlsafe_b64encode(key))
    else:
        # It's already a Fernet key string
        fernet = Fernet(key)
    return fernet.encrypt(password.encode()).decode()


def _decrypt_password(encrypted_password: str) -> str:
    """Decrypt password from storage"""
    key = _get_encryption_key()
    # Fernet.generate_key() already returns a URL-safe base64-encoded key
    if isinstance(key, bytes) and len(key) == 32:
        # It's raw bytes, encode it
        fernet = Fernet(base64.urlsafe_b64encode(key))
    else:
        # It's already a Fernet key string
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
        
        Args:
            to_addresses: List of recipient email addresses
            subject: Email subject
            body: Plain text body
            body_html: HTML body (optional)
            cc_addresses: CC addresses (optional)
            attachments: List of dicts with 'filename' and 'content' (bytes)
            tracking_id: Tracking ID for linking emails to NDAs
            nda_record_id: NDA record ID for tracking
            
        Returns:
            Message ID of sent email
        """
        config = self._get_active_config()
        if not config:
            raise RuntimeError("No active email configuration found")

        # Decrypt password (handle decryption failures gracefully - MailHog doesn't need passwords)
        smtp_password = None
        if config.smtp_password_encrypted:
            try:
                smtp_password = _decrypt_password(config.smtp_password_encrypted)
            except Exception as e:
                logger.warning(f"Failed to decrypt SMTP password, using empty password: {e}")
                smtp_password = None

        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{config.from_name or ''} <{config.from_address}>".strip()
        msg['To'] = ', '.join(to_addresses)
        if cc_addresses:
            msg['Cc'] = ', '.join(cc_addresses)
        msg['Subject'] = subject
        
        # Generate tracking ID if not provided
        if not tracking_id:
            tracking_id = f"NDA-{uuid.uuid4().hex[:8].upper()}"
        
        # Add tracking header
        msg['X-NDA-Tracking-ID'] = tracking_id
        
        # Add plain text part
        msg.attach(MIMEText(body, 'plain'))
        
        # Add HTML part if provided
        if body_html:
            msg.attach(MIMEText(body_html, 'html'))
        
        # Add attachments
        if attachments:
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment['content'])
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {attachment["filename"]}'
                )
                msg.attach(part)
        
        # Send email
        try:
            await aiosmtplib.send(
                msg,
                hostname=config.smtp_host,
                port=config.smtp_port,
                username=config.smtp_user,
                password=smtp_password,
                use_tls=config.smtp_use_tls,
            )
            
            message_id = msg['Message-ID'] or f"<{uuid.uuid4()}@nda-tool>"
            
            # Store email message record
            self._store_email_message(
                nda_record_id=nda_record_id,
                message_id=message_id,
                direction="sent",
                subject=subject,
                body=body,
                body_html=body_html,
                from_address=config.from_address,
                to_addresses=to_addresses,
                cc_addresses=cc_addresses or [],
                attachments=[att.get('filename') for att in (attachments or [])],
                tracking_id=tracking_id,
                sent_at=datetime.utcnow(),
            )
            
            logger.info(f"Email sent successfully: {subject} to {to_addresses}")
            return message_id
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise

    def _store_email_message(
        self,
        nda_record_id: Optional[str],
        message_id: str,
        direction: str,
        subject: str,
        body: Optional[str],
        body_html: Optional[str],
        from_address: str,
        to_addresses: List[str],
        cc_addresses: List[str],
        attachments: List[str],
        tracking_id: Optional[str],
        sent_at: Optional[datetime] = None,
        received_at: Optional[datetime] = None,
    ):
        """Store email message in database"""
        db = get_db_session()
        try:
            nda_uuid = None
            if nda_record_id:
                try:
                    nda_uuid = uuid.UUID(nda_record_id)
                except ValueError:
                    logger.warning(f"Invalid NDA record ID: {nda_record_id}")
            
            email_msg = EmailMessage(
                nda_record_id=nda_uuid,
                message_id=message_id,
                direction=direction,
                subject=subject,
                body=body,
                body_html=body_html,
                from_address=from_address,
                to_addresses=to_addresses,
                cc_addresses=cc_addresses,
                attachments=attachments,
                tracking_id=tracking_id,
                sent_at=sent_at,
                received_at=received_at,
            )
            
            db.add(email_msg)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to store email message: {e}")
            db.rollback()
        finally:
            db.close()

    async def check_imap_messages(self) -> List[Dict[str, Any]]:
        """
        Check IMAP inbox for new messages
        
        Returns:
            List of message dictionaries with parsed email data
        """
        config = self._get_active_config()
        if not config or not config.imap_host:
            logger.warning("No IMAP configuration found")
            return []

        try:
            # Decrypt password
            imap_password = _decrypt_password(config.imap_password_encrypted) if config.imap_password_encrypted else None
            
            if not imap_password:
                logger.warning("No IMAP password configured")
                return []

            # Connect to IMAP server
            imap_client = aioimaplib.IMAP4_SSL(
                host=config.imap_host,
                port=config.imap_port or 993,
            )
            await imap_client.wait_hello_from_server()
            
            await imap_client.login(config.imap_user, imap_password)
            await imap_client.select('INBOX')
            
            # Search for unread messages
            typ, data = await imap_client.search(None, 'UNSEEN')
            if typ != 'OK':
                logger.error("Failed to search IMAP inbox")
                await imap_client.logout()
                return []
            
            message_ids = data[0].split()
            messages = []
            
            for msg_id in message_ids:
                try:
                    typ, msg_data = await imap_client.fetch(msg_id, '(RFC822)')
                    if typ == 'OK' and msg_data[0]:
                        email_body = msg_data[0][1]
                        parsed_msg = self._parse_email_message(email_body)
                        if parsed_msg:
                            messages.append(parsed_msg)
                except Exception as e:
                    logger.error(f"Error parsing message {msg_id}: {e}")
            
            await imap_client.logout()
            return messages
            
        except Exception as e:
            logger.error(f"Failed to check IMAP messages: {e}")
            return []

    def _parse_email_message(self, email_bytes: bytes) -> Optional[Dict[str, Any]]:
        """Parse email message from bytes"""
        from email import message_from_bytes
        
        try:
            msg = message_from_bytes(email_bytes)
            
            # Extract basic fields
            subject = msg.get('Subject', '')
            from_addr = msg.get('From', '')
            to_addrs = msg.get('To', '')
            cc_addrs = msg.get('Cc', '')
            message_id = msg.get('Message-ID', '')
            tracking_id = msg.get('X-NDA-Tracking-ID', '')
            
            # Extract body
            body = None
            body_html = None
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == 'text/plain' and not body:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    elif content_type == 'text/html' and not body_html:
                        body_html = part.get_payload(decode=True).decode('utf-8', errors='ignore')
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            # Extract attachments
            attachments = []
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_disposition() == 'attachment':
                        filename = part.get_filename()
                        if filename:
                            attachments.append({
                                'filename': filename,
                                'content': part.get_payload(decode=True),
                                'content_type': part.get_content_type(),
                            })
            
            return {
                'message_id': message_id,
                'subject': subject,
                'from_address': from_addr,
                'to_addresses': [addr.strip() for addr in to_addrs.split(',') if addr.strip()],
                'cc_addresses': [addr.strip() for addr in cc_addrs.split(',') if cc_addrs and cc_addrs.strip()],
                'body': body,
                'body_html': body_html,
                'attachments': attachments,
                'tracking_id': tracking_id,
                'received_at': datetime.utcnow(),
            }
        except Exception as e:
            logger.error(f"Error parsing email message: {e}")
            return None


def create_email_service() -> EmailService:
    """Factory function for email service"""
    return EmailService()


# Register email service
register_service(EMAIL_SERVICE, create_email_service)


def get_email_service() -> EmailService:
    """Get email service instance"""
    return get_service(EMAIL_SERVICE)

