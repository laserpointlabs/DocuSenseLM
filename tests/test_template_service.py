#!/usr/bin/env python3
"""
Test suite for NDA Template Management Service

Tests the template service that handles:
1. Template creation and versioning
2. DOCX template rendering with variables  
3. Template validation and storage
4. Template listing and management
5. Version management (current/active status)

Following TDD approach - comprehensive tests before implementation.
"""

import pytest
import uuid
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

# We'll create these as we implement
from api.services.template_service import TemplateService, TemplateNotFoundError, TemplateValidationError
from api.db.schema import NDATemplate, User
from api.services.storage_service import StorageService


class TestTemplateServiceCreation:
    """Test template creation and validation"""
    
    def test_template_service_initializes(self):
        """Test that TemplateService can be created"""
        # Mock storage service to avoid external dependencies
        with patch('api.services.template_service.get_storage_service') as mock_get_storage:
            mock_storage = Mock(spec=StorageService)
            mock_get_storage.return_value = mock_storage
            
            service = TemplateService()
            
            assert service is not None
            assert hasattr(service, 'storage')
            # Should ensure template bucket exists on init
            assert mock_storage.file_exists.called or mock_storage.upload_file.called

    @patch('api.services.template_service.get_storage_service')
    @patch('api.services.template_service.get_db_session')
    def test_create_new_template_success(self, mock_db_session, mock_get_storage):
        """Test creating a brand new template successfully"""
        # Setup mocks
        mock_storage = Mock(spec=StorageService)
        mock_get_storage.return_value = mock_storage
        mock_storage.upload_file.return_value = "nda-templates/template123/test_template.docx"
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        # Mock query for checking existing templates (should return None for new template)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        
        # Create valid DOCX file content (starts with PK)
        docx_content = b'PK\x03\x04' + b'fake_docx_content'
        
        service = TemplateService()
        
        # Test template creation
        user_uuid = str(uuid.uuid4())
        template = service.create_template(
            name="Test Template",
            description="A test template",
            file_data=docx_content,
            created_by=user_uuid,
            template_key="test-template"
        )
        
        # Verify template object created correctly
        assert template is not None
        assert template.name == "Test Template"
        assert template.description == "A test template"
        assert template.template_key == "test-template"
        assert template.version == 1  # First version
        assert template.is_active is True
        assert template.is_current is True
        assert template.created_by is not None
        
        # Verify storage service called
        mock_storage.upload_file.assert_called_once()
        upload_args = mock_storage.upload_file.call_args[1]
        assert upload_args['bucket'] == "nda-templates"
        assert docx_content in upload_args['file_data'] or upload_args['file_data'] == docx_content
        
        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch('api.services.template_service.get_storage_service')
    def test_create_template_invalid_file_format(self, mock_get_storage):
        """Test that non-DOCX files are rejected"""
        mock_storage = Mock(spec=StorageService)
        mock_get_storage.return_value = mock_storage
        
        service = TemplateService()
        
        # Test with non-DOCX content
        invalid_content = b'This is not a DOCX file'
        
        with pytest.raises(TemplateValidationError) as exc_info:
            service.create_template(
                name="Invalid Template",
                description="Invalid file",
                file_data=invalid_content
            )
        
        assert "DOCX" in str(exc_info.value) or "invalid" in str(exc_info.value).lower()

    @patch('api.services.template_service.get_storage_service')
    @patch('api.services.template_service.get_db_session')
    def test_create_template_version_increment(self, mock_db_session, mock_get_storage):
        """Test that template versions are incremented correctly"""
        # Setup mocks
        mock_storage = Mock(spec=StorageService)
        mock_get_storage.return_value = mock_storage
        mock_storage.upload_file.return_value = "nda-templates/template456/test_v2.docx"
        
        # Mock existing template with version 1
        existing_template = Mock()
        existing_template.version = 1
        existing_template.template_key = "test-template"
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        # Return existing template for max version query
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = existing_template
        
        docx_content = b'PK\x03\x04' + b'fake_docx_v2_content'
        
        service = TemplateService()
        
        # Create new version
        template = service.create_template(
            name="Test Template v2",
            description="Second version",
            file_data=docx_content,
            template_key="test-template",  # Same key = new version
            change_notes="Added new clauses"
        )
        
        # Should be version 2
        assert template.version == 2
        assert template.template_key == "test-template"
        assert template.is_current is True  # New version becomes current
        assert template.change_notes == "Added new clauses"


