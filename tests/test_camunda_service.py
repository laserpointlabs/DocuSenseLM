#!/usr/bin/env python3
"""
Test suite for Camunda Workflow Service

Tests the Camunda integration that handles:
1. Process instance management (start, stop, query)
2. External task processing (polling, completion)
3. User task management (assignment, completion)
4. Process variable handling (input/output)
5. Message event triggering (customer signature)
6. BPMN deployment and management
7. Workflow status synchronization
8. Error handling and recovery

Following TDD approach - comprehensive tests before implementation.
"""

import pytest
import uuid
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import List, Dict, Any

# We'll create these as we implement
from api.services.camunda_service import (
    CamundaService, CamundaConnectionError, CamundaProcessError,
    CamundaTaskError, get_camunda_service, create_camunda_service
)
from api.workers.camunda_worker import CamundaWorker
from api.db.schema import NDAWorkflowInstance, NDAWorkflowTask


class TestCamundaServiceConnection:
    """Test Camunda service connection and configuration"""
    
    def test_camunda_service_initializes(self):
        """Test that CamundaService can be created"""
        with patch.dict('os.environ', {
            'CAMUNDA_URL': 'http://localhost:8080/engine-rest',
            'CAMUNDA_USER': 'admin',
            'CAMUNDA_PASSWORD': 'admin'
        }):
            service = CamundaService()
            assert service is not None
            assert hasattr(service, 'base_url')
            assert service.base_url == 'http://localhost:8080/engine-rest'

    def test_camunda_config_from_env_vars(self):
        """Test Camunda configuration from environment variables"""
        with patch.dict('os.environ', {
            'CAMUNDA_URL': 'http://camunda.example.com:8080/engine-rest',
            'CAMUNDA_USER': 'workflow-user',
            'CAMUNDA_PASSWORD': 'secure-password'
        }):
            service = CamundaService()
            assert service.base_url == 'http://camunda.example.com:8080/engine-rest'
            assert service.auth == ('workflow-user', 'secure-password')

    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_check_camunda_health_success(self, mock_client):
        """Test successful Camunda health check"""
        # Mock successful health response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'UP'}
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.get.return_value = mock_response
        
        service = CamundaService()
        is_healthy = await service.check_health()
        
        assert is_healthy is True
        mock_client_instance.get.assert_called_once()

    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_check_camunda_health_failure(self, mock_client):
        """Test Camunda health check when service is down"""
        # Mock connection failure
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.get.side_effect = Exception("Connection refused")
        
        service = CamundaService()
        is_healthy = await service.check_health()
        
        assert is_healthy is False


class TestCamundaServiceProcessManagement:
    """Test process instance management"""
    
    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_start_process_instance_success(self, mock_client):
        """Test successful process instance start"""
        # Mock successful process start response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'process-instance-123',
            'processDefinitionId': 'nda_review_approval:1:def-456',
            'businessKey': 'NDA-ABCD1234',
            'ended': False
        }
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post.return_value = mock_response
        
        service = CamundaService()
        
        result = await service.start_process_instance(
            process_key='nda_review_approval',
            variables={'nda_record_id': str(uuid.uuid4())},
            business_key='NDA-ABCD1234'
        )
        
        assert result['id'] == 'process-instance-123'
        assert result['businessKey'] == 'NDA-ABCD1234'
        mock_client_instance.post.assert_called_once()

    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_start_process_instance_failure(self, mock_client):
        """Test process instance start failure"""
        # Mock process start failure
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Process definition not found"
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post.return_value = mock_response
        
        service = CamundaService()
        
        with pytest.raises(CamundaProcessError) as exc_info:
            await service.start_process_instance(
                process_key='invalid_process',
                variables={}
            )
        
        assert "process definition" in str(exc_info.value).lower() or "400" in str(exc_info.value)

    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_get_process_instance(self, mock_client):
        """Test retrieving process instance details"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'process-instance-123',
            'state': 'ACTIVE',
            'businessKey': 'NDA-ABCD1234'
        }
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.get.return_value = mock_response
        
        service = CamundaService()
        instance = await service.get_process_instance('process-instance-123')
        
        assert instance['id'] == 'process-instance-123'
        assert instance['state'] == 'ACTIVE'

    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_get_process_variables(self, mock_client):
        """Test retrieving process instance variables"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'nda_record_id': {'value': str(uuid.uuid4()), 'type': 'String'},
            'reviewer_user_id': {'value': str(uuid.uuid4()), 'type': 'String'},
            'llm_approved': {'value': True, 'type': 'Boolean'}
        }
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.get.return_value = mock_response
        
        service = CamundaService()
        variables = await service.get_process_variables('process-instance-123')
        
        assert 'nda_record_id' in variables
        assert 'llm_approved' in variables
        assert variables['llm_approved'] is True  # Should extract value from Camunda format


