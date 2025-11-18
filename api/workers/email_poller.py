"""
Email polling worker to check for incoming emails and process signed NDAs
"""
import asyncio
import logging
import os
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from api.db import get_db_session
from api.db.schema import NDARecord, EmailMessage, Document, DocumentStatus
from api.services.email_service import get_email_service
from api.services.email_parser import EmailParser
from api.services.service_registry import get_storage_service
from ingest.worker import worker

logger = logging.getLogger(__name__)


class EmailPoller:
    """Worker to poll email inbox and process incoming NDA emails"""

    def __init__(self):
        self.email_service = get_email_service()
        self.email_parser = EmailParser()
        self.running = False
        self.poll_interval = int(os.getenv("EMAIL_POLL_INTERVAL", "60"))  # Default 60 seconds

    async def start(self):
        """Start the email polling loop"""
        self.running = True
        logger.info(f"Email poller started (poll interval: {self.poll_interval}s)")
        
        while self.running:
            try:
                await self._poll_and_process()
            except Exception as e:
                logger.error(f"Error in email polling loop: {e}", exc_info=True)
            
            # Wait before next poll
            await asyncio.sleep(self.poll_interval)

    def stop(self):
        """Stop the email polling loop"""
        self.running = False
        logger.info("Email poller stopped")

    async def _poll_and_process(self):
        """Poll email inbox and process new messages"""
        try:
            # Check for new emails
            messages = await self.email_service.check_imap_messages()
            
            if not messages:
                logger.debug("No new emails found")
                return
            
            logger.info(f"Found {len(messages)} new email(s)")
            
            for email_data in messages:
                try:
                    await self._process_email(email_data)
                except Exception as e:
                    logger.error(f"Failed to process email {email_data.get('message_id', 'unknown')}: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Error polling emails: {e}", exc_info=True)

    async def _process_email(self, email_data: Dict[str, Any]):
        """Process a single email message"""
        message_id = email_data.get('message_id', '')
        logger.info(f"Processing email: {message_id}")
        
        # Parse email and link to NDA
        # Note: process_incoming_email is async but EmailParser doesn't use async internally
        # We'll call it directly since it's actually synchronous
        nda_record_id = self.email_parser.process_incoming_email_sync(email_data)
        
        if not nda_record_id:
            logger.debug(f"Email {message_id} not linked to any NDA")
            return
        
        logger.info(f"Email {message_id} linked to NDA {nda_record_id}")
        
        # Check if email has NDA attachment
        if not self.email_parser.has_nda_attachment(email_data):
            logger.debug(f"Email {message_id} does not have NDA attachment")
            return
        
        # Extract attachments
        attachments = self.email_parser.extract_attachments(email_data)
        nda_attachments = [
            att for att in attachments
            if att.get('filename', '').lower().endswith(('.pdf', '.docx', '.doc'))
        ]
        
        if not nda_attachments:
            logger.debug(f"Email {message_id} has no NDA file attachments")
            return
        
        # Process each NDA attachment
        for attachment in nda_attachments:
            try:
                await self._process_nda_attachment(nda_record_id, attachment, email_data)
            except Exception as e:
                logger.error(f"Failed to process attachment {attachment.get('filename')}: {e}", exc_info=True)

    async def _process_nda_attachment(
        self,
        nda_record_id: str,
        attachment: Dict[str, Any],
        email_data: Dict[str, Any],
    ):
        """Process an NDA attachment from email"""
        filename = attachment.get('filename', 'unknown')
        file_content = attachment.get('content', b'')
        
        logger.info(f"Processing NDA attachment: {filename} for NDA {nda_record_id}")
        
        # Get NDA record
        db = get_db_session()
        try:
            nda_uuid = uuid.UUID(nda_record_id)
            nda_record = db.query(NDARecord).filter(NDARecord.id == nda_uuid).first()
            
            if not nda_record:
                logger.warning(f"NDA record {nda_record_id} not found")
                return
            
            # Check if this is a signed version (different from original)
            # For now, we'll upload it as a new document and update the NDA status
            
            # Create document record
            document = Document(
                filename=filename,
                status=DocumentStatus.UPLOADED,
            )
            db.add(document)
            db.flush()
            document_id = str(document.id)
            
            # Upload file to storage
            storage = get_storage_service()
            s3_path = storage.upload_file(
                bucket="nda-raw",
                object_name=f"{document_id}/{filename}",
                file_data=file_content,
                content_type="application/pdf" if filename.lower().endswith('.pdf') else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
            # Update document with s3_path
            document.s3_path = s3_path
            db.commit()
            
            # Update NDA record status to customer_signed
            old_status = nda_record.status
            nda_record.status = "customer_signed"
            nda_record.document_id = document.id  # Link to new signed document
            
            # Trigger workflow event if workflow exists
            if nda_record.workflow_instance_id:
                from api.services.camunda_service import get_camunda_service
                camunda = get_camunda_service()
                workflow_instance = db.query(NDAWorkflowInstance).filter(
                    NDAWorkflowInstance.id == nda_record.workflow_instance_id
                ).first()
                
                if workflow_instance and workflow_instance.camunda_process_instance_id:
                    # Correlate message to trigger customer signed event
                    camunda.correlate_message(
                        message_name="CustomerSignedMessage",
                        process_instance_id=workflow_instance.camunda_process_instance_id,
                        variables={"customer_signed": True},
                    )
                    logger.info(f"Triggered customer signed event for workflow {workflow_instance.id}")
            
            db.commit()
            
            logger.info(f"Updated NDA {nda_record_id} status: {old_status} -> customer_signed")
            
            # Queue ingestion in background (this will extract text and update registry)
            # We'll use a simple background task approach
            import threading
            def ingest_background():
                try:
                    # Save to temp file for ingestion
                    import tempfile
                    suffix = '.pdf' if filename.lower().endswith('.pdf') else '.docx'
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(file_content)
                        temp_file = tmp.name
                    
                    # Run ingestion
                    worker.ingest_document(temp_file, filename, document_id)
                    
                    # Clean up temp file
                    import os
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as e:
                    logger.error(f"Background ingestion failed: {e}", exc_info=True)
            
            # Start ingestion in background thread
            thread = threading.Thread(target=ingest_background, daemon=True)
            thread.start()
            
        except Exception as e:
            logger.error(f"Failed to process NDA attachment: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()


# Global poller instance
_email_poller: Optional[EmailPoller] = None
_poller_task: Optional[asyncio.Task] = None


def start_email_poller():
    """Start the email poller worker"""
    global _email_poller, _poller_task
    
    if _email_poller is not None and _email_poller.running:
        logger.warning("Email poller is already running")
        return
    
    _email_poller = EmailPoller()
    
    # Create event loop if needed
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Start poller in background
    _poller_task = loop.create_task(_email_poller.start())
    logger.info("Email poller task started")


def stop_email_poller():
    """Stop the email poller worker"""
    global _email_poller, _poller_task
    
    if _email_poller:
        _email_poller.stop()
    
    if _poller_task:
        _poller_task.cancel()
    
    logger.info("Email poller stopped")

