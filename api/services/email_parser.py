"""
Email parser for processing incoming emails and linking them to NDAs
"""
import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

from api.db import get_db_session
from api.db.schema import EmailMessage, NDARecord
from api.services.email_service import get_email_service

logger = logging.getLogger(__name__)


class EmailParser:
    """Parser for processing incoming emails and linking to NDAs"""

    def __init__(self):
        self.email_service = get_email_service()

    def process_incoming_email_sync(self, email_data: Dict[str, Any]) -> Optional[str]:
        """Synchronous version of process_incoming_email"""
        return self._process_incoming_email(email_data)
    
    async def process_incoming_email(self, email_data: Dict[str, Any]) -> Optional[str]:
        """Async wrapper for process_incoming_email"""
        return self._process_incoming_email(email_data)
    
    def _process_incoming_email(self, email_data: Dict[str, Any]) -> Optional[str]:
        """
        Process incoming email and link to NDA if applicable
        
        Args:
            email_data: Parsed email data from email service
            
        Returns:
            NDA record ID if linked, None otherwise
        """
        message_id = email_data.get('message_id')
        tracking_id = email_data.get('tracking_id')
        
        # Check if we already processed this message
        db = get_db_session()
        try:
            existing = db.query(EmailMessage).filter(
                EmailMessage.message_id == message_id
            ).first()
            
            if existing:
                logger.info(f"Email message {message_id} already processed")
                return str(existing.nda_record_id) if existing.nda_record_id else None
        finally:
            db.close()

        # Try to find NDA by tracking ID
        nda_record_id = None
        if tracking_id:
            nda_record_id = self._find_nda_by_tracking_id(tracking_id)
        
        # If no tracking ID, try to find by subject/from address
        if not nda_record_id:
            nda_record_id = self._find_nda_by_email_content(email_data)
        
        # Store email message
        self._store_received_email(email_data, nda_record_id)
        
        return nda_record_id

    def _find_nda_by_tracking_id(self, tracking_id: str) -> Optional[str]:
        """Find NDA record by tracking ID"""
        db = get_db_session()
        try:
            # Look for sent email with this tracking ID
            sent_email = db.query(EmailMessage).filter(
                EmailMessage.tracking_id == tracking_id,
                EmailMessage.direction == 'sent'
            ).first()
            
            if sent_email:
                return str(sent_email.nda_record_id)
        finally:
            db.close()
        return None

    def _find_nda_by_email_content(self, email_data: Dict[str, Any]) -> Optional[str]:
        """
        Try to find NDA by analyzing email content
        Looks for NDA-related keywords and counterparty information
        """
        subject = email_data.get('subject', '').lower()
        body = (email_data.get('body') or '').lower()
        from_address = email_data.get('from_address', '')
        
        # Look for NDA-related keywords
        nda_keywords = ['nda', 'non-disclosure', 'confidentiality', 'agreement']
        if not any(keyword in subject or keyword in body for keyword in nda_keywords):
            return None
        
        # Extract domain from email address
        domain = None
        if '@' in from_address:
            domain = from_address.split('@')[1].lower()
        
        # Search for NDA records by domain
        db = get_db_session()
        try:
            if domain:
                nda_record = db.query(NDARecord).filter(
                    NDARecord.counterparty_domain.ilike(f'%{domain}%')
                ).order_by(NDARecord.created_at.desc()).first()
                
                if nda_record:
                    return str(nda_record.id)
        finally:
            db.close()
        
        return None

    def _store_received_email(self, email_data: Dict[str, Any], nda_record_id: Optional[str]):
        """Store received email message in database"""
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
                message_id=email_data.get('message_id', ''),
                direction='received',
                subject=email_data.get('subject', ''),
                body=email_data.get('body'),
                body_html=email_data.get('body_html'),
                from_address=email_data.get('from_address', ''),
                to_addresses=email_data.get('to_addresses', []),
                cc_addresses=email_data.get('cc_addresses', []),
                attachments=[att.get('filename') for att in email_data.get('attachments', [])],
                tracking_id=email_data.get('tracking_id'),
                received_at=email_data.get('received_at', datetime.utcnow()),
            )
            
            db.add(email_msg)
            db.commit()
            
            logger.info(f"Stored received email: {email_data.get('subject')}")
        except Exception as e:
            logger.error(f"Failed to store received email: {e}")
            db.rollback()
        finally:
            db.close()

    def extract_attachments(self, email_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract attachments from email data"""
        return email_data.get('attachments', [])

    def has_nda_attachment(self, email_data: Dict[str, Any]) -> bool:
        """Check if email has NDA-related attachment (PDF/DOCX)"""
        attachments = email_data.get('attachments', [])
        for att in attachments:
            filename = att.get('filename', '').lower()
            if filename.endswith(('.pdf', '.docx', '.doc')):
                # Check if filename suggests it's an NDA
                if any(keyword in filename for keyword in ['nda', 'agreement', 'confidentiality']):
                    return True
        return False

