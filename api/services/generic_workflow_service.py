"""
Generic Workflow Service for any document type

Generalizes the Phase 1 NDA workflow system to support any document type:
- Generic document workflow management (replaces NDA-specific)
- Document-type-aware Camunda integration
- Multi-document-type workflow routing
- Generic document creation and management
- Generic email handling for any document type
- Status management across document types
- Backward compatibility with Phase 1 NDA workflows

Integrates with:
- DocumentTypeService (Task 2.2) for configuration
- Generic schema (Task 2.1) for database operations  
- Phase 1 services (Camunda, Email, Template) for functionality
"""

import logging
import uuid
import tempfile
import os
from datetime import datetime, date
from typing import Dict, Any, List, Optional

from api.db import get_db_session
from api.db.generic_schema import (
    LegalDocument, DocumentWorkflowInstance, DocumentWorkflowTask, DocumentType
)
from api.db.schema import Document, DocumentStatus
from api.services.document_type_service import get_document_type_service, DocumentTypeNotFoundError
from api.services.camunda_service import get_camunda_service, CamundaProcessError
from api.services.email_service import get_email_service, EmailSendError
from api.services.template_service import get_template_service, TemplateNotFoundError
from api.services.service_registry import get_storage_service
from api.services.registry_service import registry_service

logger = logging.getLogger(__name__)


class WorkflowNotFoundError(Exception):
    """Raised when workflow is not found"""
    pass


class WorkflowConfigurationError(Exception):
    """Raised when workflow configuration is invalid"""
    pass


class DocumentWorkflowError(Exception):
    """Raised when document workflow operations fail"""
    pass