class TestTemplateServiceVersioning:
    """Test template versioning functionality"""
    
    @patch('api.services.template_service.get_db_session')
    def test_get_template_by_id(self, mock_db_session):
        """Test retrieving template by ID"""
        mock_template = Mock(spec=NDATemplate)
        mock_template.id = "template-uuid"
        mock_template.name = "Test Template"
        mock_template.is_active = True
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_template
        
        service = TemplateService()
        result = service.get_template("template-uuid")
        
        assert result == mock_template
        mock_db.query.assert_called()

    @patch('api.services.template_service.get_db_session')
    def test_get_template_not_found(self, mock_db_session):
        """Test retrieving non-existent template raises error"""
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = TemplateService()
        
        with pytest.raises(TemplateNotFoundError):
            service.get_template("nonexistent-uuid")

    @patch('api.services.template_service.get_db_session')
    def test_list_templates(self, mock_db_session):
        """Test listing templates with filtering"""
        # Create mock templates
        template1 = Mock(spec=NDATemplate)
        template1.template_key = "standard-nda" 
        template1.is_current = True
        template1.is_active = True
        
        template2 = Mock(spec=NDATemplate)
        template2.template_key = "mutual-nda"
        template2.is_current = True
        template2.is_active = False
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.order_by.return_value.all.return_value = [template1, template2]
        
        service = TemplateService()
        
        # Test list all templates
        templates = service.list_templates()
        assert len(templates) == 2
        
        # Test list only active templates
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [template1]
        active_templates = service.list_templates(active_only=True)
        assert len(active_templates) == 1

    @patch('api.services.template_service.get_db_session')
    def test_set_current_version(self, mock_db_session):
        """Test setting a template version as current"""
        # Mock existing templates
        old_current = Mock(spec=NDATemplate)
        old_current.id = "old-uuid"
        old_current.template_key = "test-template"
        old_current.version = 1
        old_current.is_current = True
        
        new_current = Mock(spec=NDATemplate)
        new_current.id = "new-uuid"
        new_current.template_key = "test-template"
        new_current.version = 2
        new_current.is_current = False
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = new_current
        mock_db.query.return_value.filter.return_value.all.return_value = [old_current, new_current]
        
        service = TemplateService()
        service.set_current_version("new-uuid")
        
        # Should update is_current flags
        assert old_current.is_current is False
        assert new_current.is_current is True
        mock_db.commit.assert_called()


