"""
Camunda BPMN workflow service client

Handles:
- Process instance management (start, stop, query)
- External task processing (polling, completion)  
- User task management (assignment, completion)
- Process variable handling (input/output)
- Message event triggering (customer signature)
- BPMN deployment and management
- Workflow status synchronization
"""

import os
import logging
import asyncio
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from api.db import get_db_session
from api.db.schema import NDAWorkflowInstance

logger = logging.getLogger(__name__)


class CamundaConnectionError(Exception):
    """Raised when Camunda connection fails"""
    pass


class CamundaProcessError(Exception):
    """Raised when Camunda process operations fail"""
    pass


class CamundaTaskError(Exception):
    """Raised when Camunda task operations fail"""
    pass


class CamundaService:
    """Service for interacting with Camunda BPMN engine via REST API"""
    
    # NDA process constants
    NDA_PROCESS_KEY = 'nda_review_approval'
    CUSTOMER_SIGNED_MESSAGE = 'CustomerSignedMessage'

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.base_url = base_url or os.getenv("CAMUNDA_URL", "http://localhost:8080/engine-rest")
        self.username = username or os.getenv("CAMUNDA_USER", "demo")
        self.password = password or os.getenv("CAMUNDA_PASSWORD", "demo")
        
        # Clean base URL
        if self.base_url.endswith("/"):
            self.base_url = self.base_url[:-1]
        
        # Authentication tuple
        self.auth = (self.username, self.password)
        
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx library not available - required for Camunda integration")

    async def check_health(self) -> bool:
        """Check if Camunda is accessible"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/version",
                    auth=self.auth
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Camunda health check failed: {e}")
            return False

    async def start_process_instance(
        self,
        process_key: str,
        variables: Dict[str, Any],
        business_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Start a new process instance"""
        try:
            # Convert variables to Camunda format
            camunda_variables = self._convert_variables_to_camunda_format(variables)
            
            payload = {
                "variables": camunda_variables
            }
            
            if business_key:
                payload["businessKey"] = business_key

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/process-definition/key/{process_key}/start",
                    json=payload,
                    auth=self.auth
                )
                
                if response.status_code != 200:
                    raise CamundaProcessError(f"Failed to start process: {response.status_code} {response.text}")
                
                result = response.json()
                logger.info(f"Started process instance {result['id']} for {process_key}")
                return result
                
        except Exception as e:
            logger.error(f"Failed to start process instance: {e}")
            raise CamundaProcessError(f"Failed to start process: {str(e)}")

    async def get_process_instance(self, process_instance_id: str) -> Optional[Dict[str, Any]]:
        """Get process instance details"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/process-instance/{process_instance_id}",
                    auth=self.auth
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    return None
                else:
                    raise CamundaConnectionError(f"Failed to get process instance: {response.status_code}")
                    
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                return None
            logger.error(f"Failed to get process instance: {e}")
            raise CamundaConnectionError(f"Failed to get process instance: {str(e)}")

    async def get_process_variables(self, process_instance_id: str) -> Dict[str, Any]:
        """Get process instance variables"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/process-instance/{process_instance_id}/variables",
                    auth=self.auth
                )
                
                if response.status_code == 200:
                    camunda_variables = response.json()
                    return self._convert_variables_from_camunda_format(camunda_variables)
                else:
                    logger.warning(f"Failed to get variables: {response.status_code}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Failed to get process variables: {e}")
            return {}

    async def fetch_external_tasks(
        self, 
        topic_name: Optional[str] = None, 
        max_tasks: int = 10
    ) -> List[Dict[str, Any]]:
        """Fetch external tasks for processing"""
        try:
            payload = {
                "maxTasks": max_tasks,
                "topics": []
            }
            
            if topic_name:
                payload["topics"] = [{
                    "topicName": topic_name,
                    "lockDuration": 300000  # 5 minutes
                }]

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/external-task/fetchAndLock",
                    json=payload,
                    auth=self.auth
                )
                
                if response.status_code == 200:
                    tasks = response.json()
                    logger.info(f"Fetched {len(tasks)} external tasks")
                    return tasks
                else:
                    logger.warning(f"Failed to fetch external tasks: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Failed to fetch external tasks: {e}")
            return []

    async def complete_external_task(
        self,
        task_id: str,
        worker_id: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Complete an external task"""
        try:
            payload = {
                "workerId": worker_id
            }
            
            if variables:
                payload["variables"] = self._convert_variables_to_camunda_format(variables)

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/external-task/{task_id}/complete",
                    json=payload,
                    auth=self.auth
                )
                
                if response.status_code == 204:
                    logger.info(f"Completed external task {task_id}")
                    return True
                else:
                    raise CamundaTaskError(f"Failed to complete task: {response.status_code} {response.text}")
                    
        except Exception as e:
            logger.error(f"Failed to complete external task: {e}")
            raise CamundaTaskError(f"Failed to complete task: {str(e)}")

    async def get_user_tasks(
        self,
        process_instance_id: Optional[str] = None,
        assignee: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get user tasks"""
        try:
            params = {}
            if process_instance_id:
                params["processInstanceId"] = process_instance_id
            if assignee:
                params["assignee"] = assignee

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/task",
                    params=params,
                    auth=self.auth
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Failed to get user tasks: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Failed to get user tasks: {e}")
            return []

    async def send_message_event(
        self,
        message_name: str,
        business_key: Optional[str] = None,
        process_variables: Optional[Dict[str, Any]] = None,
        process_instance_id: Optional[str] = None
    ) -> bool:
        """Send message event to trigger intermediate catch events"""
        try:
            message_data = self._prepare_message_event_data(
                message_name, business_key, process_variables, process_instance_id
            )

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/message",
                    json=message_data,
                    auth=self.auth
                )
                
                if response.status_code == 204:
                    logger.info(f"Sent message event {message_name}")
                    return True
                else:
                    raise CamundaProcessError(f"Failed to send message: {response.status_code} {response.text}")
                    
        except Exception as e:
            logger.error(f"Failed to send message event: {e}")
            raise CamundaProcessError(f"Failed to send message: {str(e)}")

    async def deploy_bpmn_file(
        self, 
        filename: str, 
        bpmn_content: str
    ) -> str:
        """Deploy BPMN file to Camunda"""
        try:
            # Validate BPMN content
            if not self._validate_bpmn_content(bpmn_content):
                raise CamundaProcessError("Invalid BPMN content")

            # Prepare multipart form data
            files = {
                'deployment-name': (None, filename),
                'deployment-source': (None, 'NDA Tool'),
                filename: (filename, bpmn_content, 'application/xml')
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/deployment/create",
                    files=files,
                    auth=self.auth
                )
                
                if response.status_code == 200:
                    result = response.json()
                    deployment_id = result.get('id')
                    logger.info(f"Deployed BPMN file {filename} as deployment {deployment_id}")
                    return deployment_id
                else:
                    raise CamundaProcessError(f"Failed to deploy BPMN: {response.status_code} {response.text}")
                    
        except Exception as e:
            logger.error(f"Failed to deploy BPMN file: {e}")
            raise CamundaProcessError(f"Failed to deploy BPMN: {str(e)}")

    async def list_process_definitions(self) -> List[Dict[str, Any]]:
        """List deployed process definitions"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/process-definition",
                    auth=self.auth
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Failed to list process definitions: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Failed to list process definitions: {e}")
            return []

    def _convert_variables_to_camunda_format(self, variables: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Convert Python variables to Camunda variable format"""
        camunda_vars = {}
        
        for key, value in variables.items():
            if isinstance(value, bool):
                camunda_vars[key] = {"value": value, "type": "Boolean"}
            elif isinstance(value, int):
                camunda_vars[key] = {"value": value, "type": "Integer"}
            elif isinstance(value, float):
                camunda_vars[key] = {"value": value, "type": "Double"}
            elif isinstance(value, str):
                camunda_vars[key] = {"value": value, "type": "String"}
            else:
                # Default to string for other types
                camunda_vars[key] = {"value": str(value), "type": "String"}
        
        return camunda_vars

    def _convert_variables_from_camunda_format(self, camunda_variables: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Convert Camunda variables to Python format"""
        python_vars = {}
        
        for key, var_data in camunda_variables.items():
            value = var_data.get('value')
            var_type = var_data.get('type', 'String')
            
            # Convert based on type
            if var_type == 'Boolean':
                python_vars[key] = bool(value)
            elif var_type == 'Integer':
                python_vars[key] = int(value) if value is not None else None
            elif var_type == 'Double':
                python_vars[key] = float(value) if value is not None else None
            else:  # String or other
                python_vars[key] = value
        
        return python_vars

    def _prepare_message_event_data(
        self,
        message_name: str,
        business_key: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        process_instance_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Prepare message event data for Camunda API"""
        message_data = {
            "messageName": message_name
        }
        
        if business_key:
            message_data["businessKey"] = business_key
            
        if process_instance_id:
            message_data["processInstanceId"] = process_instance_id
            
        if variables:
            message_data["processVariables"] = self._convert_variables_to_camunda_format(variables)
        
        return message_data

    def _validate_bpmn_content(self, bpmn_content: str) -> bool:
        """Validate BPMN XML content"""
        try:
            # Parse XML to check if it's valid
            root = ET.fromstring(bpmn_content)
            
            # Check if it's BPMN (has bpmn namespace and process elements)
            if 'bpmn' not in root.tag.lower():
                return False
            
            # Look for process elements (try multiple namespaces)
            namespaces = [
                '{http://www.omg.org/spec/BPMN/20100524/MODEL}process',
                './/process'  # Without namespace
            ]
            
            processes = []
            for ns in namespaces:
                processes.extend(root.findall(ns))
            
            if not processes:
                return False
            
            return True
            
        except ET.ParseError:
            return False
        except Exception:
            return False

    def get_nda_process_key(self) -> str:
        """Get the process key for NDA workflow"""
        return self.NDA_PROCESS_KEY

    async def correlate_message(
        self,
        message_name: str,
        business_key: Optional[str] = None,
        process_instance_id: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Correlate message to resume waiting processes"""
        return await self.send_message_event(
            message_name=message_name,
            business_key=business_key,
            process_variables=variables,
            process_instance_id=process_instance_id
        )

    async def terminate_process_instance(self, process_instance_id: str) -> bool:
        """Terminate active process instance"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(
                    f"{self.base_url}/process-instance/{process_instance_id}",
                    auth=self.auth
                )
                
                if response.status_code == 204:
                    logger.info(f"Terminated process instance {process_instance_id}")
                    return True
                else:
                    logger.warning(f"Failed to terminate process: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to terminate process instance: {e}")
            return False

    def sync_workflow_status(self, workflow_instance_id: str):
        """Synchronize workflow status with Camunda"""
        db = get_db_session()
        try:
            import uuid
            workflow_uuid = uuid.UUID(workflow_instance_id)
            workflow_instance = db.query(NDAWorkflowInstance).filter(
                NDAWorkflowInstance.id == workflow_uuid
            ).first()
            
            if workflow_instance and workflow_instance.camunda_process_instance_id:
                # This would implement the sync logic
                # For now, just commit any pending changes
                db.commit()
                
        except Exception as e:
            logger.error(f"Failed to sync workflow status: {e}")
            db.rollback()
        finally:
            db.close()

    # Sync methods (for backward compatibility with existing API endpoints)
    def health_check(self) -> bool:
        """Sync health check (wrapper for async version)"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.check_health())
        except Exception:
            # If no event loop, create one
            return asyncio.run(self.check_health())

    def get_process_instance_sync(self, process_instance_id: str) -> Optional[Dict[str, Any]]:
        """Sync wrapper for get_process_instance"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.get_process_instance(process_instance_id))
        except Exception:
            return asyncio.run(self.get_process_instance(process_instance_id))

    def get_user_tasks_sync(
        self,
        process_instance_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Sync wrapper for get_user_tasks"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.get_user_tasks(process_instance_id))
        except Exception:
            return asyncio.run(self.get_user_tasks(process_instance_id))


# Global service instance
_camunda_service: Optional[CamundaService] = None


def get_camunda_service() -> CamundaService:
    """Get or create Camunda service instance (singleton)"""
    global _camunda_service
    if _camunda_service is None:
        _camunda_service = CamundaService()
    return _camunda_service


def create_camunda_service() -> CamundaService:
    """Create new Camunda service instance (for testing)"""
    return CamundaService()