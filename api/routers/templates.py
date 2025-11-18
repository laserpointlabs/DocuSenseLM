"""
Template router for managing NDA templates
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.responses import Response
from typing import Optional, List
import base64
import logging

from api.db.schema import User
from api.middleware.auth import get_current_user
from api.models.requests import TemplateCreateRequest, TemplateUpdateRequest, TemplateRenderRequest
from api.models.responses import TemplateResponse, TemplateListResponse, TemplateRenderResponse
from api.services.template_service import TemplateService, create_template_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])

# Initialize template service
template_service = create_template_service()


def _template_to_response(template) -> TemplateResponse:
    """Convert template ORM object to response model"""
    return TemplateResponse(
        id=str(template.id),
        name=template.name,
        description=template.description,
        file_path=template.file_path,
        is_active=template.is_active,
        created_by=str(template.created_by) if template.created_by else None,
        created_at=template.created_at,
        updated_at=template.updated_at,
        version=getattr(template, 'version', 1),
        template_key=getattr(template, 'template_key', None),
        is_current=getattr(template, 'is_current', True),
        change_notes=getattr(template, 'change_notes', None),
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
    Create a new template or new version of existing template
    
    If template_key is provided and exists, creates a new version.
    Otherwise creates a new template.
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Validate file type
    if not file.filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="Template must be a DOCX file")
    
    try:
        # Read file content
        file_data = await file.read()
        
        # Create template (will create new version if template_key exists)
        template = template_service.create_template(
            name=name,
            description=description,
            file_data=file_data,
            created_by=str(current_user.id),
            template_key=template_key,
            change_notes=change_notes,
        )
        
        return _template_to_response(template)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(status_code=500, detail="Failed to create template")


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    active_only: bool = Query(True),
    current_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
):
    """
    List all templates
    
    Args:
        active_only: Only return active templates
        current_only: Only return current versions (latest version of each template_key)
    """
    templates = template_service.list_templates(active_only=active_only, current_only=current_only)
    return TemplateListResponse(
        templates=[_template_to_response(t) for t in templates],
        total=len(templates),
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    version: Optional[int] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Get template by ID or template_key
    
    Args:
        template_id: Template ID or template_key
        version: Specific version number (None = get current version)
    """
    template = template_service.get_template(template_id, version=version)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return _template_to_response(template)


@router.get("/{template_key}/versions", response_model=TemplateListResponse)
async def list_template_versions(
    template_key: str,
    current_user: User = Depends(get_current_user),
):
    """
    List all versions of a template
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    versions = template_service.list_template_versions(template_key)
    return TemplateListResponse(
        templates=[_template_to_response(v) for v in versions],
        total=len(versions),
    )


@router.post("/{template_key}/versions/{version}/set-current", response_model=TemplateResponse)
async def set_current_version(
    template_key: str,
    version: int,
    current_user: User = Depends(get_current_user),
):
    """
    Set a specific version as the current/default version
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    template = template_service.set_current_version(template_key, version)
    if not template:
        raise HTTPException(status_code=404, detail="Template version not found")
    
    return _template_to_response(template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    request: TemplateUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Update template metadata
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    template = template_service.update_template(
        template_id=template_id,
        name=request.name,
        description=request.description,
        is_active=request.is_active,
    )
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return _template_to_response(template)


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    version: Optional[int] = Query(None, description="Specific version to delete (None = delete all versions)"),
    current_user: User = Depends(get_current_user),
):
    """
    Delete template or specific version
    
    Args:
        template_id: Template ID or template_key
        version: Specific version to delete (None = delete all versions)
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    success = template_service.delete_template(template_id, version=version)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if version:
        return {"message": f"Template version {version} deleted successfully"}
    else:
        return {"message": "Template and all versions deleted successfully"}


@router.delete("/{template_key}/versions/{version}")
async def delete_template_version(
    template_key: str,
    version: int,
    current_user: User = Depends(get_current_user),
):
    """
    Delete a specific version of a template
    
    Args:
        template_key: Template key
        version: Version number to delete
    
    Requires admin role
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    success = template_service.delete_template_version(template_key, version)
    if not success:
        raise HTTPException(status_code=404, detail="Template version not found")
    
    return {"message": f"Template version {version} deleted successfully"}


@router.post("/{template_id}/render", response_class=Response)
async def render_template(
    template_id: str,
    request: TemplateRenderRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Render template with provided data
    
    Returns rendered DOCX file
    """
    try:
        rendered_bytes = template_service.render_template(
            template_id=template_id,
            data=request.data,
        )
        
        # Get template name for filename
        template = template_service.get_template(template_id)
        filename = f"{template.name}_rendered.docx" if template else "rendered.docx"
        
        return Response(
            content=rendered_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to render template: {e}")
        raise HTTPException(status_code=500, detail="Failed to render template")


@router.get("/{template_id}/file", response_class=Response)
async def get_template_file(
    template_id: str,
    version: Optional[int] = None,
    format: str = Query("docx", regex="^(docx|pdf)$"),
    current_user: User = Depends(get_current_user),
):
    """
    Download template file (DOCX or PDF)
    
    Args:
        template_id: Template ID or template_key
        version: Specific version number (None = get current version)
        format: File format - "docx" (original) or "pdf" (converted for viewing/sending)
    """
    try:
        template = template_service.get_template(template_id, version=version)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        if format == "pdf":
            # Get PDF version (converted from DOCX)
            file_bytes = template_service.convert_template_to_pdf(template_id, version=version)
            filename = f"{template.name}_v{template.version}.pdf" if template.version else f"{template.name}.pdf"
            media_type = "application/pdf"
            disposition = "inline"  # Show in browser
        else:
            # Get original DOCX file
            file_bytes = template_service.get_template_file(template_id, version=version)
            filename = f"{template.name}_v{template.version}.docx" if template.version else f"{template.name}.docx"
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            disposition = "attachment"  # Download
        
        return Response(
            content=file_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f'{disposition}; filename="{filename}"'
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get template file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve template file")


@router.get("/{template_id}/variables")
async def get_template_variables(
    template_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get list of variables found in template"""
    template = template_service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    variables = template_service.get_template_variables(template_id)
    return {"variables": variables}