class TestTemplateServiceRendering:
    """Test template rendering functionality"""
    
    @patch('api.services.template_service.DOCX_AVAILABLE', True)
    @patch('api.services.template_service.get_storage_service')
    @patch('api.services.template_service.get_db_session') 
    def test_render_template_success(self, mock_db_session, mock_get_storage):
        """Test successful template rendering with variables"""
        # Setup storage mock to return DOCX file
        mock_storage = Mock()
        mock_get_storage.return_value = mock_storage
        
        # Create fake DOCX content with placeholders
        fake_docx = b'PK\x03\x04fake_docx_with_{counterparty_name}_placeholder'
        mock_storage.download_file.return_value = fake_docx
        
        # Setup database mock
        mock_template = Mock(spec=NDATemplate)
        mock_template.file_path = "nda-templates/123/template.docx"
        mock_template.is_active = True
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_template
        
        # Mock DOCX processing with proper document structure
        with patch('api.services.template_service.Document') as mock_docx:
            mock_doc = Mock()
            mock_docx.return_value = mock_doc
            
            # Mock document structure
            mock_doc.paragraphs = []  # Empty list is iterable
            mock_doc.tables = []     # Empty list is iterable 
            
            # Mock save method to write fake DOCX data to BytesIO
            def mock_save(output_buffer):
                output_buffer.write(b'PK\x03\x04fake_rendered_docx_content')
            mock_doc.save = mock_save
            
            service = TemplateService()
            
            template_data = {
                'counterparty_name': 'Acme Corp',
                'effective_date': '2024-01-01',
                'term_months': '24'
            }
            
            template_uuid = str(uuid.uuid4())
            result = service.render_template(
                template_id=template_uuid,
                data=template_data
            )
            
            # Should return rendered DOCX bytes
            assert isinstance(result, bytes)
            assert len(result) > 0
            
            # Should have downloaded template file
            mock_storage.download_file.assert_called()
            
            # Should have processed DOCX document
            mock_docx.assert_called()

    @patch('api.services.template_service.DOCX_AVAILABLE', True)
    @patch('api.services.template_service.get_db_session')
    def test_render_template_not_found(self, mock_db_session):
        """Test rendering non-existent template raises error"""
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = TemplateService()
        
        nonexistent_uuid = str(uuid.uuid4())
        with pytest.raises(TemplateNotFoundError):
            service.render_template(
                template_id=nonexistent_uuid,
                data={'counterparty_name': 'Test Corp'}
            )

    @patch('api.services.template_service.DOCX_AVAILABLE', True)
    @patch('api.services.template_service.get_storage_service')
    @patch('api.services.template_service.get_db_session')
    def test_render_template_inactive_template(self, mock_db_session, mock_get_storage):
        """Test that inactive templates cannot be rendered"""
        mock_template = Mock(spec=NDATemplate)
        mock_template.is_active = False
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_template
        
        service = TemplateService()
        
        inactive_uuid = str(uuid.uuid4())
        with pytest.raises(TemplateValidationError) as exc_info:
            service.render_template(
                template_id=inactive_uuid,
                data={'counterparty_name': 'Test Corp'}
            )
        
        assert "inactive" in str(exc_info.value).lower()

    def test_validate_template_variables(self):
        """Test template variable validation"""
        service = TemplateService()
        
        # Test valid variables
        valid_data = {
            'counterparty_name': 'Acme Corp',
            'effective_date': '2024-01-01',
            'term_months': 24,
            'governing_law': 'California'
        }
        
        # Should not raise error
        result = service.validate_template_data(valid_data)
        assert result is True or result is None  # Depends on implementation
        
        # Test missing required variable
        invalid_data = {
            'effective_date': '2024-01-01'
            # Missing counterparty_name
        }
        
        with pytest.raises(TemplateValidationError) as exc_info:
            service.validate_template_data(invalid_data, require_counterparty_name=True)
        
        assert "counterparty_name" in str(exc_info.value)


class TestTemplateServiceVersioning:
    """Test template versioning functionality"""
    
    @patch('api.services.template_service.get_db_session')
    def test_get_template_versions(self, mock_db_session):
        """Test retrieving all versions of a template"""
        # Mock multiple template versions
        version1 = Mock(spec=NDATemplate)
        version1.template_key = "test-template"
        version1.version = 1
        version1.is_current = False
        
        version2 = Mock(spec=NDATemplate)
        version2.template_key = "test-template"
        version2.version = 2
        version2.is_current = True
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [version1, version2]
        
        service = TemplateService()
        versions = service.get_template_versions("test-template")
        
        assert len(versions) == 2
        assert versions[0].version <= versions[1].version  # Should be ordered

    @patch('api.services.template_service.get_db_session')
    def test_get_current_template_version(self, mock_db_session):
        """Test retrieving current version of a template"""
        current_template = Mock(spec=NDATemplate)
        current_template.template_key = "test-template"
        current_template.version = 2
        current_template.is_current = True
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = current_template
        
        service = TemplateService()
        result = service.get_current_template("test-template")
        
        assert result == current_template
        assert result.is_current is True

    @patch('api.services.template_service.get_storage_service')  
    @patch('api.services.template_service.get_db_session')
    def test_create_new_version_of_existing_template(self, mock_db_session, mock_get_storage):
        """Test creating new version of existing template"""
        # Mock storage
        mock_storage = Mock()
        mock_get_storage.return_value = mock_storage
        mock_storage.upload_file.return_value = "nda-templates/456/template_v2.docx"
        
        # Mock existing template (version 1) with real values
        existing_template = Mock(spec=NDATemplate)
        existing_template.version = 1  # Real integer, not mock
        existing_template.is_current = True
        existing_template.template_key = "test-template"
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        # Return existing template for max version check
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = existing_template
        # Return templates for updating is_current
        mock_db.query.return_value.filter.return_value.all.return_value = [existing_template]
        
        service = TemplateService()
        docx_content = b'PK\x03\x04' + b'fake_docx_v2_content'
        
        new_template = service.create_template(
            name="Test Template v2", 
            description="Second version",
            file_data=docx_content,
            template_key="test-template",  # Same key = new version
            change_notes="Added new clauses"
        )
        
        # Should be version 2
        assert new_template.version == 2
        assert new_template.template_key == "test-template"
        assert new_template.change_notes == "Added new clauses"
        
        # Old template should no longer be current (check if update was called)
        # The mock should have been updated by the service
        assert mock_db.query.return_value.filter.return_value.update.called


