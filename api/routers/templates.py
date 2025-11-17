"""
Template router for managing NDA templates

Provides REST API endpoints for:
- Creating templates (with versioning)
- Listing templates  
- Rendering templates with data
- Template version management

Integrates with TemplateService (Task 1.3) and authentication.
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.responses import Response
from typing import Optional, List
import base64
import logging

from api.db.schema import User
from api.middleware.auth import get_current_user
from api.models.requests import TemplateRenderRequest
from api.models.responses import TemplateResponse, TemplateListResponse, TemplateRenderResponse
from api.services.template_service import get_template_service, TemplateNotFoundError, TemplateValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])


def _template_to_response(template) -> TemplateResponse:
    """Convert template entity to response model"""
    return TemplateResponse(
        id=str(template.id),
        name=template.name,
        description=template.description,
        file_path=template.file_path,
        version=template.version,
        template_key=template.template_key,
        is_active=template.is_active,
        is_current=template.is_current,
        created_by=str(template.created_by) if template.created_by else None,
        created_at=template.created_at,
        updated_at=template.updated_at,
        change_notes=template.change_notes,
    )


@router.post("", response_model=TemplateResponse)
async def create_template(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    template_key: Optional[str] = Form(None),
    change_notes: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Create new template or new version of existing template
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Validate file type
    if not file.content_type or "wordprocessingml" not in file.content_type:
        raise HTTPException(status_code=400, detail="File must be a DOCX document")
    
    try:
        # Read file data
        file_data = await file.read()
        
        # Create template
        template_service = get_template_service()
        template = template_service.create_template(
            name=name,
            description=description,
            file_data=file_data,
            created_by=str(current_user.id),
            template_key=template_key,
            change_notes=change_notes,
        )
        
        logger.info(f"Created template {template.id}: {name} (v{template.version})")
        return _template_to_response(template)
        
    except TemplateValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(status_code=500, detail="Failed to create template")


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    active_only: bool = Query(False, description="Show only active templates"),
    current_only: bool = Query(True, description="Show only current versions"),
    current_user: User = Depends(get_current_user),
):
    """
    List templates with optional filtering
    """
    try:
        template_service = get_template_service()
        templates = template_service.list_templates(
            active_only=active_only,
            current_only=current_only
        )
        
        return TemplateListResponse(
            templates=[_template_to_response(t) for t in templates],
            total=len(templates)
        )
        
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to list templates")


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get template by ID"""
    try:
        template_service = get_template_service()
        template = template_service.get_template(template_id)
        
        return _template_to_response(template)
        
    except TemplateNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found")
    except Exception as e:
        logger.error(f"Failed to get template: {e}")
        raise HTTPException(status_code=500, detail="Failed to get template")


@router.post("/{template_id}/render", response_model=TemplateRenderResponse)
async def render_template(
    template_id: str,
    request: TemplateRenderRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Render template with provided data
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        template_service = get_template_service()
        
        # Render template
        rendered_bytes = template_service.render_template(
            template_id=template_id,
            data=request.data
        )
        
        # Encode as base64 for JSON response
        file_data_b64 = base64.b64encode(rendered_bytes).decode()
        filename = f"rendered_template_{template_id[:8]}.docx"
        
        return TemplateRenderResponse(
            file_data=file_data_b64,
            filename=filename
        )
        
    except TemplateNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found")
    except TemplateValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to render template: {e}")
        raise HTTPException(status_code=500, detail="Failed to render template")


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Delete template (soft delete - set inactive)
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        template_service = get_template_service()
        template_service.delete_template(template_id)
        
        return {"message": "Template deleted successfully"}
        
    except TemplateNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found")
    except Exception as e:
        logger.error(f"Failed to delete template: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete template")