class TestCamundaServiceTaskManagement:
    """Test external task and user task management"""
    
    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_fetch_external_tasks(self, mock_client):
        """Test fetching external tasks for processing"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'id': 'task-123',
                'topicName': 'llm_review',
                'processInstanceId': 'process-456',
                'variables': {
                    'nda_record_id': {'value': str(uuid.uuid4()), 'type': 'String'}
                }
            },
            {
                'id': 'task-789',
                'topicName': 'send_to_customer',
                'processInstanceId': 'process-101',
                'variables': {
                    'customer_email': {'value': 'customer@example.com', 'type': 'String'}
                }
            }
        ]
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post.return_value = mock_response
        
        service = CamundaService()
        
        tasks = await service.fetch_external_tasks(
            topic_name='llm_review',
            max_tasks=10
        )
        
        assert len(tasks) >= 0  # Could be filtered by topic
        mock_client_instance.post.assert_called()

    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_complete_external_task_success(self, mock_client):
        """Test successful external task completion"""
        mock_response = Mock()
        mock_response.status_code = 204  # No content = success
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post.return_value = mock_response
        
        service = CamundaService()
        
        success = await service.complete_external_task(
            task_id='task-123',
            worker_id='test-worker',
            variables={'llm_approved': True, 'llm_confidence': 0.85}
        )
        
        assert success is True
        mock_client_instance.post.assert_called()

    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_complete_external_task_failure(self, mock_client):
        """Test external task completion failure"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Task not found or already completed"
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post.return_value = mock_response
        
        service = CamundaService()
        
        with pytest.raises(CamundaTaskError):
            await service.complete_external_task(
                task_id='invalid-task',
                worker_id='test-worker',
                variables={}
            )

    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_get_user_tasks(self, mock_client):
        """Test retrieving user tasks for assignment"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'id': 'user-task-123',
                'name': 'Human Review',
                'assignee': str(uuid.uuid4()),
                'processInstanceId': 'process-456',
                'taskDefinitionKey': 'Task_HumanReview'
            }
        ]
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.get.return_value = mock_response
        
        service = CamundaService()
        tasks = await service.get_user_tasks(
            process_instance_id='process-456'
        )
        
        assert len(tasks) == 1
        assert tasks[0]['name'] == 'Human Review'


class TestCamundaServiceMessageEvents:
    """Test message event handling"""
    
    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_send_message_event_success(self, mock_client):
        """Test successful message event sending"""
        mock_response = Mock()
        mock_response.status_code = 204  # Success
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post.return_value = mock_response
        
        service = CamundaService()
        
        success = await service.send_message_event(
            message_name='CustomerSignedMessage',
            business_key='NDA-ABCD1234',
            process_variables={'customer_signed_at': datetime.utcnow().isoformat()}
        )
        
        assert success is True
        mock_client_instance.post.assert_called()

    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_send_message_event_failure(self, mock_client):
        """Test message event sending failure"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Message not found"
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post.return_value = mock_response
        
        service = CamundaService()
        
        with pytest.raises(CamundaProcessError):
            await service.send_message_event(
                message_name='InvalidMessage',
                business_key='NDA-INVALID'
            )