class TestTemplateServiceStorage:
    """Test template storage and retrieval"""
    
    @patch('api.services.template_service.get_storage_service')
    def test_template_bucket_initialization(self, mock_get_storage):
        """Test that template bucket is created/verified on service init"""
        mock_storage = Mock()
        mock_get_storage.return_value = mock_storage
        mock_storage.file_exists.return_value = False  # Bucket doesn't exist
        
        TemplateService()
        
        # Should try to create bucket by uploading check file
        assert mock_storage.upload_file.called

    @patch('api.services.template_service.get_storage_service')
    @patch('api.services.template_service.get_db_session')
    def test_delete_template(self, mock_db_session, mock_get_storage):
        """Test template deletion (soft delete - set inactive)"""
        # Use proper UUID for template ID
        template_uuid = str(uuid.uuid4())
        mock_template = Mock(spec=NDATemplate)
        mock_template.id = template_uuid
        mock_template.is_active = True
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_template
        
        service = TemplateService()
        service.delete_template(template_uuid)
        
        # Should set inactive, not hard delete
        assert mock_template.is_active is False
        mock_db.commit.assert_called()

    def test_template_file_naming_convention(self):
        """Test that template files are named consistently"""
        service = TemplateService()
        
        # Test file naming logic
        filename = service._generate_template_filename(
            template_id="abc123",
            original_name="My Template.docx",
            version=1
        )
        
        # Should be safe filename
        assert "/" not in filename
        assert "\\" not in filename
        assert filename.endswith(".docx")
        assert "abc123" in filename or "template" in filename.lower()


class TestTemplateServiceErrorHandling:
    """Test error handling and edge cases"""
    
    @patch('api.services.template_service.get_storage_service')
    def test_storage_failure_handling(self, mock_get_storage):
        """Test handling of storage service failures"""
        mock_storage = Mock()
        mock_get_storage.return_value = mock_storage
        mock_storage.upload_file.side_effect = Exception("Storage unavailable")
        
        service = TemplateService()
        docx_content = b'PK\x03\x04' + b'fake_docx_content'
        
        with pytest.raises(Exception) as exc_info:
            service.create_template(
                name="Test Template",
                file_data=docx_content
            )
        
        assert "storage" in str(exc_info.value).lower() or "unavailable" in str(exc_info.value)

    @patch('api.services.template_service.get_storage_service')
    @patch('api.services.template_service.get_db_session')
    def test_database_failure_rollback(self, mock_db_session, mock_get_storage):
        """Test that database failures trigger rollback"""
        mock_storage = Mock()
        mock_get_storage.return_value = mock_storage
        mock_storage.upload_file.return_value = "path/to/template.docx"
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.commit.side_effect = Exception("Database error")
        
        service = TemplateService()
        docx_content = b'PK\x03\x04' + b'fake_docx_content'
        
        with pytest.raises(Exception):
            service.create_template(
                name="Test Template",
                file_data=docx_content
            )
        
        # Should call rollback on failure
        mock_db.rollback.assert_called()

    def test_template_data_sanitization(self):
        """Test that template data is properly sanitized"""
        service = TemplateService()
        
        # Test data with potentially problematic content
        unsafe_data = {
            'counterparty_name': 'Acme Corp <script>alert("hack")</script>',
            'effective_date': '2024-01-01; DROP TABLE users;--',
            'malicious_field': '${system.exit(1)}'
        }
        
        # Should sanitize or validate the data
        result = service._sanitize_template_data(unsafe_data)
        
        # Should remove or escape dangerous content
        assert '<script>' not in result.get('counterparty_name', '')
        assert 'DROP TABLE' not in result.get('effective_date', '')
        assert 'system.exit' not in str(result)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
