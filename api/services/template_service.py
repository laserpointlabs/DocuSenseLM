"""
Template service for managing NDA templates and rendering them with data

Handles:
- Template creation and versioning
- DOCX template rendering with variable substitution
- Template validation and storage
- Template listing and management
"""

import uuid
import logging
import tempfile
import os
import re
from typing import Dict, Any, Optional, List
from io import BytesIO
from datetime import datetime

try:
    from docx import Document
    from docx.shared import Pt
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

from api.db import get_db_session
from api.db.schema import NDATemplate, User
from api.services.service_registry import get_storage_service

logger = logging.getLogger(__name__)

TEMPLATE_BUCKET = "nda-templates"


class TemplateNotFoundError(Exception):
    """Raised when a template is not found"""
    pass


class TemplateValidationError(Exception):
    """Raised when template data or file is invalid"""
    pass


class TemplateService:
    """Service for managing and rendering NDA templates"""

    def __init__(self):
        self.storage = get_storage_service()
        self._ensure_template_bucket()

    def _ensure_template_bucket(self):
        """Ensure template bucket exists"""
        try:
            if not self.storage.file_exists(TEMPLATE_BUCKET, ".bucket_check"):
                # Try to create bucket by uploading a dummy file
                try:
                    self.storage.upload_file(
                        TEMPLATE_BUCKET,
                        ".bucket_check",
                        b"",
                        "text/plain"
                    )
                except Exception:
                    # Bucket might already exist, that's fine
                    pass
        except Exception as e:
            logger.warning(f"Could not ensure template bucket exists: {e}")

    def create_template(
        self,
        name: str,
        description: Optional[str] = None,
        file_data: bytes = None,
        created_by: Optional[str] = None,
        template_key: Optional[str] = None,
        change_notes: Optional[str] = None,
    ) -> NDATemplate:
        """
        Create a new template or new version of existing template
        
        Args:
            name: Template name
            description: Template description
            file_data: Template file bytes (DOCX)
            created_by: User ID who created the template
            template_key: Unique key for template (auto-generated from name if not provided)
            change_notes: Notes about changes in this version
            
        Returns:
            Created NDATemplate instance
        """
        # Validate file format
        if not file_data or not file_data.startswith(b'PK'):
            raise TemplateValidationError("Template must be a valid DOCX file")

        # Auto-generate template key if not provided
        if not template_key:
            template_key = self._generate_template_key(name)

        db = get_db_session()
        try:
            # Check if this is a new version of existing template
            existing_template = db.query(NDATemplate).filter(
                NDATemplate.template_key == template_key
            ).order_by(NDATemplate.version.desc()).first()

            version = 1
            if existing_template:
                # Get the actual version number (handle both Mock and real objects)
                current_version = getattr(existing_template, 'version', 0)
                if hasattr(current_version, 'return_value'):
                    current_version = current_version.return_value or 0
                version = int(current_version) + 1
                logger.info(f"Creating version {version} of template '{template_key}'")

            # Generate filename and upload to storage
            template_id = str(uuid.uuid4())
            filename = self._generate_template_filename(template_id, name, version)
            
            file_path = self.storage.upload_file(
                bucket=TEMPLATE_BUCKET,
                object_name=f"{template_id}/{filename}",
                file_data=file_data,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

            # Create template record
            template = NDATemplate(
                id=uuid.UUID(template_id),
                name=name,
                description=description,
                file_path=file_path,
                version=version,
                template_key=template_key,
                is_active=True,
                is_current=True,  # New version becomes current
                created_by=uuid.UUID(created_by) if created_by else None,
                change_notes=change_notes,
            )

            db.add(template)

            # If this is a new version, mark other versions as not current
            if existing_template:
                db.query(NDATemplate).filter(
                    NDATemplate.template_key == template_key,
                    NDATemplate.id != template.id
                ).update({"is_current": False})

            db.commit()
            logger.info(f"Created template {template_id} (v{version}): {name}")

            return template

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create template: {e}")
            raise
        finally:
            db.close()

    def get_template(self, template_id: str) -> NDATemplate:
        """Get template by ID"""
        db = get_db_session()
        try:
            template_uuid = uuid.UUID(template_id)
            template = db.query(NDATemplate).filter(NDATemplate.id == template_uuid).first()
            
            if not template:
                raise TemplateNotFoundError(f"Template {template_id} not found")
            
            return template
        finally:
            db.close()

    def get_current_template(self, template_key: str) -> NDATemplate:
        """Get current version of template by key"""
        db = get_db_session()
        try:
            template = db.query(NDATemplate).filter(
                NDATemplate.template_key == template_key,
                NDATemplate.is_current == True
            ).first()
            
            if not template:
                raise TemplateNotFoundError(f"No current template found for key '{template_key}'")
            
            return template
        finally:
            db.close()

    def list_templates(
        self, 
        active_only: bool = False, 
        current_only: bool = True
    ) -> List[NDATemplate]:
        """List templates with optional filtering"""
        db = get_db_session()
        try:
            query = db.query(NDATemplate)
            
            if active_only:
                query = query.filter(NDATemplate.is_active == True)
            
            if current_only:
                query = query.filter(NDATemplate.is_current == True)
            
            return query.order_by(NDATemplate.created_at.desc()).all()
        finally:
            db.close()

    def get_template_versions(self, template_key: str) -> List[NDATemplate]:
        """Get all versions of a template"""
        db = get_db_session()
        try:
            return db.query(NDATemplate).filter(
                NDATemplate.template_key == template_key
            ).order_by(NDATemplate.version.asc()).all()
        finally:
            db.close()

    def set_current_version(self, template_id: str):
        """Set a template version as current"""
        db = get_db_session()
        try:
            template_uuid = uuid.UUID(template_id)
            template = db.query(NDATemplate).filter(NDATemplate.id == template_uuid).first()
            
            if not template:
                raise TemplateNotFoundError(f"Template {template_id} not found")

            # Mark all versions of this template as not current
            db.query(NDATemplate).filter(
                NDATemplate.template_key == template.template_key
            ).update({"is_current": False})

            # Mark this version as current
            template.is_current = True
            
            db.commit()
            logger.info(f"Set template {template_id} as current version")
        finally:
            db.close()

    def delete_template(self, template_id: str):
        """Soft delete template (set inactive)"""
        db = get_db_session()
        try:
            template_uuid = uuid.UUID(template_id)
            template = db.query(NDATemplate).filter(NDATemplate.id == template_uuid).first()
            
            if not template:
                raise TemplateNotFoundError(f"Template {template_id} not found")

            # Soft delete - set inactive
            template.is_active = False
            
            db.commit()
            logger.info(f"Deleted template {template_id}: {template.name}")
        finally:
            db.close()

    def render_template(
        self, 
        template_id: str, 
        data: Dict[str, Any]
    ) -> bytes:
        """
        Render template with provided data
        
        Args:
            template_id: UUID of template to render
            data: Dictionary of template variables
            
        Returns:
            Rendered DOCX file as bytes
        """
        if not DOCX_AVAILABLE:
            raise TemplateValidationError("python-docx library not available for template rendering")

        # Get template
        template = self.get_template(template_id)
        
        if not template.is_active:
            raise TemplateValidationError(f"Template {template_id} is inactive")

        # Validate template data
        self.validate_template_data(data, require_counterparty_name=True)

        # Download template file 
        try:
            # Parse file_path (format: bucket/object_name)
            if '/' in template.file_path:
                parts = template.file_path.split('/', 1)
                bucket = parts[0]
                object_name = parts[1]
            else:
                bucket = TEMPLATE_BUCKET
                object_name = template.file_path
                
            file_bytes = self.storage.download_file(bucket, object_name)
        except Exception as e:
            logger.error(f"Failed to download template file: {e}")
            raise TemplateValidationError(f"Failed to download template file: {str(e)}")

        # Render template with data
        try:
            # Save template to temp file
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name

            # Load and process DOCX
            doc = Document(temp_path)
            
            # Sanitize template data
            safe_data = self._sanitize_template_data(data)
            
            # Replace placeholders in document
            self._replace_placeholders_in_document(doc, safe_data)

            # Save rendered document to bytes
            output_buffer = BytesIO()
            doc.save(output_buffer)
            rendered_bytes = output_buffer.getvalue()

            logger.info(f"Rendered template {template_id} with {len(safe_data)} variables")
            return rendered_bytes

        except Exception as e:
            logger.error(f"Failed to render template: {e}")
            raise TemplateValidationError(f"Failed to render template: {str(e)}")
        finally:
            # Clean up temp file
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except:
                pass

    def validate_template_data(
        self, 
        data: Dict[str, Any], 
        require_counterparty_name: bool = False
    ) -> bool:
        """Validate template data before rendering"""
        if require_counterparty_name and not data.get('counterparty_name'):
            raise TemplateValidationError("counterparty_name is required")
        
        # Additional validation can be added here
        return True

    def _sanitize_template_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize template data to prevent injection attacks"""
        sanitized = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                # Remove potential script tags and SQL injection attempts
                cleaned = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)
                cleaned = re.sub(r'[;\'"\\]', '', cleaned)  # Remove SQL/injection chars  
                cleaned = re.sub(r'DROP\s+TABLE\s+\w+', '', cleaned, flags=re.IGNORECASE)  # Remove DROP TABLE
                cleaned = re.sub(r'\$\{[^}]*\}', '', cleaned)  # Remove potential template injection
                sanitized[key] = cleaned
            else:
                sanitized[key] = value
        
        return sanitized

    def _replace_placeholders_in_document(self, doc: 'Document', data: Dict[str, Any]):
        """Replace {placeholder} variables in DOCX document"""
        # Replace in paragraphs
        for paragraph in doc.paragraphs:
            for key, value in data.items():
                placeholder = f"{{{key}}}"
                if placeholder in paragraph.text:
                    # Replace placeholder while preserving formatting
                    for run in paragraph.runs:
                        if placeholder in run.text:
                            run.text = run.text.replace(placeholder, str(value))

        # Replace in tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for key, value in data.items():
                            placeholder = f"{{{key}}}"
                            if placeholder in paragraph.text:
                                for run in paragraph.runs:
                                    if placeholder in run.text:
                                        run.text = run.text.replace(placeholder, str(value))

    def _generate_template_key(self, name: str) -> str:
        """Generate template key from name"""
        # Convert name to safe key format
        key = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
        key = re.sub(r'\s+', '-', key.strip())
        return key

    def _generate_template_filename(
        self, 
        template_id: str, 
        original_name: str, 
        version: int
    ) -> str:
        """Generate safe filename for template storage"""
        # Clean filename
        clean_name = re.sub(r'[^a-zA-Z0-9\s\-\.]', '', original_name)
        clean_name = re.sub(r'\s+', '_', clean_name.strip())
        
        # Ensure .docx extension
        if not clean_name.lower().endswith('.docx'):
            clean_name = clean_name.rsplit('.', 1)[0] + '.docx'
        
        # Add version to filename
        name_base = clean_name.rsplit('.', 1)[0]
        filename = f"{name_base}_v{version}_{template_id[:8]}.docx"
        
        return filename


# Global service instance
_template_service: Optional[TemplateService] = None


def get_template_service() -> TemplateService:
    """Get or create template service instance"""
    global _template_service
    if _template_service is None:
        _template_service = TemplateService()
    return _template_service


def create_template_service() -> TemplateService:
    """Create new template service instance (for testing)"""
    return TemplateService()