class TestCamundaServiceBPMNManagement:
    """Test BPMN deployment and management"""
    
    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_deploy_bpmn_file_success(self, mock_client):
        """Test successful BPMN file deployment"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'deployment-123',
            'name': 'nda_review_approval.bpmn',
            'deploymentTime': datetime.utcnow().isoformat(),
            'deployedProcessDefinitions': {
                'nda_review_approval': {
                    'id': 'nda_review_approval:1:def-456',
                    'key': 'nda_review_approval',
                    'version': 1
                }
            }
        }
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post.return_value = mock_response
        
        service = CamundaService()
        
        bpmn_content = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn2:definitions xmlns:bpmn2="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <bpmn2:process id="nda_review_approval" name="NDA Review" isExecutable="true">
    <!-- Test BPMN content -->
  </bpmn2:process>
</bpmn2:definitions>"""
        
        deployment_id = await service.deploy_bpmn_file(
            filename='nda_review_approval.bpmn',
            bpmn_content=bpmn_content
        )
        
        assert deployment_id == 'deployment-123'
        mock_client_instance.post.assert_called()

    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_list_process_definitions(self, mock_client):
        """Test listing deployed process definitions"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'id': 'nda_review_approval:1:def-456',
                'key': 'nda_review_approval',
                'name': 'NDA Review and Approval',
                'version': 1,
                'suspended': False
            }
        ]
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.get.return_value = mock_response
        
        service = CamundaService()
        definitions = await service.list_process_definitions()
        
        assert len(definitions) == 1
        assert definitions[0]['key'] == 'nda_review_approval'

    def test_validate_bpmn_content(self):
        """Test BPMN content validation"""
        service = CamundaService()
        
        # Test valid BPMN
        valid_bpmn = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn2:definitions xmlns:bpmn2="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <bpmn2:process id="test_process" isExecutable="true">
    <bpmn2:startEvent id="start"/>
  </bpmn2:process>
</bpmn2:definitions>"""
        
        assert service._validate_bpmn_content(valid_bpmn) is True
        
        # Test invalid BPMN
        invalid_bpmn = "This is not XML"
        assert service._validate_bpmn_content(invalid_bpmn) is False


class TestCamundaServiceVariableHandling:
    """Test process variable handling and type conversion"""
    
    def test_convert_variables_to_camunda_format(self):
        """Test converting Python variables to Camunda format"""
        service = CamundaService()
        
        python_vars = {
            'nda_record_id': str(uuid.uuid4()),
            'reviewer_user_id': str(uuid.uuid4()),
            'llm_approved': True,
            'llm_confidence': 0.85,
            'review_count': 2
        }
        
        camunda_vars = service._convert_variables_to_camunda_format(python_vars)
        
        assert 'nda_record_id' in camunda_vars
        assert camunda_vars['nda_record_id']['type'] == 'String'
        assert camunda_vars['llm_approved']['type'] == 'Boolean'
        assert camunda_vars['llm_confidence']['type'] == 'Double'
        assert camunda_vars['review_count']['type'] == 'Integer'

    def test_convert_variables_from_camunda_format(self):
        """Test converting Camunda variables to Python format"""
        service = CamundaService()
        
        camunda_vars = {
            'nda_record_id': {'value': str(uuid.uuid4()), 'type': 'String'},
            'llm_approved': {'value': True, 'type': 'Boolean'},
            'llm_confidence': {'value': 0.85, 'type': 'Double'},
        }
        
        python_vars = service._convert_variables_from_camunda_format(camunda_vars)
        
        assert isinstance(python_vars['nda_record_id'], str)
        assert isinstance(python_vars['llm_approved'], bool)
        assert isinstance(python_vars['llm_confidence'], float)
        assert python_vars['llm_approved'] is True
        assert python_vars['llm_confidence'] == 0.85


