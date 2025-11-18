"""
Camunda external task worker
Polls Camunda for external tasks and executes them
"""
import asyncio
import logging
import os
import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from api.services.camunda_service import get_camunda_service
from api.services.llm_review_service import get_llm_review_service
from api.db import get_db_session
from api.db.schema import NDARecord, NDAWorkflowInstance, NDAWorkflowTask

logger = logging.getLogger(__name__)


class CamundaWorker:
    """Worker for processing Camunda external tasks"""

    def __init__(self):
        self.camunda = get_camunda_service()
        self.llm_review_service = get_llm_review_service()
        self.worker_id = f"nda-worker-{os.getenv('HOSTNAME', 'default')}"
        self.running = False
        self.poll_interval = int(os.getenv("CAMUNDA_WORKER_POLL_INTERVAL", "5"))  # Default 5 seconds

    async def start(self):
        """Start the worker loop"""
        self.running = True
        logger.info(f"Camunda worker started (worker_id: {self.worker_id}, poll_interval: {self.poll_interval}s)")
        
        while self.running:
            try:
                await self._poll_and_process()
            except Exception as e:
                logger.error(f"Error in Camunda worker loop: {e}", exc_info=True)
            
            # Wait before next poll
            await asyncio.sleep(self.poll_interval)

    def stop(self):
        """Stop the worker loop"""
        self.running = False
        logger.info("Camunda worker stopped")

    async def _poll_and_process(self):
        """Poll for external tasks and process them"""
        try:
            # Poll for multiple external task topics
            topics = ["llm_review", "send_to_customer", "llm_review_signed"]
            
            for topic in topics:
                task = self.camunda.fetch_and_lock_external_task(
                    topic=topic,
                    worker_id=self.worker_id,
                    max_tasks=1,
                )
                
                if task:
                    if topic == "llm_review":
                        await self._process_llm_review_task(task)
                    elif topic == "send_to_customer":
                        await self._process_send_to_customer_task(task)
                    elif topic == "llm_review_signed":
                        await self._process_llm_review_signed_task(task)
                    break  # Process one task at a time
            else:
                logger.debug("No external tasks available")
                
        except Exception as e:
            logger.error(f"Error polling external tasks: {e}", exc_info=True)

    async def _process_llm_review_task(self, task: Dict[str, Any]):
        """Process an LLM review external task"""
        task_id = task.get("id")
        process_instance_id = task.get("processInstanceId")
        variables = task.get("variables", {})
        
        logger.info(f"Processing LLM review task {task_id} for process instance {process_instance_id}")
        
        # Get NDA record ID from task variables
        nda_record_id = variables.get("nda_record_id", {}).get("value")
        if not nda_record_id:
            logger.error(f"No nda_record_id in task variables")
            # Complete task with failure
            self.camunda.complete_external_task(
                task_id=task_id,
                worker_id=self.worker_id,
                variables={"llm_approved": False, "llm_review_error": "Missing nda_record_id"},
            )
            return
        
        try:
            # Perform LLM review
            review_result = await self.llm_review_service.review_nda(nda_record_id)
            
            # Update NDA status and workflow instance status based on review
            db = get_db_session()
            try:
                nda_uuid = uuid.UUID(nda_record_id)
                nda_record = db.query(NDARecord).filter(NDARecord.id == nda_uuid).first()
                
                if nda_record:
                    if review_result["approved"]:
                        nda_record.status = "llm_reviewed_approved"
                    else:
                        nda_record.status = "llm_reviewed_rejected"
                    
                    # Update workflow instance status if exists
                    if nda_record.workflow_instance_id:
                        workflow_instance = db.query(NDAWorkflowInstance).filter(
                            NDAWorkflowInstance.id == nda_record.workflow_instance_id
                        ).first()
                        
                        if workflow_instance:
                            if review_result["approved"]:
                                workflow_instance.current_status = "llm_review_passed"
                            else:
                                workflow_instance.current_status = "failed_llm_rejected"
                                # Mark as completed since LLM rejection ends the workflow
                                from datetime import datetime
                                workflow_instance.completed_at = datetime.utcnow()
                    
                    db.commit()
                    logger.info(f"Updated NDA {nda_record_id} status to {nda_record.status}")
            finally:
                db.close()
            
            # Complete task with results
            success = self.camunda.complete_external_task(
                task_id=task_id,
                worker_id=self.worker_id,
                variables={
                    "llm_approved": review_result["approved"],
                    "llm_confidence": review_result["confidence"],
                    "llm_reasoning": review_result.get("reasoning", ""),
                },
            )
            
            if success:
                logger.info(f"Completed LLM review task {task_id} for NDA {nda_record_id}")
            else:
                logger.error(f"Failed to complete task {task_id}")
                
        except Exception as e:
            logger.error(f"Failed to process LLM review task: {e}", exc_info=True)
            # Complete task with failure
            self.camunda.complete_external_task(
                task_id=task_id,
                worker_id=self.worker_id,
                variables={
                    "llm_approved": False,
                    "llm_review_error": str(e),
                },
            )

    async def _process_send_to_customer_task(self, task: Dict[str, Any]):
        """Process send to customer external task"""
        task_id = task.get("id")
        process_instance_id = task.get("processInstanceId")
        variables = task.get("variables", {})
        
        logger.info(f"Processing send to customer task {task_id} for process instance {process_instance_id}")
        
        # Get NDA record ID and customer email from task variables
        nda_record_id = variables.get("nda_record_id", {}).get("value")
        customer_email = variables.get("customer_email", {}).get("value")
        
        if not nda_record_id:
            logger.error(f"No nda_record_id in task variables")
            self.camunda.complete_external_task(
                task_id=task_id,
                worker_id=self.worker_id,
                variables={"send_email_error": "Missing nda_record_id"},
            )
            return
        
        if not customer_email:
            logger.error(f"No customer_email in task variables")
            self.camunda.complete_external_task(
                task_id=task_id,
                worker_id=self.worker_id,
                variables={"send_email_error": "Missing customer_email"},
            )
            return
        
        try:
            # Send email to customer
            from api.services.service_registry import get_email_service
            from api.services.service_registry import get_storage_service
            
            db = get_db_session()
            try:
                nda_uuid = uuid.UUID(nda_record_id)
                nda_record = db.query(NDARecord).filter(NDARecord.id == nda_uuid).first()
                
                if not nda_record:
                    raise ValueError(f"NDA record {nda_record_id} not found")
                
                # Download NDA file from storage
                storage = get_storage_service()
                file_path = nda_record.file_uri
                
                # Parse file path
                if '/' in file_path:
                    parts = file_path.split('/', 1)
                    bucket = parts[0] if parts[0] else "nda-raw"
                    object_name = parts[1] if len(parts) > 1 else file_path
                else:
                    bucket = "nda-raw"
                    object_name = file_path
                
                file_bytes = storage.download_file(bucket, object_name)
                
                # Generate email
                email_service = get_email_service()
                email_subject = f"Non-Disclosure Agreement - {nda_record.counterparty_name}"
                email_body_text = f"""Dear {nda_record.counterparty_name},

Please find attached the Non-Disclosure Agreement for your review and signature.

Please review the document carefully and return a signed copy at your earliest convenience.

If you have any questions or concerns, please do not hesitate to contact us.

Thank you for your cooperation.

Best regards,
NDA Management System
"""
                
                # Send email
                message_id = await email_service.send_email(
                    to_addresses=[customer_email],
                    subject=email_subject,
                    body=email_body_text,
                    attachments=[{
                        'filename': f"NDA_{nda_record.counterparty_name.replace(' ', '_')}.pdf",
                        'content': file_bytes,
                    }],
                    nda_record_id=nda_record_id,
                )
                
                # Update NDA status
                nda_record.status = "sent_to_customer"
                db.commit()
                
                logger.info(f"Sent NDA {nda_record_id} to customer {customer_email}")
                
            finally:
                db.close()
            
            # Complete task
            success = self.camunda.complete_external_task(
                task_id=task_id,
                worker_id=self.worker_id,
                variables={
                    "email_sent": True,
                    "message_id": message_id,
                },
            )
            
            if success:
                logger.info(f"Completed send to customer task {task_id}")
            else:
                logger.error(f"Failed to complete task {task_id}")
                
        except Exception as e:
            logger.error(f"Failed to process send to customer task: {e}", exc_info=True)
            self.camunda.complete_external_task(
                task_id=task_id,
                worker_id=self.worker_id,
                variables={
                    "email_sent": False,
                    "send_email_error": str(e),
                },
            )

    async def _process_llm_review_signed_task(self, task: Dict[str, Any]):
        """Process LLM review of signed document external task"""
        task_id = task.get("id")
        process_instance_id = task.get("processInstanceId")
        variables = task.get("variables", {})
        
        logger.info(f"Processing LLM review signed task {task_id} for process instance {process_instance_id}")
        
        # Get NDA record ID from task variables
        nda_record_id = variables.get("nda_record_id", {}).get("value")
        if not nda_record_id:
            logger.error(f"No nda_record_id in task variables")
            self.camunda.complete_external_task(
                task_id=task_id,
                worker_id=self.worker_id,
                variables={"llm_signed_approved": False, "llm_review_error": "Missing nda_record_id"},
            )
            return
        
        try:
            # Perform LLM review of signed document
            review_result = await self.llm_review_service.review_nda(nda_record_id)
            
            # Update NDA status
            db = get_db_session()
            try:
                nda_uuid = uuid.UUID(nda_record_id)
                nda_record = db.query(NDARecord).filter(NDARecord.id == nda_uuid).first()
                
                if nda_record:
                    if review_result["approved"]:
                        nda_record.status = "llm_signed_reviewed_approved"
                    else:
                        nda_record.status = "llm_signed_reviewed_rejected"
                    
                    # Update workflow instance status
                    if nda_record.workflow_instance_id:
                        workflow_instance = db.query(NDAWorkflowInstance).filter(
                            NDAWorkflowInstance.id == nda_record.workflow_instance_id
                        ).first()
                        
                        if workflow_instance:
                            if review_result["approved"]:
                                workflow_instance.current_status = "llm_signed_review_passed"
                            else:
                                workflow_instance.current_status = "failed_llm_signed_rejected"
                                workflow_instance.completed_at = datetime.utcnow()
                    
                    db.commit()
                    logger.info(f"Updated NDA {nda_record_id} status to {nda_record.status}")
            finally:
                db.close()
            
            # Complete task with results
            success = self.camunda.complete_external_task(
                task_id=task_id,
                worker_id=self.worker_id,
                variables={
                    "llm_signed_approved": review_result["approved"],
                    "llm_signed_confidence": review_result["confidence"],
                    "llm_signed_reasoning": review_result.get("reasoning", ""),
                },
            )
            
            if success:
                logger.info(f"Completed LLM review signed task {task_id} for NDA {nda_record_id}")
            else:
                logger.error(f"Failed to complete task {task_id}")
                
        except Exception as e:
            logger.error(f"Failed to process LLM review signed task: {e}", exc_info=True)
            self.camunda.complete_external_task(
                task_id=task_id,
                worker_id=self.worker_id,
                variables={
                    "llm_signed_approved": False,
                    "llm_review_error": str(e),
                },
            )


# Global worker instance
_camunda_worker: Optional[CamundaWorker] = None
_worker_task: Optional[asyncio.Task] = None


def start_camunda_worker():
    """Start the Camunda worker"""
    global _camunda_worker, _worker_task
    
    if _camunda_worker is not None and _camunda_worker.running:
        logger.warning("Camunda worker is already running")
        return
    
    _camunda_worker = CamundaWorker()
    
    # Create event loop if needed
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Start worker in background
    _worker_task = loop.create_task(_camunda_worker.start())
    logger.info("Camunda worker task started")


def stop_camunda_worker():
    """Stop the Camunda worker"""
    global _camunda_worker, _worker_task
    
    if _camunda_worker:
        _camunda_worker.stop()
    
    if _worker_task:
        _worker_task.cancel()
    
    logger.info("Camunda worker stopped")



