"""
Workflow router for NDA creation and workflow management
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Optional, List
import uuid
import logging
from datetime import date, datetime
import asyncio

from api.db import get_db_session
from api.db.schema import User, Document, DocumentStatus, NDARecord, NDAAuditLog, NDAWorkflowInstance, NDAWorkflowTask, NDAEvent
from api.middleware.auth import get_current_user
from api.models.requests import NDACreateRequest, NDASendEmailRequest, NDAUpdateRequest
from api.models.responses import NDARecordSummary
from api.services.template_service import TemplateService, create_template_service
from api.services.registry_service import registry_service
from api.services.service_registry import get_storage_service, get_email_service
from api.services.camunda_service import get_camunda_service
from api.routers.registry import _to_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflow", tags=["workflow"])

# Lazy initialization of template service
_template_service: Optional[TemplateService] = None

def get_template_service() -> TemplateService:
    """Get template service instance (lazy initialization)"""
    global _template_service
    if _template_service is None:
        _template_service = create_template_service()
    return _template_service


def _log_audit_action(
    nda_record_id: str,
    user_id: Optional[str],
    action: str,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Log action to audit log"""
    db = get_db_session()
    try:
        nda_uuid = uuid.UUID(nda_record_id)
        user_uuid = None
        if user_id:
            try:
                user_uuid = uuid.UUID(user_id)
            except ValueError:
                pass
        
        audit_log = NDAAuditLog(
            nda_record_id=nda_uuid,
            user_id=user_uuid,
            action=action,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(audit_log)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log audit action: {e}")
        db.rollback()
    finally:
        db.close()


@router.post("/nda/create", response_model=NDARecordSummary)
async def create_nda(
    request: NDACreateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Create an unsigned NDA from a template
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Get template
        template_service = get_template_service()
        template = template_service.get_template(request.template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        if not template.is_active:
            raise HTTPException(status_code=400, detail="Template is not active")
        
        # Prepare template data
        template_data = {
            'counterparty_name': request.counterparty_name,
            'effective_date': request.effective_date,
            'term_months': request.term_months,
            'survival_months': request.survival_months,
            'governing_law': request.governing_law or '',
            'disclosing_party': request.disclosing_party or '',
            'receiving_party': request.receiving_party or request.counterparty_name,
        }
        
        # Add additional data if provided
        if request.additional_data:
            template_data.update(request.additional_data)
        
        # Render template (use current version if not specified)
        rendered_docx_bytes = template_service.render_template(
            template_id=request.template_id,
            data=template_data,
        )
        
        # Convert rendered DOCX to PDF for storage and customer use
        # PDF conversion is REQUIRED - we don't store DOCX files
        rendered_bytes = None
        conversion_error = None
        
        try:
            # Save rendered DOCX temporarily and convert to PDF
            import tempfile
            import os
            import subprocess
            
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_docx:
                temp_docx.write(rendered_docx_bytes)
                temp_docx_path = temp_docx.name
            
            temp_pdf_path = temp_docx_path.replace('.docx', '.pdf')
            
            try:
                # Try LibreOffice first (more reliable)
                result = subprocess.run(
                    ['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', os.path.dirname(temp_pdf_path), temp_docx_path],
                    capture_output=True,
                    timeout=30
                )
                
                if result.returncode == 0 and os.path.exists(temp_pdf_path):
                    with open(temp_pdf_path, 'rb') as pdf_file:
                        rendered_bytes = pdf_file.read()
                else:
                    # Fallback to docx2pdf library
                    try:
                        from docx2pdf import convert
                        convert(temp_docx_path, temp_pdf_path)
                        if os.path.exists(temp_pdf_path):
                            with open(temp_pdf_path, 'rb') as pdf_file:
                                rendered_bytes = pdf_file.read()
                        else:
                            raise Exception("PDF file was not created")
                    except Exception as e2:
                        conversion_error = f"Both LibreOffice and docx2pdf failed: {str(e2)}"
            except Exception as e:
                conversion_error = f"PDF conversion failed: {str(e)}"
            finally:
                # Clean up temp files
                try:
                    if os.path.exists(temp_docx_path):
                        os.unlink(temp_docx_path)
                except:
                    pass
                try:
                    if os.path.exists(temp_pdf_path):
                        os.unlink(temp_pdf_path)
                except:
                    pass
        
        except Exception as e:
            conversion_error = f"PDF conversion setup failed: {str(e)}"
        
        # PDF conversion is mandatory - fail if it doesn't work
        if not rendered_bytes or not rendered_bytes.startswith(b'%PDF'):
            error_msg = conversion_error or "PDF conversion failed - no PDF data generated"
            logger.error(f"Failed to convert NDA to PDF: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to convert NDA to PDF. This is required for document security. Error: {error_msg}"
            )
        
        # Get template to track version used
        template_used = template_service.get_template(request.template_id)
        
        # Create document record
        db = get_db_session()
        try:
            is_pdf = rendered_bytes.startswith(b'%PDF')
            file_ext = '.pdf' if is_pdf else '.docx'
            document = Document(
                filename=f"NDA_{request.counterparty_name}_{uuid.uuid4().hex[:8]}{file_ext}",
                status=DocumentStatus.UPLOADED,
            )
            db.add(document)
            db.flush()
            document_id = str(document.id)
            
            # Upload rendered file to storage (PDF preferred, DOCX fallback)
            storage = get_storage_service()
            is_pdf = rendered_bytes.startswith(b'%PDF')
            file_ext = '.pdf' if is_pdf else '.docx'
            filename = f"NDA_{request.counterparty_name.replace(' ', '_')}_{document_id[:8]}{file_ext}"
            content_type = "application/pdf" if is_pdf else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            s3_path = storage.upload_file(
                bucket="nda-raw",
                object_name=f"{document_id}/{filename}",
                file_data=rendered_bytes,
                content_type=content_type
            )
            
            # Update document with s3_path
            document.s3_path = s3_path
            db.commit()
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create document: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")
        finally:
            db.close()
        
        # Create NDA record
        try:
            # Extract domain from email if provided
            counterparty_domain = request.counterparty_domain
            if not counterparty_domain and request.counterparty_email:
                if '@' in request.counterparty_email:
                    counterparty_domain = request.counterparty_email.split('@')[1]
            
            # Extract text from PDF immediately for LLM review
            extracted_text = None
            if rendered_bytes and rendered_bytes.startswith(b'%PDF'):
                try:
                    import tempfile
                    import os
                    from ingest.parser import DocumentParser
                    
                    # Save to temp file for parsing
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                        tmp_file.write(rendered_bytes)
                        tmp_path = tmp_file.name
                    
                    try:
                        parser = DocumentParser()
                        result = parser.parse(tmp_path)
                        extracted_text = result.get('text', '')
                        if extracted_text:
                            logger.info(f"Extracted {len(extracted_text)} characters from PDF during NDA creation")
                        else:
                            logger.warning(f"No text extracted from PDF during NDA creation")
                    finally:
                        # Clean up temp file
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                except Exception as e:
                    logger.warning(f"Failed to extract text during NDA creation: {e}. Text will be extracted later.")
                    # Don't fail NDA creation if text extraction fails
            
            nda_record = registry_service.upsert_record(
                document_id=document_id,
                counterparty_name=request.counterparty_name,
                counterparty_domain=counterparty_domain,
                entity_id=request.entity_id,
                owner_user_id=str(current_user.id),
                direction=request.direction,
                nda_type=request.nda_type,
                effective_date=request.effective_date,
                term_months=request.term_months,
                survival_months=request.survival_months,
                status="created",
                file_uri=s3_path,
                file_bytes=rendered_bytes,
                extracted_text=extracted_text,  # Extract text immediately for LLM review
                template_id=str(template_used.id) if template_used else None,
                template_version=template_used.version if template_used else None,
                tags={
                    'template_id': request.template_id,
                    'template_name': template_used.name if template_used else None,
                    'template_key': template_used.template_key if template_used else None,
                    'template_version': template_used.version if template_used else None,
                    'created_by': current_user.username,
                },
                facts={
                    'disclosing_party': request.disclosing_party,
                    'receiving_party': request.receiving_party or request.counterparty_name,
                    'governing_law': request.governing_law,
                },
            )
            
            # Log audit action
            _log_audit_action(
                nda_record_id=str(nda_record.id),
                user_id=str(current_user.id),
                action="nda_created",
                details={
                    'template_id': request.template_id,
                    'counterparty_name': request.counterparty_name,
                    'status': 'created',
                    'auto_start_workflow': request.auto_start_workflow,
                },
            )
            
            logger.info(f"Created NDA: {nda_record.id} for {request.counterparty_name}")
            
            # Auto-start workflow if requested
            workflow_instance_id = None
            if request.auto_start_workflow:
                try:
                    camunda = get_camunda_service()
                    
                    # Prepare workflow variables
                    process_variables = {
                        "nda_record_id": str(nda_record.id),
                        "reviewer_user_id": request.reviewer_user_id or str(current_user.id),
                        "approver_user_id": request.approver_user_id or str(current_user.id),
                        "internal_signer_user_id": request.internal_signer_user_id or str(current_user.id),
                        "customer_email": request.counterparty_email or "",
                    }
                    
                    # Start Camunda process instance
                    result = camunda.start_process_instance(
                        process_key="nda_review_approval",
                        variables=process_variables,
                        business_key=f"NDA-{str(nda_record.id)[:8].upper()}",
                    )
                    
                    camunda_process_instance_id = result.get("id")
                    
                    # Create workflow instance record
                    db = get_db_session()
                    try:
                        workflow_instance = NDAWorkflowInstance(
                            nda_record_id=nda_record.id,
                            camunda_process_instance_id=camunda_process_instance_id,
                            current_status="started",
                            started_at=datetime.utcnow(),
                        )
                        db.add(workflow_instance)
                        db.flush()
                        
                        # Link to NDA record
                        nda_record.workflow_instance_id = workflow_instance.id
                        nda_record.status = "customer_signed"  # Initial status - will change as workflow progresses
                        db.commit()
                        
                        workflow_instance_id = str(workflow_instance.id)
                        
                        logger.info(f"Auto-started workflow {workflow_instance_id} for NDA {nda_record.id}")
                    except Exception as e:
                        db.rollback()
                        logger.error(f"Failed to create workflow instance record: {e}")
                        raise
                    finally:
                        db.close()
                        
                except Exception as e:
                    logger.error(f"Failed to auto-start workflow: {e}", exc_info=True)
                    # Don't fail NDA creation if workflow start fails
                    # User can manually start workflow later
            
            summary = _to_summary(nda_record)
            if workflow_instance_id:
                summary.workflow_instance_id = workflow_instance_id
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to create NDA record: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create NDA record: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create NDA: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create NDA: {str(e)}")


@router.get("/nda/{nda_id}/status")
async def get_nda_status(
    nda_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get NDA workflow status"""
    db = get_db_session()
    try:
        nda_uuid = uuid.UUID(nda_id)
        nda_record = db.query(NDARecord).filter(NDARecord.id == nda_uuid).first()
        
        if not nda_record:
            raise HTTPException(status_code=404, detail="NDA not found")
        
        return {
            'id': str(nda_record.id),
            'status': nda_record.status,
            'counterparty_name': nda_record.counterparty_name,
            'effective_date': nda_record.effective_date.isoformat() if nda_record.effective_date else None,
            'expiry_date': nda_record.expiry_date.isoformat() if nda_record.expiry_date else None,
            'workflow_instance_id': str(nda_record.workflow_instance_id) if nda_record.workflow_instance_id else None,
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid NDA ID")
    finally:
        db.close()


@router.post("/nda/{nda_id}/send")
async def send_nda_email(
    nda_id: str,
    request: NDASendEmailRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Send NDA to customer via email
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not request.to_addresses:
        raise HTTPException(status_code=400, detail="At least one recipient email address is required")
    
    db = get_db_session()
    try:
        nda_uuid = uuid.UUID(nda_id)
        nda_record = db.query(NDARecord).filter(NDARecord.id == nda_uuid).first()
        
        if not nda_record:
            raise HTTPException(status_code=404, detail="NDA not found")
        
        # Check if NDA is in a sendable state
        if nda_record.status not in ['created', 'draft']:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot send NDA with status '{nda_record.status}'. Only 'created' or 'draft' NDAs can be sent."
            )
        
        # Download NDA file from storage
        storage = get_storage_service()
        file_path = nda_record.file_uri
        
        # Parse file path (format: bucket/object_name)
        if '/' in file_path:
            parts = file_path.split('/', 1)
            bucket = parts[0] if parts[0] else "nda-raw"
            object_name = parts[1] if len(parts) > 1 else file_path
        else:
            bucket = "nda-raw"
            object_name = file_path
        
        try:
            file_bytes = storage.download_file(bucket, object_name)
        except Exception as e:
            logger.error(f"Failed to download NDA file: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to download NDA file: {str(e)}")
        
        # Generate tracking ID
        tracking_id = f"NDA-{nda_id[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"
        
        # Generate email subject and body
        email_subject = request.subject or f"Non-Disclosure Agreement - {nda_record.counterparty_name}"
        
        email_body_text = request.message or f"""Dear {nda_record.counterparty_name},

Please find attached the Non-Disclosure Agreement for your review and signature.

Please review the document carefully and return a signed copy at your earliest convenience.

If you have any questions or concerns, please do not hesitate to contact us.

Thank you for your cooperation.

Best regards,
NDA Management System
"""
        
        email_body_html = f"""<html>
<body>
<p>Dear {nda_record.counterparty_name},</p>
<p>Please find attached the <strong>Non-Disclosure Agreement</strong> for your review and signature.</p>
<p>Please review the document carefully and return a signed copy at your earliest convenience.</p>
<p>If you have any questions or concerns, please do not hesitate to contact us.</p>
<p>Thank you for your cooperation.</p>
<p>Best regards,<br>NDA Management System</p>
<hr>
<p><small>Tracking ID: {tracking_id}</small></p>
</body>
</html>"""
        
        # Send email
        email_service = get_email_service()
        try:
            # Run async email sending
            # Convert DOCX to PDF for customer (if file is DOCX)
            attachment_filename = f"NDA_{nda_record.counterparty_name.replace(' ', '_')}.pdf"
            attachment_content = file_bytes
            
            # File should already be PDF (converted during NDA creation)
            # But if it's DOCX, convert to PDF for customer
            if file_bytes.startswith(b'PK') and not file_bytes.startswith(b'%PDF'):
                try:
                    from api.services.template_service import TemplateService, create_template_service
                    import tempfile
                    import os
                    temp_template_service = create_template_service()
                    
                    # Save DOCX temporarily
                    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_docx:
                        temp_docx.write(file_bytes)
                        temp_docx_path = temp_docx.name
                    
                    temp_pdf_path = temp_docx_path.replace('.docx', '.pdf')
                    try:
                        from docx2pdf import convert
                        convert(temp_docx_path, temp_pdf_path)
                        with open(temp_pdf_path, 'rb') as pdf_file:
                            attachment_content = pdf_file.read()
                        attachment_filename = attachment_filename.replace('.docx', '.pdf')
                    except Exception as e:
                        logger.warning(f"Failed to convert DOCX to PDF, sending DOCX instead: {e}")
                        attachment_filename = f"NDA_{nda_record.counterparty_name.replace(' ', '_')}.docx"
                    finally:
                        try:
                            os.unlink(temp_docx_path)
                        except:
                            pass
                        try:
                            if os.path.exists(temp_pdf_path):
                                os.unlink(temp_pdf_path)
                        except:
                            pass
                except Exception as e:
                    logger.warning(f"Failed to convert DOCX to PDF, sending DOCX instead: {e}")
                    attachment_filename = f"NDA_{nda_record.counterparty_name.replace(' ', '_')}.docx"
            
            message_id = await email_service.send_email(
                to_addresses=request.to_addresses,
                subject=email_subject,
                body=email_body_text,
                body_html=email_body_html,
                cc_addresses=request.cc_addresses or [],
                attachments=[{
                    'filename': attachment_filename,
                    'content': attachment_content,
                }],
                tracking_id=tracking_id,
                nda_record_id=nda_id,
            )
            
            # Update NDA status to indicate it's been sent (but keep as 'created' for now)
            # The status will change to 'customer_signed' when we receive the signed version
            
            # Log audit action
            _log_audit_action(
                nda_record_id=nda_id,
                user_id=str(current_user.id),
                action="email_sent",
                details={
                    'to_addresses': request.to_addresses,
                    'cc_addresses': request.cc_addresses,
                    'tracking_id': tracking_id,
                    'message_id': message_id,
                },
            )
            
            logger.info(f"Sent NDA {nda_id} via email to {request.to_addresses}")
            
            return {
                'nda_id': nda_id,
                'message_id': message_id,
                'tracking_id': tracking_id,
                'sent_to': request.to_addresses,
                'status': 'sent',
                'message': 'NDA sent successfully via email',
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid NDA ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send NDA email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send NDA: {str(e)}")
    finally:
        db.close()


@router.post("/nda/{nda_id}/start-workflow")
async def start_workflow(
    nda_id: str,
    reviewer_user_id: Optional[str] = None,
    approver_user_id: Optional[str] = None,
    final_approver_user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Start Camunda workflow for an NDA
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db_session()
    try:
        nda_uuid = uuid.UUID(nda_id)
        nda_record = db.query(NDARecord).filter(NDARecord.id == nda_uuid).first()
        
        if not nda_record:
            raise HTTPException(status_code=404, detail="NDA record not found")
        
        # Check if workflow already started - allow deletion first
        if nda_record.workflow_instance_id:
            workflow_instance = db.query(NDAWorkflowInstance).filter(
                NDAWorkflowInstance.id == nda_record.workflow_instance_id
            ).first()
            if workflow_instance:
                # Check if process is still active
                camunda = get_camunda_service()
                process_instance = None
                if workflow_instance.camunda_process_instance_id:
                    process_instance = camunda.get_process_instance(workflow_instance.camunda_process_instance_id)
                
                if process_instance and process_instance.get("state") == "ACTIVE":
                    raise HTTPException(
                        status_code=400,
                        detail=f"Workflow already active. Please delete the existing workflow first (ID: {workflow_instance.id})",
                    )
                else:
                    # Process completed or doesn't exist, allow starting new one
                    # But warn user they should delete the old one first
                    logger.warning(f"NDA {nda_id} has a completed workflow instance. Starting new workflow.")
        
        # Get Camunda service
        camunda = get_camunda_service()
        
        # Start process instance
        process_variables = {
            "nda_record_id": nda_id,
            "reviewer_user_id": reviewer_user_id or str(current_user.id),
            "approver_user_id": approver_user_id or str(current_user.id),
            "final_approver_user_id": final_approver_user_id or str(current_user.id),
        }
        
        result = camunda.start_process_instance(
            process_key="nda_review_approval",
            variables=process_variables,
            business_key=f"NDA-{nda_id[:8].upper()}",
        )
        
        process_instance_id = result["id"]
        camunda_process_instance_id = result.get("id")
        
        # Create workflow instance record
        workflow_instance = NDAWorkflowInstance(
            nda_record_id=nda_uuid,
            camunda_process_instance_id=camunda_process_instance_id,
            current_status="started",
            started_at=datetime.utcnow(),
        )
        db.add(workflow_instance)
        db.flush()
        
        # Link to NDA record
        nda_record.workflow_instance_id = workflow_instance.id
        nda_record.status = "customer_signed"  # Update status when workflow starts
        db.commit()
        
        # Log audit action
        _log_audit_action(
            nda_record_id=nda_id,
            user_id=str(current_user.id),
            action="workflow_started",
            details={
                "camunda_process_instance_id": camunda_process_instance_id,
                "workflow_instance_id": str(workflow_instance.id),
            },
        )
        
        logger.info(f"Started workflow for NDA {nda_id}: {camunda_process_instance_id}")
        
        return {
            "workflow_instance_id": str(workflow_instance.id),
            "camunda_process_instance_id": camunda_process_instance_id,
            "status": "started",
            "message": "Workflow started successfully",
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid NDA ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start workflow: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")
    finally:
        db.close()


@router.get("/users")
async def list_users_for_workflow(
    current_user: User = Depends(get_current_user),
):
    """
    List users for workflow signer assignment
    
    Returns list of users that can be assigned as reviewers, approvers, or signers
    """
    db = get_db_session()
    try:
        users = db.query(User).filter(User.is_active == True).all()
        return [
            {
                "id": str(user.id),
                "username": user.username,
                "role": user.role,
            }
            for user in users
        ]
    finally:
        db.close()


@router.get("/workflows")
async def list_workflows(
    status: Optional[str] = None,
    include_ndas_without_workflow: bool = True,
    current_user: User = Depends(get_current_user),
):
    """
    List all workflow instances and optionally NDAs without workflows
    
    Args:
        status: Filter by workflow status
        include_ndas_without_workflow: Include NDAs that haven't started workflows yet
    """
    db = get_db_session()
    camunda = get_camunda_service()
    try:
        # Get workflow instances
        query = db.query(NDAWorkflowInstance)
        
        if status:
            query = query.filter(NDAWorkflowInstance.current_status == status)
        
        workflows = query.order_by(NDAWorkflowInstance.started_at.desc()).limit(100).all()
        
        workflow_list = []
        for w in workflows:
            # Sync workflow status with Camunda and NDA status
            actual_state = "UNKNOWN"
            camunda_state = None
            needs_update = False
            
            # Get associated NDA record to check its status
            nda_record = db.query(NDARecord).filter(NDARecord.workflow_instance_id == w.id).first()
            
            if w.camunda_process_instance_id:
                process_instance = camunda.get_process_instance(w.camunda_process_instance_id)
                if process_instance:
                    camunda_state = process_instance.get("state")
                    actual_state = camunda_state
                    
                    # Even if process is ACTIVE, check if NDA status indicates failure
                    if nda_record and nda_record.status == "llm_reviewed_rejected" and w.current_status == "started":
                        # LLM rejected but workflow status not updated - sync it
                        w.current_status = "failed_llm_rejected"
                        w.completed_at = datetime.utcnow()
                        needs_update = True
                else:
                    # Check history
                    process_history = camunda.get_process_instance_history(w.camunda_process_instance_id)
                    if process_history:
                        camunda_state = process_history.get("state")
                        actual_state = camunda_state
                        # Update workflow instance if completed
                        if camunda_state in ["COMPLETED", "TERMINATED", "DELETED"] and not w.completed_at:
                            w.completed_at = datetime.utcnow()
                            if camunda_state == "COMPLETED":
                                # Check variables to determine final status
                                variables = camunda.get_process_instance_variables(w.camunda_process_instance_id)
                                if variables.get("llm_approved") is False:
                                    w.current_status = "failed_llm_rejected"
                                elif variables.get("human_approved") is False:
                                    w.current_status = "failed_human_rejected"
                                elif variables.get("approval_approved") is False:
                                    w.current_status = "failed_approval_rejected"
                                else:
                                    w.current_status = "completed"
                            elif camunda_state == "TERMINATED":
                                w.current_status = "terminated"
                            needs_update = True
                    else:
                        # Process not found - check NDA status as fallback
                        if nda_record:
                            if nda_record.status == "llm_reviewed_rejected" and w.current_status == "started":
                                w.current_status = "failed_llm_rejected"
                                w.completed_at = datetime.utcnow()
                                needs_update = True
                            elif nda_record.status == "llm_reviewed_approved" and w.current_status == "started":
                                w.current_status = "llm_review_passed"
                                needs_update = True
            
            # Commit updates if needed
            if needs_update:
                db.commit()
            
            # Determine display status - prioritize current_status, fallback to actual_state
            display_status = w.current_status or actual_state or "unknown"
            
            workflow_list.append({
                "id": str(w.id),
                "nda_record_id": str(w.nda_record_id),
                "camunda_process_instance_id": w.camunda_process_instance_id,
                "current_status": w.current_status,
                "actual_state": actual_state,  # From Camunda (for reference)
                "display_status": display_status,  # Primary status for UI display
                "started_at": w.started_at.isoformat() if w.started_at else None,
                "completed_at": w.completed_at.isoformat() if w.completed_at else None,
                "has_workflow": True,
            })
        
        # Optionally include NDAs without workflows
        ndas_without_workflows = []
        if include_ndas_without_workflow:
            nda_query = db.query(NDARecord).filter(NDARecord.workflow_instance_id.is_(None))
            if status:
                # Filter by NDA status if workflow status filter is applied
                nda_query = nda_query.filter(NDARecord.status == status)
            
            ndas = nda_query.order_by(NDARecord.created_at.desc()).limit(100).all()
            ndas_without_workflows = [
                {
                    "id": None,  # No workflow instance ID yet
                    "nda_record_id": str(nda.id),
                    "camunda_process_instance_id": None,
                    "current_status": nda.status,
                    "actual_state": "NO_WORKFLOW",
                    "display_status": nda.status,  # Use NDA status as display status
                    "started_at": None,
                    "completed_at": None,
                    "has_workflow": False,
                }
                for nda in ndas
            ]
        
        # Combine and sort by created_at/started_at
        all_items = workflow_list + ndas_without_workflows
        all_items.sort(key=lambda x: x.get("started_at") or "", reverse=True)
        
        return {
            "workflows": all_items,
            "total": len(all_items),
            "with_workflows": len(workflow_list),
            "without_workflows": len(ndas_without_workflows),
        }
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list workflows: {str(e)}")
    finally:
        db.close()


@router.get("/workflow/{workflow_instance_id}/tasks")
async def get_workflow_tasks(
    workflow_instance_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get tasks for a workflow instance"""
    db = get_db_session()
    try:
        workflow_uuid = uuid.UUID(workflow_instance_id)
        workflow_instance = db.query(NDAWorkflowInstance).filter(
            NDAWorkflowInstance.id == workflow_uuid
        ).first()
        
        if not workflow_instance:
            raise HTTPException(status_code=404, detail="Workflow instance not found")
        
        # Sync workflow status before returning tasks
        camunda = get_camunda_service()
        camunda_process_id = workflow_instance.camunda_process_instance_id
        nda_record = db.query(NDARecord).filter(NDARecord.workflow_instance_id == workflow_uuid).first()
        
        if camunda_process_id:
            process_instance = camunda.get_process_instance(camunda_process_id)
            if not process_instance:
                # Check history
                process_history = camunda.get_process_instance_history(camunda_process_id)
                if process_history:
                    camunda_state = process_history.get("state")
                    if camunda_state in ["COMPLETED", "TERMINATED", "DELETED"] and not workflow_instance.completed_at:
                        workflow_instance.completed_at = datetime.utcnow()
                        if camunda_state == "COMPLETED":
                            variables = camunda.get_process_instance_variables(camunda_process_id)
                            if variables.get("llm_approved") is False:
                                workflow_instance.current_status = "failed_llm_rejected"
                            elif variables.get("human_approved") is False:
                                workflow_instance.current_status = "failed_human_rejected"
                            elif variables.get("approval_approved") is False:
                                workflow_instance.current_status = "failed_approval_rejected"
                            else:
                                workflow_instance.current_status = "completed"
                        elif camunda_state == "TERMINATED":
                            workflow_instance.current_status = "terminated"
                        db.commit()
            else:
                # Process is ACTIVE, but check NDA status as fallback
                if nda_record and nda_record.status == "llm_reviewed_rejected" and workflow_instance.current_status == "started":
                    workflow_instance.current_status = "failed_llm_rejected"
                    workflow_instance.completed_at = datetime.utcnow()
                    db.commit()
        
        # Get active tasks
        camunda_tasks = camunda.get_user_tasks(
            process_instance_id=camunda_process_id,
        )
        
        # If no active tasks, check if workflow is completed and get historic tasks
        historic_tasks = []
        if not camunda_tasks and camunda_process_id:
            # Check if process instance exists (might be completed)
            process_instance = camunda.get_process_instance(camunda_process_id)
            if not process_instance:
                # Process completed, get historic tasks
                historic_tasks = camunda.get_historic_tasks(
                    process_instance_id=camunda_process_id,
                    finished=True,
                )
                # Convert historic tasks to same format as active tasks
                camunda_tasks = [
                    {
                        "id": task.get("id"),
                        "name": task.get("name"),
                        "assignee": task.get("assignee"),
                        "created": task.get("startTime"),
                        "due": task.get("dueDate"),
                        "endTime": task.get("endTime"),
                        "completed": True,
                    }
                    for task in historic_tasks
                ]
        
        # Get tasks from database
        db_tasks = db.query(NDAWorkflowTask).filter(
            NDAWorkflowTask.workflow_instance_id == workflow_uuid
        ).all()
        
        return {
            "workflow_instance_id": workflow_instance_id,
            "workflow_status": workflow_instance.current_status,
            "camunda_process_instance_id": camunda_process_id,
            "camunda_tasks": camunda_tasks,
            "database_tasks": [
                {
                    "id": str(task.id),
                    "task_id": task.task_id,
                    "task_name": task.task_name,
                    "status": task.status,
                    "assignee_user_id": str(task.assignee_user_id) if task.assignee_user_id else None,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                }
                for task in db_tasks
            ],
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow instance ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get workflow tasks: {str(e)}")
    finally:
        db.close()


@router.post("/workflow/task/{task_id}/complete")
async def complete_workflow_task(
    task_id: str,
    approved: bool,
    comments: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Complete a workflow task (user task)
    
    Requires admin role or task assignee
    """
    db = get_db_session()
    try:
        # Get task from Camunda
        camunda = get_camunda_service()
        camunda_tasks = camunda.get_user_tasks()
        task = next((t for t in camunda_tasks if t.get("id") == task_id), None)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Check authorization
        task_assignee = task.get("assignee")
        if current_user.role != "admin" and str(current_user.id) != task_assignee:
            raise HTTPException(status_code=403, detail="Not authorized to complete this task")
        
        # Determine variable name based on task name
        task_name = task.get("name", "").lower()
        if "human review" in task_name:
            variable_name = "human_approved"
        elif "internal signature" in task_name or "internal signer" in task_name:
            variable_name = "internal_signed"
        elif "approval" in task_name and "final" not in task_name:
            variable_name = "approval_approved"
        elif "final approval" in task_name:
            variable_name = "final_approved"
        else:
            variable_name = "approved"
        
        # Complete task in Camunda
        success = camunda.complete_user_task(
            task_id=task_id,
            variables={variable_name: approved},
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to complete task in Camunda")
        
        # Update NDA status
        process_instance_id = task.get("processInstanceId")
        if process_instance_id:
            workflow_instance = db.query(NDAWorkflowInstance).filter(
                NDAWorkflowInstance.camunda_process_instance_id == process_instance_id
            ).first()
            
            if workflow_instance:
                nda_record = db.query(NDARecord).filter(
                    NDARecord.workflow_instance_id == workflow_instance.id
                ).first()
                
                if nda_record:
                    if approved:
                        if "internal signature" in task_name.lower() or "internal signer" in task_name.lower():
                            nda_record.status = "approved"
                        elif "final" in task_name.lower():
                            nda_record.status = "approved"
                        else:
                            nda_record.status = "reviewed"
                    else:
                        nda_record.status = "rejected"
                    
                    db.commit()
        
        # Log audit action
        if workflow_instance and nda_record:
            _log_audit_action(
                nda_record_id=str(nda_record.id),
                user_id=str(current_user.id),
                action="task_completed",
                details={
                    "task_id": task_id,
                    "task_name": task.get("name"),
                    "approved": approved,
                    "comments": comments,
                },
            )
        
        return {
            "task_id": task_id,
            "completed": True,
            "approved": approved,
            "message": "Task completed successfully",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete task: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to complete task: {str(e)}")
    finally:
        db.close()


@router.post("/workflow/{workflow_instance_id}/customer-signed")
async def trigger_customer_signed(
    workflow_instance_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Trigger customer signed event - called when customer sends back signed document
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db_session()
    try:
        workflow_uuid = uuid.UUID(workflow_instance_id)
        workflow_instance = db.query(NDAWorkflowInstance).filter(
            NDAWorkflowInstance.id == workflow_uuid
        ).first()
        
        if not workflow_instance:
            raise HTTPException(status_code=404, detail="Workflow instance not found")
        
        camunda = get_camunda_service()
        camunda_process_id = workflow_instance.camunda_process_instance_id
        
        if not camunda_process_id:
            raise HTTPException(status_code=400, detail="No Camunda process instance found")
        
        # Correlate message to trigger intermediate catch event
        success = camunda.correlate_message(
            message_name="CustomerSignedMessage",
            process_instance_id=camunda_process_id,
            variables={"customer_signed": True},
        )
        
        if not success:
            logger.warning(f"Failed to correlate message for workflow {workflow_instance_id}")
        
        # Update NDA status
        nda_record = db.query(NDARecord).filter(
            NDARecord.workflow_instance_id == workflow_uuid
        ).first()
        
        if nda_record:
            nda_record.status = "customer_signed"
            workflow_instance.current_status = "customer_signed"
            db.commit()
        
        logger.info(f"Customer signed event triggered for workflow {workflow_instance_id}")
        
        return {
            "message": "Customer signed event triggered",
            "workflow_instance_id": workflow_instance_id,
            "message_correlated": success,
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow instance ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger customer signed: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to trigger customer signed: {str(e)}")
    finally:
        db.close()


@router.post("/email/poll")
async def poll_emails_manual(
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger email polling (for testing)
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        from api.workers.email_poller import EmailPoller
        
        poller = EmailPoller()
        messages = await poller.email_service.check_imap_messages()
        
        processed_count = 0
        for email_data in messages:
            try:
                await poller._process_email(email_data)
                processed_count += 1
            except Exception as e:
                logger.error(f"Failed to process email: {e}", exc_info=True)
        
        return {
            'message': 'Email polling completed',
            'emails_found': len(messages),
            'emails_processed': processed_count,
        }
    except Exception as e:
        logger.error(f"Failed to poll emails: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to poll emails: {str(e)}")


@router.post("/nda/{nda_id}/update-status")
async def update_nda_status(
    nda_id: str,
    status: str,
    current_user: User = Depends(get_current_user),
):
    """
    Manually update NDA status
    
    Requires admin role
    Status should be passed as query parameter: ?status=created
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Validate status
    valid_statuses = [
        'created', 'draft', 'negotiating', 'customer_signed',
        'llm_reviewed_approved', 'llm_reviewed_rejected',
        'reviewed', 'approved', 'rejected', 'signed',
        'archived', 'expired', 'active', 'terminated'
    ]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
    
    db = get_db_session()
    try:
        nda_uuid = uuid.UUID(nda_id)
        nda_record = db.query(NDARecord).filter(NDARecord.id == nda_uuid).first()
        
        if not nda_record:
            raise HTTPException(status_code=404, detail="NDA not found")
        
        old_status = nda_record.status
        nda_record.status = status
        db.commit()
        
        # Log audit action
        _log_audit_action(
            nda_record_id=nda_id,
            user_id=str(current_user.id),
            action="status_changed",
            details={
                'old_status': old_status,
                'new_status': status,
            },
        )
        
        logger.info(f"Updated NDA {nda_id} status: {old_status} -> {status}")
        return {
            'id': str(nda_record.id),
            'status': nda_record.status,
            'message': f'Status updated from {old_status} to {status}',
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid NDA ID")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update NDA status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")
    finally:
        db.close()


@router.post("/bpmn/deploy")
async def deploy_bpmn_workflows(current_user: User = Depends(get_current_user)):
    """
    Manually deploy BPMN workflow definitions to Camunda
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        from pathlib import Path
        
        camunda = get_camunda_service()
        
        # Check if Camunda is accessible
        if not camunda.health_check():
            raise HTTPException(status_code=503, detail="Camunda is not accessible. Is it running?")
        
        # Find BPMN files
        bpmn_dir = Path("/app/camunda/bpmn")
        if not bpmn_dir.exists():
            # Try relative path
            project_root = Path(__file__).parent.parent.parent
            bpmn_dir = project_root / "camunda" / "bpmn"
        
        if not bpmn_dir.exists():
            raise HTTPException(status_code=404, detail=f"BPMN directory not found: {bpmn_dir}")
        
        bpmn_files = list(bpmn_dir.glob("*.bpmn"))
        if not bpmn_files:
            raise HTTPException(status_code=404, detail=f"No BPMN files found in {bpmn_dir}")
        
        results = []
        deployed = 0
        skipped = 0
        failed = 0
        
        for bpmn_file in bpmn_files:
            process_key = bpmn_file.stem
            
            # Check if already deployed
            existing = camunda.get_process_definition_key(process_key)
            if existing:
                results.append({
                    'file': bpmn_file.name,
                    'process_key': process_key,
                    'status': 'skipped',
                    'message': f"Already deployed (version {existing.get('version', '?')})"
                })
                skipped += 1
                continue
            
            # Deploy the BPMN file
            result = camunda.deploy_process_definition(str(bpmn_file))
            if result:
                results.append({
                    'file': bpmn_file.name,
                    'process_key': process_key,
                    'status': 'deployed',
                    'deployment_id': result.get('id'),
                    'message': 'Successfully deployed'
                })
                deployed += 1
            else:
                results.append({
                    'file': bpmn_file.name,
                    'process_key': process_key,
                    'status': 'failed',
                    'message': 'Deployment failed'
                })
                failed += 1
        
        return {
            'summary': {
                'total': len(bpmn_files),
                'deployed': deployed,
                'skipped': skipped,
                'failed': failed
            },
            'results': results
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deploy BPMN workflows: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to deploy BPMN workflows: {str(e)}")


@router.post("/workflow/{workflow_instance_id}/restart")
async def restart_workflow(
    workflow_instance_id: str,
    reviewer_user_id: Optional[str] = None,
    approver_user_id: Optional[str] = None,
    final_approver_user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Restart a workflow for an NDA
    Deletes the old workflow instance and starts a new one
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db_session()
    try:
        workflow_uuid = uuid.UUID(workflow_instance_id)
        workflow_instance = db.query(NDAWorkflowInstance).filter(
            NDAWorkflowInstance.id == workflow_uuid
        ).first()
        
        if not workflow_instance:
            raise HTTPException(status_code=404, detail="Workflow instance not found")
        
        nda_record = db.query(NDARecord).filter(
            NDARecord.id == workflow_instance.nda_record_id
        ).first()
        
        if not nda_record:
            raise HTTPException(status_code=404, detail="NDA record not found")
        
        nda_id = str(nda_record.id)
        camunda_process_instance_id = workflow_instance.camunda_process_instance_id
        
        # Delete/terminate old Camunda process instance if it exists
        camunda = get_camunda_service()
        if camunda_process_instance_id:
            # Try to terminate if running, delete if completed
            process_instance = camunda.get_process_instance(camunda_process_instance_id)
            if process_instance:
                if process_instance.get("state") == "ACTIVE":
                    camunda.terminate_process_instance(camunda_process_instance_id)
                else:
                    camunda.delete_process_instance(camunda_process_instance_id)
        
        # Delete old workflow instance
        db.delete(workflow_instance)
        nda_record.workflow_instance_id = None
        db.flush()
        
        # Start new workflow
        process_variables = {
            "nda_record_id": nda_id,
            "reviewer_user_id": reviewer_user_id or str(current_user.id),
            "approver_user_id": approver_user_id or str(current_user.id),
            "final_approver_user_id": final_approver_user_id or str(current_user.id),
        }
        
        result = camunda.start_process_instance(
            process_key="nda_review_approval",
            variables=process_variables,
            business_key=f"NDA-{nda_id[:8].upper()}",
        )
        
        new_camunda_process_instance_id = result.get("id")
        
        # Create new workflow instance record
        new_workflow_instance = NDAWorkflowInstance(
            nda_record_id=nda_record.id,
            camunda_process_instance_id=new_camunda_process_instance_id,
            current_status="started",
            started_at=datetime.utcnow(),
        )
        db.add(new_workflow_instance)
        db.flush()
        
        # Link to NDA record
        nda_record.workflow_instance_id = new_workflow_instance.id
        nda_record.status = "customer_signed"
        db.commit()
        
        # Log audit action
        _log_audit_action(
            nda_record_id=nda_id,
            user_id=str(current_user.id),
            action="workflow_restarted",
            details={
                "old_camunda_process_instance_id": camunda_process_instance_id,
                "new_camunda_process_instance_id": new_camunda_process_instance_id,
                "workflow_instance_id": str(new_workflow_instance.id),
            },
        )
        
        logger.info(f"Restarted workflow for NDA {nda_id}: {new_camunda_process_instance_id}")
        
        return {
            "workflow_instance_id": str(new_workflow_instance.id),
            "camunda_process_instance_id": new_camunda_process_instance_id,
            "status": "started",
            "message": "Workflow restarted successfully",
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow instance ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restart workflow: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to restart workflow: {str(e)}")
    finally:
        db.close()


@router.get("/workflow/{workflow_instance_id}/details")
async def get_workflow_details(
    workflow_instance_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed workflow information including state, variables, activities, and incidents
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db_session()
    try:
        workflow_uuid = uuid.UUID(workflow_instance_id)
        workflow_instance = db.query(NDAWorkflowInstance).filter(
            NDAWorkflowInstance.id == workflow_uuid
        ).first()
        
        if not workflow_instance:
            raise HTTPException(status_code=404, detail="Workflow instance not found")
        
        camunda = get_camunda_service()
        camunda_process_id = workflow_instance.camunda_process_instance_id
        
        # Get process instance (active or from history)
        process_instance = camunda.get_process_instance(camunda_process_id)
        process_history = None
        if not process_instance and camunda_process_id:
            process_history = camunda.get_process_instance_history(camunda_process_id)
        
        # Get variables
        variables = {}
        if camunda_process_id:
            variables = camunda.get_process_instance_variables(camunda_process_id)
        
        # Get activity instances (execution path)
        activities = []
        if camunda_process_id:
            activities = camunda.get_activity_instances(camunda_process_id)
        
        # Get incidents (errors)
        incidents = []
        if camunda_process_id:
            incidents = camunda.get_incidents(camunda_process_id)
        
        # Get tasks
        active_tasks = camunda.get_user_tasks(process_instance_id=camunda_process_id) if camunda_process_id else []
        historic_tasks = []
        if not active_tasks and camunda_process_id:
            historic_tasks = camunda.get_historic_tasks(process_instance_id=camunda_process_id, finished=True)
        
        # Get external tasks
        external_tasks = camunda.get_external_tasks(process_instance_id=camunda_process_id) if camunda_process_id else []
        
        # Determine state
        state = "UNKNOWN"
        if process_instance:
            state = process_instance.get("state", "UNKNOWN")
        elif process_history:
            state = process_history.get("state", "COMPLETED")
        
        return {
            "workflow_instance_id": workflow_instance_id,
            "camunda_process_instance_id": camunda_process_id,
            "state": state,
            "current_status": workflow_instance.current_status,
            "started_at": workflow_instance.started_at.isoformat() if workflow_instance.started_at else None,
            "completed_at": workflow_instance.completed_at.isoformat() if workflow_instance.completed_at else None,
            "process_instance": process_instance or process_history,
            "variables": variables,
            "activities": activities,
            "incidents": incidents,
            "active_tasks": active_tasks,
            "historic_tasks": historic_tasks,
            "external_tasks": external_tasks,
            "diagnostics": {
                "has_active_process": process_instance is not None,
                "has_completed_process": process_history is not None,
                "has_incidents": len(incidents) > 0,
                "has_active_tasks": len(active_tasks) > 0,
                "has_external_tasks": len(external_tasks) > 0,
                "task_count": len(active_tasks) + len(historic_tasks),
            },
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow instance ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get workflow details: {str(e)}")
    finally:
        db.close()


@router.delete("/nda/{nda_id}")
async def delete_nda(
    nda_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Delete an NDA record and its workflow (if exists)
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db_session()
    try:
        nda_uuid = uuid.UUID(nda_id)
        nda_record = db.query(NDARecord).filter(NDARecord.id == nda_uuid).first()
        
        if not nda_record:
            raise HTTPException(status_code=404, detail="NDA record not found")
        
        # Delete workflow if exists
        if nda_record.workflow_instance_id:
            workflow_instance = db.query(NDAWorkflowInstance).filter(
                NDAWorkflowInstance.id == nda_record.workflow_instance_id
            ).first()
            
            if workflow_instance:
                camunda = get_camunda_service()
                camunda_process_id = workflow_instance.camunda_process_instance_id
                
                # Delete/terminate Camunda process instance
                if camunda_process_id:
                    process_instance = camunda.get_process_instance(camunda_process_id)
                    if process_instance:
                        if process_instance.get("state") == "ACTIVE":
                            camunda.terminate_process_instance(camunda_process_id)
                        else:
                            camunda.delete_process_instance(camunda_process_id)
                    else:
                        camunda.delete_process_instance(camunda_process_id)
                
                # Delete workflow tasks
                db.query(NDAWorkflowTask).filter(
                    NDAWorkflowTask.workflow_instance_id == workflow_instance.id
                ).delete()
                
                # Delete workflow instance
                db.delete(workflow_instance)
        
        # Delete audit logs for this NDA
        db.query(NDAAuditLog).filter(
            NDAAuditLog.nda_record_id == nda_uuid
        ).delete(synchronize_session=False)
        
        # Delete NDA events for this NDA
        db.query(NDAEvent).filter(
            NDAEvent.nda_id == nda_uuid
        ).delete(synchronize_session=False)
        
        # Delete NDA record
        db.delete(nda_record)
        db.commit()
        
        logger.info(f"Deleted NDA {nda_id}")
        
        return {
            "message": "NDA deleted successfully",
            "nda_id": nda_id,
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid NDA ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete NDA: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete NDA: {str(e)}")
    finally:
        db.close()


@router.delete("/workflow/{workflow_instance_id}")
async def delete_workflow(
    workflow_instance_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Delete/terminate a workflow instance
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db_session()
    try:
        workflow_uuid = uuid.UUID(workflow_instance_id)
        workflow_instance = db.query(NDAWorkflowInstance).filter(
            NDAWorkflowInstance.id == workflow_uuid
        ).first()
        
        if not workflow_instance:
            raise HTTPException(status_code=404, detail="Workflow instance not found")
        
        nda_record = db.query(NDARecord).filter(
            NDARecord.id == workflow_instance.nda_record_id
        ).first()
        
        if not nda_record:
            raise HTTPException(status_code=404, detail="NDA record not found")
        
        nda_id = str(nda_record.id)
        camunda_process_instance_id = workflow_instance.camunda_process_instance_id
        
        # Delete/terminate Camunda process instance
        camunda = get_camunda_service()
        if camunda_process_instance_id:
            # Try to terminate if running, delete if completed
            process_instance = camunda.get_process_instance(camunda_process_instance_id)
            if process_instance:
                if process_instance.get("state") == "ACTIVE":
                    success = camunda.terminate_process_instance(camunda_process_instance_id)
                    if not success:
                        logger.warning(f"Failed to terminate process instance {camunda_process_instance_id}, continuing with deletion")
                else:
                    camunda.delete_process_instance(camunda_process_instance_id)
            else:
                # Process instance doesn't exist in Camunda, try to delete anyway
                camunda.delete_process_instance(camunda_process_instance_id)
        
        # Delete workflow instance and tasks
        db.query(NDAWorkflowTask).filter(
            NDAWorkflowTask.workflow_instance_id == workflow_uuid
        ).delete()
        
        db.delete(workflow_instance)
        nda_record.workflow_instance_id = None
        db.commit()
        
        # Log audit action
        _log_audit_action(
            nda_record_id=nda_id,
            user_id=str(current_user.id),
            action="workflow_deleted",
            details={
                "camunda_process_instance_id": camunda_process_instance_id,
                "workflow_instance_id": workflow_instance_id,
            },
        )
        
        logger.info(f"Deleted workflow instance {workflow_instance_id} for NDA {nda_id}")
        
        return {
            "message": "Workflow deleted successfully",
            "workflow_instance_id": workflow_instance_id,
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow instance ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete workflow: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete workflow: {str(e)}")
    finally:
        db.close()


@router.put("/workflow/{workflow_instance_id}")
async def update_workflow(
    workflow_instance_id: str,
    reviewer_user_id: Optional[str] = None,
    approver_user_id: Optional[str] = None,
    internal_signer_user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Update workflow signers
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db = get_db_session()
    try:
        workflow_uuid = uuid.UUID(workflow_instance_id)
        workflow_instance = db.query(NDAWorkflowInstance).filter(
            NDAWorkflowInstance.id == workflow_uuid
        ).first()
        
        if not workflow_instance:
            raise HTTPException(status_code=404, detail="Workflow instance not found")
        
        # Update Camunda process variables if workflow is active
        camunda = get_camunda_service()
        if workflow_instance.camunda_process_instance_id:
            process_instance = camunda.get_process_instance(workflow_instance.camunda_process_instance_id)
            if process_instance and process_instance.get("state") == "ACTIVE":
                # Update variables in Camunda
                if reviewer_user_id:
                    camunda.set_process_variable(
                        workflow_instance.camunda_process_instance_id,
                        "reviewer_user_id",
                        reviewer_user_id
                    )
                if approver_user_id:
                    camunda.set_process_variable(
                        workflow_instance.camunda_process_instance_id,
                        "approver_user_id",
                        approver_user_id
                    )
                if internal_signer_user_id:
                    camunda.set_process_variable(
                        workflow_instance.camunda_process_instance_id,
                        "internal_signer_user_id",
                        internal_signer_user_id
                    )
        
        db.commit()
        
        _log_audit_action(
            nda_record_id=str(workflow_instance.nda_record_id),
            user_id=str(current_user.id),
            action="workflow_updated",
            details={
                "workflow_instance_id": workflow_instance_id,
                "reviewer_user_id": reviewer_user_id,
                "approver_user_id": approver_user_id,
                "internal_signer_user_id": internal_signer_user_id,
            },
        )
        
        return {
            "message": "Workflow updated successfully",
            "workflow_instance_id": workflow_instance_id,
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow instance ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update workflow: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update workflow: {str(e)}")
    finally:
        db.close()


@router.post("/workflow/{workflow_instance_id}/override")
async def override_workflow(
    workflow_instance_id: str,
    action: str,  # "approve", "reject", "retry"
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Override workflow state - approve, reject, or retry a failed workflow
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if action not in ["approve", "reject", "retry"]:
        raise HTTPException(status_code=400, detail="Action must be 'approve', 'reject', or 'retry'")
    
    db = get_db_session()
    try:
        workflow_uuid = uuid.UUID(workflow_instance_id)
        workflow_instance = db.query(NDAWorkflowInstance).filter(
            NDAWorkflowInstance.id == workflow_uuid
        ).first()
        
        if not workflow_instance:
            raise HTTPException(status_code=404, detail="Workflow instance not found")
        
        nda_record = db.query(NDARecord).filter(
            NDARecord.id == workflow_instance.nda_record_id
        ).first()
        
        if not nda_record:
            raise HTTPException(status_code=404, detail="NDA record not found")
        
        nda_id = str(nda_record.id)
        
        if action == "approve":
            # Manually approve - set status to approved
            nda_record.status = "approved"
            workflow_instance.current_status = "completed_override"
            workflow_instance.completed_at = datetime.utcnow()
            db.commit()
            
            _log_audit_action(
                nda_record_id=nda_id,
                user_id=str(current_user.id),
                action="workflow_override_approved",
                details={
                    "workflow_instance_id": workflow_instance_id,
                    "reason": reason,
                },
            )
            
            return {
                "message": "Workflow manually approved",
                "nda_id": nda_id,
                "status": "approved",
            }
            
        elif action == "reject":
            # Manually reject
            nda_record.status = "rejected"
            workflow_instance.current_status = "rejected_override"
            workflow_instance.completed_at = datetime.utcnow()
            db.commit()
            
            _log_audit_action(
                nda_record_id=nda_id,
                user_id=str(current_user.id),
                action="workflow_override_rejected",
                details={
                    "workflow_instance_id": workflow_instance_id,
                    "reason": reason,
                },
            )
            
            return {
                "message": "Workflow manually rejected",
                "nda_id": nda_id,
                "status": "rejected",
            }
            
        elif action == "retry":
            # Retry workflow - delete old and start new
            camunda = get_camunda_service()
            camunda_process_id = workflow_instance.camunda_process_instance_id
            
            # Delete old process instance
            if camunda_process_id:
                process_instance = camunda.get_process_instance(camunda_process_id)
                if process_instance:
                    if process_instance.get("state") == "ACTIVE":
                        camunda.terminate_process_instance(camunda_process_id)
                    else:
                        camunda.delete_process_instance(camunda_process_id)
            
            # Delete old workflow instance
            db.delete(workflow_instance)
            nda_record.workflow_instance_id = None
            db.flush()
            
            # Start new workflow
            process_variables = {
                "nda_record_id": nda_id,
                "reviewer_user_id": str(current_user.id),
                "approver_user_id": str(current_user.id),
                "final_approver_user_id": str(current_user.id),
            }
            
            result = camunda.start_process_instance(
                process_key="nda_review_approval",
                variables=process_variables,
                business_key=f"NDA-{nda_id[:8].upper()}",
            )
            
            new_camunda_process_id = result.get("id")
            
            # Create new workflow instance
            new_workflow_instance = NDAWorkflowInstance(
                nda_record_id=nda_record.id,
                camunda_process_instance_id=new_camunda_process_id,
                current_status="started",
                started_at=datetime.utcnow(),
            )
            db.add(new_workflow_instance)
            db.flush()
            
            nda_record.workflow_instance_id = new_workflow_instance.id
            nda_record.status = "customer_signed"
            db.commit()
            
            _log_audit_action(
                nda_record_id=nda_id,
                user_id=str(current_user.id),
                action="workflow_retry",
                details={
                    "old_workflow_instance_id": workflow_instance_id,
                    "new_workflow_instance_id": str(new_workflow_instance.id),
                    "reason": reason,
                },
            )
            
            return {
                "message": "Workflow retried successfully",
                "nda_id": nda_id,
                "new_workflow_instance_id": str(new_workflow_instance.id),
            }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow instance ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to override workflow: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to override workflow: {str(e)}")
    finally:
        db.close()