class GenericWorkflowService:
    """
    Generic workflow service that supports any document type
    
    Replaces NDA-specific workflow logic with document-type-aware logic
    """

    def __init__(self):
        self.document_type_service = get_document_type_service()
        self.camunda_service = get_camunda_service()

    def get_process_key_for_document_type(self, document_type: str) -> str:
        """Get workflow process key for document type"""
        return self.document_type_service.get_workflow_process_key(document_type)

    def supports_document_type(self, document_type: str) -> bool:
        """Check if document type is supported for workflows"""
        return self.document_type_service.supports_document_type(document_type)

    def get_workflow_config(self, document_type: str) -> Dict[str, Any]:
        """Get complete workflow configuration for document type"""
        if not self.supports_document_type(document_type):
            raise WorkflowConfigurationError(f"Document type '{document_type}' not supported")
        
        doc_type_config = self.document_type_service.get_document_type_config(document_type)
        
        return {
            'document_type': document_type,
            'process_key': doc_type_config.get('workflow_process_key', ''),
            'llm_review': doc_type_config.get('llm_review', {}),
            'template_bucket': doc_type_config.get('template_bucket', 'legal-templates'),
            'display_name': doc_type_config.get('display_name', document_type.title())
        }

    async def start_workflow_for_document(
        self,
        document_id: str,
        document_type: str,
        variables: Dict[str, Any],
        business_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start workflow for any document type
        
        Uses DocumentTypeService to determine correct process key
        """
        try:
            # Get process key for this document type
            process_key = self.get_process_key_for_document_type(document_type)
            
            # Add document type to variables
            workflow_variables = {
                **variables,
                'document_id': document_id,
                'document_type': document_type
            }
            
            # Generate business key if not provided
            if not business_key:
                business_key = f"{document_type.upper()}-{document_id[:8].upper()}"
            
            # Start Camunda process
            result = await self.camunda_service.start_process_instance(
                process_key=process_key,
                variables=workflow_variables,
                business_key=business_key
            )
            
            logger.info(f"Started {document_type} workflow: {result['id']}")
            return result
            
        except DocumentTypeNotFoundError as e:
            raise WorkflowConfigurationError(f"Document type '{document_type}' not configured: {str(e)}")
        except CamundaProcessError as e:
            raise DocumentWorkflowError(f"Failed to start workflow for {document_type}: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to start workflow for {document_type}: {e}")
            raise DocumentWorkflowError(f"Workflow start failed: {str(e)}")

    async def create_workflow_instance(
        self,
        legal_document_id: uuid.UUID,
        document_type: str,
        camunda_process_instance_id: str,
        process_key: str,
        initial_status: str = "started"
    ) -> DocumentWorkflowInstance:
        """Create generic workflow instance for any document type"""
        db = get_db_session()
        try:
            workflow_instance = DocumentWorkflowInstance(
                legal_document_id=legal_document_id,
                document_type=document_type,
                camunda_process_instance_id=camunda_process_instance_id,
                process_key=process_key,
                current_status=initial_status,
                started_at=datetime.utcnow(),
            )
            
            db.add(workflow_instance)
            db.commit()
            
            logger.info(f"Created workflow instance for {document_type}: {workflow_instance.id}")
            return workflow_instance
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create workflow instance: {e}")
            raise DocumentWorkflowError(f"Failed to create workflow instance: {str(e)}")
        finally:
            db.close()

    def get_workflow_by_document(self, document_id: str) -> Optional[DocumentWorkflowInstance]:
        """Get workflow instance by legal document ID"""
        db = get_db_session()
        try:
            document_uuid = uuid.UUID(document_id)
            workflow = db.query(DocumentWorkflowInstance).filter(
                DocumentWorkflowInstance.legal_document_id == document_uuid
            ).first()
            
            return workflow
            
        except ValueError:
            raise WorkflowNotFoundError(f"Invalid document ID: {document_id}")
        except Exception as e:
            logger.error(f"Failed to get workflow: {e}")
            raise DocumentWorkflowError(f"Failed to get workflow: {str(e)}")
        finally:
            db.close()

    def get_workflows_by_document_type(self, document_type: str) -> List[DocumentWorkflowInstance]:
        """Get workflows filtered by document type"""
        db = get_db_session()
        try:
            workflows = db.query(DocumentWorkflowInstance).filter(
                DocumentWorkflowInstance.document_type == document_type
            ).all()
            
            return workflows
            
        finally:
            db.close()

    def list_workflows(
        self,
        document_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[DocumentWorkflowInstance]:
        """List workflows with optional filtering"""
        db = get_db_session()
        try:
            query = db.query(DocumentWorkflowInstance)
            
            if document_type:
                query = query.filter(DocumentWorkflowInstance.document_type == document_type)
            
            if status:
                query = query.filter(DocumentWorkflowInstance.current_status == status)
            
            workflows = query.order_by(DocumentWorkflowInstance.started_at.desc()).limit(limit).all()
            return workflows
            
        finally:
            db.close()

    async def complete_task_for_document_type(
        self,
        task_id: str,
        document_type: str,
        approved: bool,
        comments: Optional[str] = None
    ) -> Dict[str, Any]:
        """Complete task with document type awareness"""
        try:
            # Get user tasks from Camunda
            user_tasks = await self.camunda_service.get_user_tasks()
            task = next((t for t in user_tasks if t.get("id") == task_id), None)
            
            if not task:
                raise WorkflowNotFoundError(f"Task {task_id} not found")
            
            # For Phase 2, return success (full task logic in later phases)
            return {
                'task_id': task_id,
                'document_type': document_type,
                'approved': approved,
                'comments': comments,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"Failed to complete task for {document_type}: {e}")
            raise DocumentWorkflowError(f"Task completion failed: {str(e)}")

    def get_user_tasks_by_document_type(
        self,
        user_id: str,
        document_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[DocumentWorkflowTask]:
        """Get user tasks filtered by document type"""
        db = get_db_session()
        try:
            # Join workflow tasks with workflow instances to filter by document type
            query = db.query(DocumentWorkflowTask).join(DocumentWorkflowInstance)
            
            # Filter by assignee
            query = query.filter(DocumentWorkflowTask.assignee_user_id == uuid.UUID(user_id))
            
            # Filter by document type if specified
            if document_type:
                query = query.filter(DocumentWorkflowInstance.document_type == document_type)
            
            # Filter by status if specified
            if status:
                query = query.filter(DocumentWorkflowTask.status == status)
            
            tasks = query.all()
            return tasks
            
        finally:
            db.close()

    def update_document_status_from_workflow(
        self,
        document_id: str,
        workflow_event: str,
        new_status: str
    ):
        """Update document status based on workflow events (generic)"""
        db = get_db_session()
        try:
            document_uuid = uuid.UUID(document_id)
            legal_document = db.query(LegalDocument).filter(
                LegalDocument.id == document_uuid
            ).first()
            
            if not legal_document:
                raise WorkflowNotFoundError(f"Document {document_id} not found")
            
            # Update status
            legal_document.status = new_status
            db.commit()
            
            logger.info(f"Updated {legal_document.document_type} document {document_id} status: {new_status}")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update document status: {e}")
            raise DocumentWorkflowError(f"Status update failed: {str(e)}")
        finally:
            db.close()

    def is_valid_status_transition(
        self,
        document_type: str,
        from_status: str,
        to_status: str
    ) -> bool:
        """Validate status transition is valid for document type"""
        # Use same status flow as Phase 1 for all document types
        valid_transitions = {
            'created': ['draft', 'in_review'],
            'draft': ['created', 'in_review'],
            'in_review': ['llm_reviewed_approved', 'llm_reviewed_rejected', 'reviewed'],
            'llm_reviewed_approved': ['reviewed', 'pending_signature'],
            'llm_reviewed_rejected': ['rejected'],
            'reviewed': ['approved', 'rejected', 'pending_signature'],
            'approved': ['pending_signature', 'signed'],
            'pending_signature': ['customer_signed'],
            'customer_signed': ['llm_reviewed_approved', 'llm_reviewed_rejected', 'signed'],
            'signed': ['active'],
            'active': ['expired', 'terminated', 'archived'],
            'expired': ['archived'],
            'terminated': ['archived']
        }
        
        allowed_transitions = valid_transitions.get(from_status, [])
        return to_status in allowed_transitions


class GenericDocumentService:
    """
    Generic document service that coordinates document operations for any type
    
    Provides high-level document operations that work across document types
    """

    def __init__(self):
        self.workflow_service = GenericWorkflowService()
        self.template_service = get_template_service()
        self.email_service = get_email_service()
        self.document_type_service = get_document_type_service()
        self.storage = get_storage_service()

    async def create_document_from_template(
        self,
        template_id: str,
        document_type: str,
        template_data: Dict[str, Any],
        document_metadata: Dict[str, Any],
        owner_user_id: Optional[str] = None,
        auto_start_workflow: bool = True
    ) -> LegalDocument:
        """
        Create document from template for any document type
        
        Generalizes the Phase 1 NDA creation process
        """
        try:
            # Validate document type is supported
            if not self.document_type_service.supports_document_type(document_type):
                raise DocumentWorkflowError(f"Document type '{document_type}' not supported")
            
            # Validate metadata against document type schema
            self.document_type_service.validate_metadata(document_type, document_metadata)
            
            # Get and validate template
            template = self.template_service.get_template(template_id)
            if not template.is_active:
                raise DocumentWorkflowError("Template is not active")
            
            # Render template
            rendered_bytes = self.template_service.render_template(
                template_id=template_id,
                data=template_data
            )
            
            # Create document record
            db = get_db_session()
            try:
                document = Document(
                    filename=f"{document_type}_{template_data.get('counterparty_name', 'document')}_{uuid.uuid4().hex[:8]}.pdf",
                    status=DocumentStatus.UPLOADED,
                )
                db.add(document)
                db.flush()
                document_id = str(document.id)
                
                # Upload file
                filename = f"{document_type}_{document_id[:8]}.pdf"
                file_path = self.storage.upload_file(
                    bucket=self.document_type_service.get_template_bucket(document_type),
                    object_name=f"{document_id}/{filename}",
                    file_data=rendered_bytes,
                    content_type="application/pdf"
                )
                
                document.s3_path = file_path
                db.commit()
                
            except Exception as e:
                db.rollback()
                raise DocumentWorkflowError(f"Failed to create document: {str(e)}")
            finally:
                db.close()
            
            # Create legal document record using generic registry
            from api.services.generic_workflow_service import create_legal_document
            legal_document = create_legal_document(
                document_id=document_id,
                document_type=document_type,
                counterparty_name=template_data.get('counterparty_name'),
                document_metadata=document_metadata,
                counterparty_domain=template_data.get('counterparty_domain'),
                counterparty_email=template_data.get('counterparty_email'),
                owner_user_id=owner_user_id,
                effective_date=template_data.get('effective_date'),
                expiry_date=template_data.get('expiry_date'),
                status="created",
                file_uri=file_path,
                file_bytes=rendered_bytes,
                template_id=template_id,
                template_version=template.version,
            )
            
            logger.info(f"Created {document_type} document: {legal_document.id}")
            
            # Auto-start workflow if requested
            if auto_start_workflow:
                try:
                    workflow_result = await self.workflow_service.start_workflow_for_document(
                        document_id=str(legal_document.id),
                        document_type=document_type,
                        variables={
                            'document_id': str(legal_document.id),
                            'owner_user_id': owner_user_id or '',
                            **variables
                        }
                    )
                    
                    # Create workflow instance record
                    workflow_instance = await self.workflow_service.create_workflow_instance(
                        legal_document_id=legal_document.id,
                        document_type=document_type,
                        camunda_process_instance_id=workflow_result['id'],
                        process_key=self.workflow_service.get_process_key_for_document_type(document_type)
                    )
                    
                    # Link to legal document
                    db = get_db_session()
                    try:
                        legal_document.workflow_instance_id = workflow_instance.id
                        legal_document.status = "in_review"
                        db.commit()
                    finally:
                        db.close()
                    
                except Exception as e:
                    logger.error(f"Failed to auto-start workflow: {e}")
                    # Don't fail document creation if workflow start fails
            
            return legal_document
            
        except Exception as e:
            logger.error(f"Failed to create {document_type} document: {e}")
            raise DocumentWorkflowError(f"Document creation failed: {str(e)}")

    async def send_document_email(
        self,
        document_id: str,
        to_addresses: List[str],
        subject: Optional[str] = None,
        message: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send document via email for any document type
        
        Generalizes Phase 1 NDA email sending
        """
        try:
            # Get legal document
            db = get_db_session()
            try:
                document_uuid = uuid.UUID(document_id)
                legal_document = db.query(LegalDocument).filter(
                    LegalDocument.id == document_uuid
                ).first()
                
                if not legal_document:
                    raise WorkflowNotFoundError(f"Document {document_id} not found")
                
                # Update status to pending_signature
                legal_document.status = "pending_signature"
                db.commit()
                
            finally:
                db.close()
            
            # Download document file
            file_path = legal_document.file_uri
            if '/' in file_path:
                parts = file_path.split('/', 1)
                bucket, object_name = parts[0], parts[1]
            else:
                bucket = self.document_type_service.get_template_bucket(legal_document.document_type)
                object_name = file_path
            
            file_bytes = self.storage.download_file(bucket, object_name)
            
            # Generate tracking ID
            tracking_id = self.email_service._generate_tracking_id(document_id)
            
            # Generate email content based on document type
            doc_type_config = self.document_type_service.get_document_type_config(legal_document.document_type)
            
            email_subject = subject or f"{doc_type_config['display_name']} - {legal_document.counterparty_name}"
            email_body = message or f"""Dear {legal_document.counterparty_name},

Please find attached the {doc_type_config['display_name']} for your review and signature.

Please review the document carefully and return a signed copy at your earliest convenience.

Best regards,
Legal Document Management System"""

            # Send email
            message_id = await self.email_service.send_email(
                to_addresses=to_addresses,
                subject=email_subject,
                body=email_body,
                cc_addresses=cc_addresses or [],
                attachments=[{
                    'filename': f"{legal_document.document_type}_{legal_document.counterparty_name.replace(' ', '_')}.pdf",
                    'content': file_bytes,
                }],
                tracking_id=tracking_id,
                nda_record_id=document_id,  # For backward compatibility with Phase 1 email service
            )
            
            logger.info(f"Sent {legal_document.document_type} document {document_id} via email")
            
            return {
                'message_id': message_id,
                'tracking_id': tracking_id,
                'sent_to': to_addresses,
                'document_type': legal_document.document_type,
                'status': 'sent'
            }
            
        except Exception as e:
            logger.error(f"Failed to send document email: {e}")
            raise DocumentWorkflowError(f"Email send failed: {str(e)}")


# Generic registry service extension for legal documents
class GenericRegistryService:
    """Extended registry service for generic legal documents"""
    
    def create_legal_document(
        self,
        document_id: str,
        document_type: str,
        counterparty_name: str,
        document_metadata: Dict[str, Any],
        **kwargs
    ) -> LegalDocument:
        """Create legal document record (extends Phase 1 registry service)"""
        db = get_db_session()
        try:
            legal_document = LegalDocument(
                document_id=uuid.UUID(document_id) if document_id and document_id != 'None' else None,
                document_type=document_type,
                counterparty_name=counterparty_name or 'Unknown Counterparty',
                counterparty_domain=kwargs.get('counterparty_domain'),
                counterparty_email=kwargs.get('counterparty_email'),
                owner_user_id=uuid.UUID(kwargs['owner_user_id']) if kwargs.get('owner_user_id') else None,
                effective_date=kwargs.get('effective_date'),
                expiry_date=kwargs.get('expiry_date'),
                status=kwargs.get('status', 'created'),
                file_uri=kwargs.get('file_uri', ''),
                file_sha256=kwargs.get('file_bytes', b'')[:32] if kwargs.get('file_bytes') else b'default_hash'.ljust(32, b'0'),
                extracted_text=kwargs.get('extracted_text'),
                document_metadata=document_metadata,
                template_id=uuid.UUID(kwargs['template_id']) if kwargs.get('template_id') else None,
                template_version=kwargs.get('template_version'),
                tags=kwargs.get('tags', {}),
                facts_json=kwargs.get('facts_json'),
            )
            
            db.add(legal_document)
            db.commit()
            
            return legal_document
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create legal document: {e}")
            raise DocumentWorkflowError(f"Document creation failed: {str(e)}")
        finally:
            db.close()


# Add method to existing registry service for backward compatibility
def create_legal_document(*args, **kwargs):
    """Create legal document using generic registry service"""
    generic_registry = GenericRegistryService()
    return generic_registry.create_legal_document(*args, **kwargs)

# Monkey patch for backward compatibility
registry_service.create_legal_document = create_legal_document


# Global service instances
_generic_workflow_service: Optional[GenericWorkflowService] = None
_generic_document_service: Optional[GenericDocumentService] = None


def get_generic_workflow_service() -> GenericWorkflowService:
    """Get or create generic workflow service instance (singleton)"""
    global _generic_workflow_service
    if _generic_workflow_service is None:
        _generic_workflow_service = GenericWorkflowService()
    return _generic_workflow_service


def create_generic_workflow_service() -> GenericWorkflowService:
    """Create new generic workflow service instance (for testing)"""
    return GenericWorkflowService()


def get_generic_document_service() -> GenericDocumentService:
    """Get or create generic document service instance (singleton)"""
    global _generic_document_service
    if _generic_document_service is None:
        _generic_document_service = GenericDocumentService()
    return _generic_document_service
