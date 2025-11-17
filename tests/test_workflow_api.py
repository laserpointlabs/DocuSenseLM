#!/usr/bin/env python3
"""
Test suite for NDA Workflow API Endpoints

Tests the API layer that ties together all Phase 1 services:
1. Template API endpoints (upload, version, render)
2. NDA creation API (create from template + start workflow)
3. Workflow management API (start/stop workflows, task management)
4. Email API (send NDAs, track status)  
5. Status API (workflow progress tracking)
6. INTEGRATION TESTING (all services working together)
7. End-to-end workflow testing (complete NDA lifecycle)

This validates that Tasks 1.1-1.5 work together as a complete system.
"""

import pytest
import uuid
import json
from datetime import datetime, date
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from typing import List, Dict, Any

# We'll create these API endpoints as we implement
from api.main import app  # Main FastAPI app
from api.routers.workflow import router as workflow_router
from api.routers.templates import router as template_router

# Test client for API testing
client = TestClient(app)


class TestTemplateAPIEndpoints:
    """Test template management API endpoints"""
    
    def test_template_router_exists(self):
        """Test that template router is properly configured"""
        # Check if template router is included in main app
        assert any(route.path.startswith("/templates") for route in app.routes)

    @patch('api.routers.templates.get_template_service')
    def test_create_template_endpoint(self, mock_get_template_service):
        """Test POST /templates endpoint for creating templates"""
        # Mock template service
        mock_service = Mock()
        mock_get_template_service.return_value = mock_service
        
        mock_template = Mock()
        mock_template.id = str(uuid.uuid4())
        mock_template.name = "Test Template"
        mock_template.version = 1
        mock_template.is_active = True
        mock_service.create_template.return_value = mock_template
        
        # Mock authentication
        with patch('api.routers.templates.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.role = "admin"
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            # Test template creation
            response = client.post(
                "/templates",
                data={
                    "name": "Test Template",
                    "description": "A test template",
                    "template_key": "test-template"
                },
                files={"file": ("template.docx", b"PK\x03\x04fake_docx_content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            )
            
            # Should succeed for admin user
            assert response.status_code == 200 or response.status_code == 201
            mock_service.create_template.assert_called_once()

    @patch('api.routers.templates.get_template_service')
    def test_list_templates_endpoint(self, mock_get_template_service):
        """Test GET /templates endpoint for listing templates"""
        # Mock template service
        mock_service = Mock()
        mock_get_template_service.return_value = mock_service
        
        mock_templates = [
            Mock(id=str(uuid.uuid4()), name="Template 1", version=1),
            Mock(id=str(uuid.uuid4()), name="Template 2", version=1),
        ]
        mock_service.list_templates.return_value = mock_templates
        
        with patch('api.routers.templates.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.role = "admin"
            mock_auth.return_value = mock_user
            
            response = client.get("/templates")
            
            assert response.status_code == 200
            data = response.json()
            assert "templates" in data
            mock_service.list_templates.assert_called()

    @patch('api.routers.templates.get_template_service')
    def test_render_template_endpoint(self, mock_get_template_service):
        """Test POST /templates/{template_id}/render endpoint"""
        template_id = str(uuid.uuid4())
        
        # Mock template service
        mock_service = Mock()
        mock_get_template_service.return_value = mock_service
        mock_service.render_template.return_value = b"PK\x03\x04rendered_docx_content"
        
        with patch('api.routers.templates.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.role = "admin"
            mock_auth.return_value = mock_user
            
            render_data = {
                "data": {
                    "counterparty_name": "Acme Corp",
                    "effective_date": "2024-01-01",
                    "term_months": 24
                }
            }
            
            response = client.post(
                f"/templates/{template_id}/render",
                json=render_data
            )
            
            assert response.status_code == 200
            mock_service.render_template.assert_called_once_with(
                template_id=template_id,
                data=render_data["data"]
            )


class TestWorkflowAPIEndpoints:
    """Test workflow management API endpoints"""
    
    def test_workflow_router_exists(self):
        """Test that workflow router is properly configured"""
        # Check if workflow router is included in main app
        assert any(route.path.startswith("/workflow") for route in app.routes)

    @patch('api.routers.workflow.get_template_service')
    @patch('api.routers.workflow.get_camunda_service')
    def test_create_nda_endpoint(self, mock_get_camunda, mock_get_template_service):
        """Test POST /workflow/nda/create endpoint"""
        # Mock template service
        mock_template_service = Mock()
        mock_get_template_service.return_value = mock_template_service
        
        mock_template = Mock()
        mock_template.is_active = True
        mock_template_service.get_template.return_value = mock_template
        mock_template_service.render_template.return_value = b"%PDF-1.4\nfake_pdf_content"
        
        # Mock Camunda service for workflow start
        mock_camunda = Mock()
        mock_get_camunda.return_value = mock_camunda
        mock_camunda.start_process_instance.return_value = {"id": "process-123"}
        
        # Mock registry service
        with patch('api.routers.workflow.registry_service') as mock_registry:
            mock_nda_record = Mock()
            mock_nda_record.id = uuid.uuid4()
            mock_registry.upsert_record.return_value = mock_nda_record
            
            # Mock storage service
            with patch('api.routers.workflow.get_storage_service') as mock_storage:
                mock_storage.return_value.upload_file.return_value = "nda-raw/test.pdf"
                
                # Mock authentication
                with patch('api.routers.workflow.get_current_user') as mock_auth:
                    mock_user = Mock()
                    mock_user.role = "admin"
                    mock_user.id = uuid.uuid4()
                    mock_auth.return_value = mock_user
                    
                    # Test NDA creation
                    nda_data = {
                        "template_id": str(uuid.uuid4()),
                        "counterparty_name": "Test Corp",
                        "effective_date": "2024-01-01",
                        "term_months": 24,
                        "auto_start_workflow": True
                    }
                    
                    response = client.post("/workflow/nda/create", json=nda_data)
                    
                    # Should create NDA and start workflow
                    assert response.status_code == 200 or response.status_code == 201
                    mock_camunda.start_process_instance.assert_called_once()

    @patch('api.routers.workflow.get_camunda_service')
    def test_start_workflow_endpoint(self, mock_get_camunda):
        """Test POST /workflow/nda/{nda_id}/start-workflow endpoint"""
        nda_id = str(uuid.uuid4())
        
        # Mock Camunda service
        mock_camunda = Mock()
        mock_get_camunda.return_value = mock_camunda
        mock_camunda.start_process_instance.return_value = {"id": "process-123"}
        
        with patch('api.routers.workflow.get_db_session') as mock_db_session:
            # Mock NDA record
            mock_nda_record = Mock()
            mock_nda_record.id = uuid.UUID(nda_id)
            mock_nda_record.workflow_instance_id = None
            
            mock_db = Mock()
            mock_db_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = mock_nda_record
            
            with patch('api.routers.workflow.get_current_user') as mock_auth:
                mock_user = Mock()
                mock_user.role = "admin"
                mock_user.id = uuid.uuid4()
                mock_auth.return_value = mock_user
                
                response = client.post(
                    f"/workflow/nda/{nda_id}/start-workflow",
                    json={"reviewer_user_id": str(mock_user.id)}
                )
                
                # Should start workflow
                assert response.status_code == 200
                mock_camunda.start_process_instance.assert_called()

    @patch('api.routers.workflow.get_email_service')  
    def test_send_nda_email_endpoint(self, mock_get_email_service):
        """Test POST /workflow/nda/{nda_id}/send endpoint"""
        nda_id = str(uuid.uuid4())
        
        # Mock email service
        mock_email_service = Mock()
        mock_get_email_service.return_value = mock_email_service
        mock_email_service.send_email.return_value = "message-123"
        
        with patch('api.routers.workflow.get_db_session') as mock_db_session:
            with patch('api.routers.workflow.get_storage_service') as mock_storage:
                # Mock NDA record
                mock_nda_record = Mock()
                mock_nda_record.id = uuid.UUID(nda_id)
                mock_nda_record.counterparty_name = "Test Corp"
                mock_nda_record.file_uri = "nda-raw/test.pdf"
                mock_nda_record.status = "created"
                
                mock_db = Mock()
                mock_db_session.return_value = mock_db
                mock_db.query.return_value.filter.return_value.first.return_value = mock_nda_record
                
                # Mock file download
                mock_storage.return_value.download_file.return_value = b"%PDF-1.4\nfake_pdf"
                
                with patch('api.routers.workflow.get_current_user') as mock_auth:
                    mock_user = Mock()
                    mock_user.role = "admin"
                    mock_auth.return_value = mock_user
                    
                    email_data = {
                        "to_addresses": ["customer@example.com"],
                        "subject": "NDA for Review",
                        "message": "Please review the attached NDA."
                    }
                    
                    response = client.post(
                        f"/workflow/nda/{nda_id}/send",
                        json=email_data
                    )
                    
                    # Should send email successfully
                    assert response.status_code == 200
                    mock_email_service.send_email.assert_called()


class TestWorkflowStatusAPIEndpoints:
    """Test workflow status and monitoring API endpoints"""
    
    @patch('api.routers.workflow.get_db_session')
    def test_get_workflow_status_endpoint(self, mock_db_session):
        """Test GET /workflow/nda/{nda_id}/status endpoint"""
        nda_id = str(uuid.uuid4())
        
        # Mock NDA record with workflow
        mock_nda_record = Mock()
        mock_nda_record.id = uuid.UUID(nda_id)
        mock_nda_record.status = "in_review"
        mock_nda_record.workflow_instance_id = uuid.uuid4()
        
        mock_workflow = Mock()
        mock_workflow.current_status = "llm_review"
        mock_workflow.started_at = datetime.utcnow()
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_nda_record, mock_workflow]
        
        with patch('api.routers.workflow.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.role = "admin"
            mock_auth.return_value = mock_user
            
            response = client.get(f"/workflow/nda/{nda_id}/status")
            
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "workflow_status" in data

    @patch('api.routers.workflow.get_db_session')
    def test_list_workflows_endpoint(self, mock_db_session):
        """Test GET /workflow/workflows endpoint"""
        # Mock workflow instances
        mock_workflows = [
            Mock(
                id=uuid.uuid4(),
                nda_record_id=uuid.uuid4(),
                current_status="llm_review",
                started_at=datetime.utcnow()
            )
        ]
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = mock_workflows
        
        with patch('api.routers.workflow.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.role = "admin" 
            mock_auth.return_value = mock_user
            
            response = client.get("/workflow/workflows")
            
            assert response.status_code == 200
            data = response.json()
            assert "workflows" in data

    @patch('api.routers.workflow.get_camunda_service')
    def test_complete_task_endpoint(self, mock_get_camunda):
        """Test POST /workflow/task/{task_id}/complete endpoint"""
        task_id = "task-123"
        
        # Mock Camunda service
        mock_camunda = Mock()
        mock_get_camunda.return_value = mock_camunda
        mock_camunda.get_user_tasks.return_value = [{
            "id": task_id,
            "name": "Human Review",
            "assignee": str(uuid.uuid4())
        }]
        mock_camunda.complete_user_task.return_value = True
        
        with patch('api.routers.workflow.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.role = "admin"
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            task_data = {
                "approved": True,
                "comments": "Looks good to me"
            }
            
            response = client.post(
                f"/workflow/task/{task_id}/complete",
                json=task_data
            )
            
            # Should complete task successfully
            assert response.status_code == 200
            # Note: actual completion logic depends on implementation


class TestNDAWorkflowIntegrationAPI:
    """Test integration between all services via API"""
    
    @patch('api.routers.workflow.get_template_service')
    @patch('api.routers.workflow.get_camunda_service')
    @patch('api.routers.workflow.registry_service')
    @patch('api.routers.workflow.get_storage_service')
    def test_full_nda_creation_workflow_integration(
        self, 
        mock_storage, 
        mock_registry,
        mock_camunda, 
        mock_template_service
    ):
        """Test complete NDA creation → workflow start → status tracking"""
        # This tests integration of Tasks 1.1-1.5 via API layer
        
        template_id = str(uuid.uuid4())
        nda_id = uuid.uuid4()
        
        # Setup all service mocks (representing Tasks 1.1-1.5)
        
        # Task 1.3: Template service
        mock_template_service.return_value.get_template.return_value = Mock(is_active=True)
        mock_template_service.return_value.render_template.return_value = b"%PDF-1.4\nrendered_content"
        
        # Task 1.2 + 1.1: Database and schema (registry service)
        mock_nda_record = Mock()
        mock_nda_record.id = nda_id
        mock_nda_record.status = "created"  # Task 1.1: Correct initial status
        mock_registry.return_value.upsert_record.return_value = mock_nda_record
        
        # Task 1.5: Camunda workflow engine
        mock_camunda.return_value.start_process_instance.return_value = {"id": "process-123"}
        
        # Storage service (part of template/file handling)
        mock_storage.return_value.upload_file.return_value = "nda-raw/test.pdf"
        
        with patch('api.routers.workflow.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.role = "admin"
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            # Test complete NDA creation with workflow
            nda_data = {
                "template_id": template_id,
                "counterparty_name": "Integration Test Corp",
                "effective_date": "2024-01-01", 
                "term_months": 24,
                "auto_start_workflow": True,  # Test workflow integration
                "reviewer_user_id": str(mock_user.id)
            }
            
            response = client.post("/workflow/nda/create", json=nda_data)
            
            # Should succeed and integrate all services
            assert response.status_code == 200 or response.status_code == 201
            
            # Verify service integration (all tasks working together)
            mock_template_service.return_value.get_template.assert_called()  # Task 1.3
            mock_template_service.return_value.render_template.assert_called()  # Task 1.3
            mock_storage.return_value.upload_file.assert_called()  # File handling
            mock_registry.return_value.upsert_record.assert_called()  # Task 1.2 + 1.1
            mock_camunda.return_value.start_process_instance.assert_called()  # Task 1.5

    @patch('api.routers.workflow.get_email_service')
    @patch('api.routers.workflow.get_camunda_service') 
    def test_email_workflow_integration(self, mock_camunda, mock_email_service):
        """Test email sending → workflow message event integration"""
        nda_id = str(uuid.uuid4())
        
        # Mock email service (Task 1.4)
        mock_email_service.return_value.send_email.return_value = "message-123"
        
        # Mock Camunda for message correlation (Task 1.5)
        mock_camunda.return_value.correlate_message.return_value = True
        
        with patch('api.routers.workflow.get_db_session') as mock_db_session:
            # Mock NDA record
            mock_nda_record = Mock()
            mock_nda_record.id = uuid.UUID(nda_id)
            mock_nda_record.status = "pending_signature"  # Task 1.1: Correct status
            mock_nda_record.workflow_instance_id = uuid.uuid4()
            
            mock_workflow = Mock()
            mock_workflow.camunda_process_instance_id = "process-123"
            
            mock_db = Mock()
            mock_db_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.side_effect = [mock_nda_record, mock_workflow]
            
            with patch('api.routers.workflow.get_storage_service') as mock_storage:
                mock_storage.return_value.download_file.return_value = b"%PDF-content"
                
                with patch('api.routers.workflow.get_current_user') as mock_auth:
                    mock_user = Mock()
                    mock_user.role = "admin"
                    mock_auth.return_value = mock_user
                    
                    # Test customer signature trigger
                    response = client.post(
                        f"/workflow/workflow/{mock_nda_record.workflow_instance_id}/trigger-customer-signed"
                    )
                    
                    # Should trigger workflow message event
                    assert response.status_code == 200
                    # Verify Camunda message correlation called
                    assert mock_camunda.return_value.correlate_message.called or mock_camunda.return_value.send_message_event.called


class TestAPIErrorHandling:
    """Test API error handling and validation"""
    
    def test_unauthenticated_access_rejected(self):
        """Test that unauthenticated requests are rejected"""
        # Test without authentication
        response = client.post("/workflow/nda/create", json={})
        
        # Should require authentication
        assert response.status_code == 401 or response.status_code == 403

    def test_non_admin_access_restricted(self):
        """Test that non-admin users can't access admin endpoints"""
        with patch('api.routers.workflow.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.role = "user"  # Not admin
            mock_auth.return_value = mock_user
            
            response = client.post("/workflow/nda/create", json={
                "template_id": str(uuid.uuid4()),
                "counterparty_name": "Test Corp"
            })
            
            # Should be forbidden for non-admin
            assert response.status_code == 403

    def test_invalid_nda_id_handling(self):
        """Test handling of invalid NDA IDs"""
        invalid_id = "not-a-valid-uuid"
        
        with patch('api.routers.workflow.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.role = "admin"
            mock_auth.return_value = mock_user
            
            response = client.get(f"/workflow/nda/{invalid_id}/status")
            
            # Should handle invalid UUID gracefully
            assert response.status_code == 400 or response.status_code == 404

    @patch('api.routers.workflow.get_template_service')
    def test_missing_template_handling(self, mock_template_service):
        """Test handling when template doesn't exist"""
        mock_template_service.return_value.get_template.side_effect = Exception("Template not found")
        
        with patch('api.routers.workflow.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.role = "admin"
            mock_auth.return_value = mock_user
            
            nda_data = {
                "template_id": str(uuid.uuid4()),
                "counterparty_name": "Test Corp"
            }
            
            response = client.post("/workflow/nda/create", json=nda_data)
            
            # Should handle missing template gracefully
            assert response.status_code == 404 or response.status_code == 400


class TestAPIRequestValidation:
    """Test API request validation and data sanitization"""
    
    def test_nda_creation_request_validation(self):
        """Test validation of NDA creation requests"""
        with patch('api.routers.workflow.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.role = "admin"
            mock_auth.return_value = mock_user
            
            # Test missing required fields
            incomplete_data = {
                "template_id": str(uuid.uuid4())
                # Missing counterparty_name
            }
            
            response = client.post("/workflow/nda/create", json=incomplete_data)
            
            # Should validate required fields
            assert response.status_code == 400 or response.status_code == 422

    def test_email_address_validation_in_api(self):
        """Test email address validation in API endpoints"""
        nda_id = str(uuid.uuid4())
        
        with patch('api.routers.workflow.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.role = "admin"
            mock_auth.return_value = mock_user
            
            # Test invalid email addresses
            email_data = {
                "to_addresses": ["invalid-email-address"],
                "subject": "NDA for Review"
            }
            
            response = client.post(f"/workflow/nda/{nda_id}/send", json=email_data)
            
            # Should validate email addresses
            assert response.status_code == 400 or response.status_code == 422

    def test_input_sanitization_in_api(self):
        """Test that API inputs are properly sanitized"""
        with patch('api.routers.workflow.get_current_user') as mock_auth:
            mock_user = Mock()
            mock_user.role = "admin"
            mock_auth.return_value = mock_user
            
            # Test with potentially malicious input
            malicious_data = {
                "template_id": str(uuid.uuid4()),
                "counterparty_name": "Test Corp <script>alert('hack')</script>",
                "governing_law": "California; DROP TABLE users;--"
            }
            
            # Should handle malicious input safely (either reject or sanitize)
            # Implementation depends on validation strategy
            try:
                response = client.post("/workflow/nda/create", json=malicious_data)
                # If it succeeds, data should be sanitized
                # If it fails, should be due to validation, not injection
                assert response.status_code != 500  # Should not crash
            except Exception as e:
                # Should not crash due to injection
                assert "script" not in str(e).lower()


class TestAPIResponseFormats:
    """Test API response formats and data structures"""
    
    def test_api_response_consistency(self):
        """Test that API responses follow consistent format"""
        # Test endpoints should return consistent response structure
        # This will depend on the actual API implementation
        pass

    def test_error_response_format(self):
        """Test that error responses follow consistent format"""
        # Test with invalid endpoint
        response = client.get("/workflow/nonexistent/endpoint")
        
        assert response.status_code == 404
        # Should have consistent error format (depends on FastAPI configuration)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