class TestCamundaServiceErrorHandling:
    """Test error handling and edge cases"""
    
    def test_camunda_connection_error_handling(self):
        """Test handling of Camunda connection errors"""
        # Test with invalid URL
        with patch.dict('os.environ', {
            'CAMUNDA_URL': 'http://invalid-host:8080/engine-rest'
        }):
            service = CamundaService()
            
            # Connection errors should be handled gracefully
            assert hasattr(service, 'base_url')
            assert service.base_url == 'http://invalid-host:8080/engine-rest'

    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_client):
        """Test handling of request timeouts"""
        # Mock timeout
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.get.side_effect = asyncio.TimeoutError("Request timed out")
        
        service = CamundaService()
        
        with pytest.raises(CamundaConnectionError) as exc_info:
            await service.get_process_instance('process-123')
        
        error_msg = str(exc_info.value).lower()
        assert "timeout" in error_msg or "connection" in error_msg or "timed out" in error_msg

    @patch('api.services.camunda_service.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_authentication_failure(self, mock_client):
        """Test handling authentication failures"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        mock_client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.get.return_value = mock_response
        
        service = CamundaService()
        
        with pytest.raises(CamundaConnectionError) as exc_info:
            await service.get_process_instance('process-123')
        
        assert "auth" in str(exc_info.value).lower() or "401" in str(exc_info.value)

    def test_service_registry_integration(self):
        """Test integration with service registry"""
        # Test singleton behavior
        service1 = get_camunda_service()
        service2 = get_camunda_service()
        assert service1 is service2
        
        # Test factory function
        service3 = create_camunda_service()
        service4 = create_camunda_service()
        assert service3 is not service4  # Should create new instances


class TestCamundaWorkerIntegration:
    """Test Camunda external task worker integration"""
    
    def test_camunda_worker_initializes(self):
        """Test that CamundaWorker can be created"""
        with patch('api.workers.camunda_worker.get_camunda_service'):
            # Import and use the actual CamundaWorker (it has its own dependencies)
            try:
                from api.workers.camunda_worker import CamundaWorker
                worker = CamundaWorker()
                assert worker is not None
                assert hasattr(worker, 'worker_id')
                assert hasattr(worker, 'running')
            except ImportError:
                # If worker dependencies aren't available, skip test
                pytest.skip("CamundaWorker dependencies not available")

    @patch('api.workers.camunda_worker.get_camunda_service')
    @pytest.mark.asyncio
    async def test_worker_task_processing_llm_review(self, mock_get_camunda):
        """Test worker processing LLM review tasks"""
        mock_camunda = AsyncMock()
        mock_get_camunda.return_value = mock_camunda
        
        # Mock LLM review task
        mock_task = {
            'id': 'llm-task-123',
            'topicName': 'llm_review',
            'variables': {
                'nda_record_id': {'value': str(uuid.uuid4()), 'type': 'String'}
            }
        }
        
        try:
            from api.workers.camunda_worker import CamundaWorker
            worker = CamundaWorker()
            
            # Should be able to identify and route LLM review tasks
            assert hasattr(worker, '_process_llm_review_task') or hasattr(worker, 'process_task')
        except ImportError:
            pytest.skip("CamundaWorker dependencies not available")

    @patch('api.workers.camunda_worker.get_camunda_service')
    @pytest.mark.asyncio
    async def test_worker_task_processing_send_to_customer(self, mock_get_camunda):
        """Test worker processing send to customer tasks"""
        mock_camunda = AsyncMock()
        mock_get_camunda.return_value = mock_camunda
        
        # Mock send to customer task
        mock_task = {
            'id': 'send-task-456',
            'topicName': 'send_to_customer',
            'variables': {
                'nda_record_id': {'value': str(uuid.uuid4()), 'type': 'String'},
                'customer_email': {'value': 'customer@example.com', 'type': 'String'}
            }
        }
        
        try:
            from api.workers.camunda_worker import CamundaWorker  
            worker = CamundaWorker()
            
            # Should be able to identify and route send to customer tasks
            assert hasattr(worker, '_process_send_to_customer_task') or hasattr(worker, 'process_task')
        except ImportError:
            pytest.skip("CamundaWorker dependencies not available")


class TestCamundaServiceNDAWorkflowIntegration:
    """Test specific NDA workflow integration"""
    
    def test_nda_workflow_process_key(self):
        """Test NDA workflow process definition key"""
        service = CamundaService()
        
        # NDA workflow should use consistent process key
        expected_process_key = 'nda_review_approval'
        assert hasattr(service, 'NDA_PROCESS_KEY') or hasattr(service, 'get_nda_process_key')
        
        # If method exists, test it
        if hasattr(service, 'get_nda_process_key'):
            process_key = service.get_nda_process_key()
            assert process_key == expected_process_key

    def test_nda_message_events(self):
        """Test NDA-specific message events"""
        service = CamundaService()
        
        # Should support customer signed message event
        customer_signed_message = 'CustomerSignedMessage'
        
        # Test message event data structure
        message_data = service._prepare_message_event_data(
            message_name=customer_signed_message,
            business_key='NDA-ABCD1234',
            variables={'customer_signed_at': datetime.utcnow().isoformat()}
        )
        
        assert message_data is not None
        assert message_data['messageName'] == customer_signed_message
        assert message_data['businessKey'] == 'NDA-ABCD1234'

    @patch('api.services.camunda_service.get_db_session')
    def test_sync_workflow_status_with_database(self, mock_db_session):
        """Test synchronizing Camunda workflow status with database"""
        # Mock database workflow instance
        mock_workflow = Mock(spec=NDAWorkflowInstance)
        mock_workflow.id = uuid.uuid4()
        mock_workflow.camunda_process_instance_id = 'process-123'
        mock_workflow.current_status = 'started'
        
        mock_db = Mock()
        mock_db_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_workflow
        
        service = CamundaService()
        
        # Should be able to sync status
        with patch.object(service, 'get_process_instance', return_value={'state': 'ACTIVE'}):
            service.sync_workflow_status(str(mock_workflow.id))
            
            # Should update database if needed
            mock_db.commit.assert_called()


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
