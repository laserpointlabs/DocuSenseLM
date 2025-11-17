"""
Camunda external task worker

Processes external tasks from Camunda:
- LLM review tasks
- Send to customer tasks  
- Other NDA workflow tasks
"""

import asyncio
import logging
import os
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from api.services.camunda_service import get_camunda_service
from api.db import get_db_session
from api.db.schema import NDARecord, NDAWorkflowInstance

logger = logging.getLogger(__name__)


class CamundaWorker:
    """Worker for processing Camunda external tasks"""

    def __init__(self):
        self.camunda = get_camunda_service()
        self.worker_id = f"nda-worker-{os.getenv('HOSTNAME', 'default')}-{uuid.uuid4().hex[:8]}"
        self.running = False
        self.poll_interval = int(os.getenv("CAMUNDA_WORKER_POLL_INTERVAL", "5"))  # Default 5 seconds

    async def start(self):
        """Start the worker loop"""
        self.running = True
        logger.info(f"Camunda worker started (worker_id: {self.worker_id})")
        
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
        logger.info(f"Camunda worker stopped (worker_id: {self.worker_id})")

    async def _poll_and_process(self):
        """Poll for external tasks and process them"""
        try:
            # Fetch tasks for topics we handle
            topics = ['llm_review', 'send_to_customer', 'llm_review_signed']
            
            for topic in topics:
                tasks = await self.camunda.fetch_external_tasks(
                    topic_name=topic,
                    max_tasks=5
                )
                
                for task in tasks:
                    try:
                        await self._process_task(task)
                    except Exception as e:
                        logger.error(f"Failed to process task {task.get('id')}: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to poll for external tasks: {e}")

    async def _process_task(self, task: Dict[str, Any]):
        """Route task to appropriate handler based on topic"""
        topic = task.get('topicName')
        
        if topic == 'llm_review':
            await self._process_llm_review_task(task)
        elif topic == 'send_to_customer':
            await self._process_send_to_customer_task(task)
        elif topic == 'llm_review_signed':
            await self._process_llm_review_signed_task(task)
        else:
            logger.warning(f"Unknown task topic: {topic}")

    async def _process_llm_review_task(self, task: Dict[str, Any]):
        """Process LLM review external task"""
        task_id = task.get('id')
        variables = task.get('variables', {})
        
        nda_record_id = variables.get('nda_record_id', {}).get('value')
        if not nda_record_id:
            logger.error("No nda_record_id in task variables")
            return
        
        # For now, just complete the task (LLM review service integration in next task)
        success = await self.camunda.complete_external_task(
            task_id=task_id,
            worker_id=self.worker_id,
            variables={'llm_approved': True, 'llm_confidence': 0.8}
        )
        
        if success:
            logger.info(f"Completed LLM review task {task_id}")

    async def _process_send_to_customer_task(self, task: Dict[str, Any]):
        """Process send to customer external task"""
        task_id = task.get('id')
        variables = task.get('variables', {})
        
        nda_record_id = variables.get('nda_record_id', {}).get('value')
        customer_email = variables.get('customer_email', {}).get('value')
        
        if not nda_record_id or not customer_email:
            logger.error("Missing required variables for send_to_customer task")
            return
        
        # For now, just complete the task (email integration in API layer)
        success = await self.camunda.complete_external_task(
            task_id=task_id,
            worker_id=self.worker_id,
            variables={'email_sent': True}
        )
        
        if success:
            logger.info(f"Completed send to customer task {task_id}")

    async def _process_llm_review_signed_task(self, task: Dict[str, Any]):
        """Process LLM review of signed document task"""
        task_id = task.get('id')
        variables = task.get('variables', {})
        
        nda_record_id = variables.get('nda_record_id', {}).get('value')
        if not nda_record_id:
            logger.error("No nda_record_id in task variables")
            return
        
        # For now, just complete the task
        success = await self.camunda.complete_external_task(
            task_id=task_id,
            worker_id=self.worker_id,
            variables={'llm_signed_approved': True}
        )
        
        if success:
            logger.info(f"Completed LLM review signed task {task_id}")


# Global worker instance
_camunda_worker: Optional[CamundaWorker] = None


def get_camunda_worker() -> CamundaWorker:
    """Get or create Camunda worker instance"""
    global _camunda_worker
    if _camunda_worker is None:
        _camunda_worker = CamundaWorker()
    return _camunda_worker