"""
Camunda BPMN workflow service client
Handles communication with Camunda REST API
"""
import os
import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class CamundaService:
    """Service for interacting with Camunda BPMN engine via REST API"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.base_url = base_url or os.getenv("CAMUNDA_URL", "http://camunda:8080")
        self.username = username or os.getenv("CAMUNDA_USERNAME", "demo")
        self.password = password or os.getenv("CAMUNDA_PASSWORD", "demo")
        
        # Ensure base_url doesn't end with /
        if self.base_url.endswith("/"):
            self.base_url = self.base_url[:-1]
        
        self.engine_rest_url = f"{self.base_url}/engine-rest"
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)

    def start_process_instance(
        self,
        process_key: str,
        variables: Optional[Dict[str, Any]] = None,
        business_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start a new process instance
        
        Args:
            process_key: BPMN process definition key (e.g., 'nda_review_approval')
            variables: Process variables to set
            business_key: Business key for the process instance
            
        Returns:
            Process instance data including id
        """
        url = f"{self.engine_rest_url}/process-definition/key/{process_key}/start"
        
        payload = {}
        if variables:
            # Convert variables to Camunda format
            payload["variables"] = self._format_variables(variables)
        if business_key:
            payload["businessKey"] = business_key
        
        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Started process instance: {result.get('id')} for process: {process_key}")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to start process instance: {e}")
            raise

    def get_process_instance(self, process_instance_id: str) -> Optional[Dict[str, Any]]:
        """Get process instance details"""
        url = f"{self.engine_rest_url}/process-instance/{process_instance_id}"
        
        try:
            response = self.session.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get process instance: {e}")
            return None

    def get_process_instances(
        self,
        business_key: Optional[str] = None,
        process_definition_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get process instances with optional filters"""
        url = f"{self.engine_rest_url}/process-instance"
        
        params = {}
        if business_key:
            params["businessKey"] = business_key
        if process_definition_key:
            params["processDefinitionKey"] = process_definition_key
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get process instances: {e}")
            return []

    def get_external_tasks(
        self,
        topic: Optional[str] = None,
        process_instance_id: Optional[str] = None,
        locked: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get external tasks
        
        Args:
            topic: Filter by topic name
            process_instance_id: Filter by process instance ID
            locked: Include locked tasks (default: False, only unlocked tasks)
        """
        url = f"{self.engine_rest_url}/external-task"
        
        params = {}
        if topic:
            params["topicName"] = topic
        if process_instance_id:
            params["processInstanceId"] = process_instance_id
        if not locked:
            params["notLocked"] = "true"
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get external tasks: {e}")
            return []

    def fetch_and_lock_external_task(
        self,
        topic: str,
        worker_id: str,
        max_tasks: int = 1,
        lock_duration: int = 60000,  # milliseconds
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch and lock an external task
        
        Args:
            topic: Topic name to fetch from
            worker_id: Worker identifier
            max_tasks: Maximum number of tasks to fetch
            lock_duration: Lock duration in milliseconds
            
        Returns:
            Task data if available, None otherwise
        """
        url = f"{self.engine_rest_url}/external-task/fetchAndLock"
        
        payload = {
            "workerId": worker_id,
            "maxTasks": max_tasks,
            "topics": [
                {
                    "topicName": topic,
                    "lockDuration": lock_duration,
                }
            ],
        }
        
        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            tasks = response.json()
            if tasks:
                return tasks[0]  # Return first task
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch external task: {e}")
            return None

    def complete_external_task(
        self,
        task_id: str,
        worker_id: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Complete an external task
        
        Args:
            task_id: External task ID
            worker_id: Worker identifier
            variables: Variables to set on completion
            
        Returns:
            True if successful
        """
        url = f"{self.engine_rest_url}/external-task/{task_id}/complete"
        
        payload = {"workerId": worker_id}
        if variables:
            payload["variables"] = self._format_variables(variables)
        
        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"Completed external task: {task_id}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to complete external task: {e}")
            return False

    def get_user_tasks(
        self,
        process_instance_id: Optional[str] = None,
        assignee: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get user tasks (active tasks only)"""
        url = f"{self.engine_rest_url}/task"
        
        params = {}
        if process_instance_id:
            params["processInstanceId"] = process_instance_id
        if assignee:
            params["assignee"] = assignee
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get user tasks: {e}")
            return []

    def get_historic_tasks(
        self,
        process_instance_id: Optional[str] = None,
        finished: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get historic tasks (completed tasks)"""
        url = f"{self.engine_rest_url}/history/task"
        
        params = {}
        if process_instance_id:
            params["processInstanceId"] = process_instance_id
        if finished:
            params["finished"] = "true"
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get historic tasks: {e}")
            return []

    def get_process_instance_variables(
        self,
        process_instance_id: str,
    ) -> Dict[str, Any]:
        """Get process instance variables (works for both active and completed instances)"""
        # First try active process instance API
        url = f"{self.engine_rest_url}/process-instance/{process_instance_id}/variables"
        
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                result = response.json()
                # Active API returns dict with variable names as keys
                # Each value is a dict with "value" and "type" keys
                if isinstance(result, dict):
                    return {k: v.get("value") if isinstance(v, dict) else v for k, v in result.items()}
                return result
        except requests.exceptions.RequestException:
            pass  # Try history API
        
        # Try history API for completed instances
        try:
            url = f"{self.engine_rest_url}/history/variable-instance"
            response = self.session.get(url, params={"processInstanceId": process_instance_id})
            if response.status_code == 200:
                result = response.json()
                # History API returns list of variable instances
                if isinstance(result, list):
                    variables = {}
                    for v in result:
                        var_name = v.get("name")
                        var_value = v.get("value")
                        variables[var_name] = var_value
                    return variables
                return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get process instance variables from history: {e}")
        
        return {}

    def get_process_instance_history(
        self,
        process_instance_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get process instance from history (for completed instances)"""
        url = f"{self.engine_rest_url}/history/process-instance/{process_instance_id}"
        
        try:
            response = self.session.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get process instance history: {e}")
            return None

    def get_activity_instances(
        self,
        process_instance_id: str,
    ) -> List[Dict[str, Any]]:
        """Get activity instances (execution path) for a process instance"""
        url = f"{self.engine_rest_url}/process-instance/{process_instance_id}/activity-instances"
        
        try:
            response = self.session.get(url)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            return response.json().get("childActivityInstances", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get activity instances: {e}")
            return []

    def get_incidents(
        self,
        process_instance_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get incidents (errors) for a process instance"""
        url = f"{self.engine_rest_url}/incident"
        
        params = {}
        if process_instance_id:
            params["processInstanceId"] = process_instance_id
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get incidents: {e}")
            return []

    def complete_user_task(
        self,
        task_id: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Complete a user task"""
        url = f"{self.engine_rest_url}/task/{task_id}/complete"
        
        payload = {}
        if variables:
            payload["variables"] = self._format_variables(variables)
        
        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"Completed user task: {task_id}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to complete user task: {e}")
            return False

    def set_task_variable(
        self,
        task_id: str,
        variable_name: str,
        value: Any,
    ) -> bool:
        """Set a variable on a task"""
        url = f"{self.engine_rest_url}/task/{task_id}/variables/{variable_name}"
        
        payload = {"value": value, "type": self._get_variable_type(value)}
        
        try:
            response = self.session.put(url, json=payload)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to set task variable: {e}")
            return False

    def set_process_variable(
        self,
        process_instance_id: str,
        variable_name: str,
        value: Any,
    ) -> bool:
        """Set a variable on a process instance"""
        url = f"{self.engine_rest_url}/process-instance/{process_instance_id}/variables/{variable_name}"
        
        payload = {"value": value, "type": self._get_variable_type(value)}
        
        try:
            response = self.session.put(url, json=payload)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to set process variable: {e}")
            return False

    def correlate_message(
        self,
        message_name: str,
        process_instance_id: Optional[str] = None,
        business_key: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Correlate a message to a process instance (for message events)"""
        url = f"{self.engine_rest_url}/message"
        
        payload = {"messageName": message_name}
        
        if process_instance_id:
            payload["processInstanceId"] = process_instance_id
        if business_key:
            payload["businessKey"] = business_key
        if variables:
            payload["processVariables"] = self._format_variables(variables)
        
        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"Correlated message '{message_name}' to process instance {process_instance_id}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to correlate message: {e}")
            return False

    def _format_variables(self, variables: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Format variables for Camunda API"""
        formatted = {}
        for key, value in variables.items():
            formatted[key] = {
                "value": value,
                "type": self._get_variable_type(value),
            }
        return formatted

    def _get_variable_type(self, value: Any) -> str:
        """Get Camunda variable type from Python value"""
        if isinstance(value, bool):
            return "Boolean"
        elif isinstance(value, int):
            return "Integer"
        elif isinstance(value, float):
            return "Double"
        elif isinstance(value, str):
            return "String"
        elif isinstance(value, (list, dict)):
            return "Json"
        else:
            return "String"

    def deploy_process_definition(
        self,
        bpmn_file_path: str,
        deployment_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Deploy a BPMN process definition to Camunda
        
        Args:
            bpmn_file_path: Path to the BPMN file
            deployment_name: Optional deployment name (defaults to filename)
            
        Returns:
            Deployment data if successful, None otherwise
        """
        import os
        from pathlib import Path
        
        if not os.path.exists(bpmn_file_path):
            logger.error(f"BPMN file not found: {bpmn_file_path}")
            return None
        
        if deployment_name is None:
            deployment_name = Path(bpmn_file_path).stem
        
        url = f"{self.engine_rest_url}/deployment/create"
        
        try:
            with open(bpmn_file_path, 'rb') as f:
                files = {
                    'deployment-name': (None, deployment_name),
                    'deployment-source': (None, 'api'),
                    'deploy-changed-only': (None, 'true'),
                    Path(bpmn_file_path).name: (Path(bpmn_file_path).name, f.read(), 'application/xml'),
                }
                response = self.session.post(url, files=files)
                response.raise_for_status()
                result = response.json()
                logger.info(f"Deployed BPMN process definition: {deployment_name}")
                return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to deploy BPMN file: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Error deploying BPMN file: {e}")
            return None

    def get_process_definition_key(self, process_key: str) -> Optional[Dict[str, Any]]:
        """
        Get process definition by key to check if it's deployed
        
        Args:
            process_key: Process definition key (e.g., 'nda_review_approval')
            
        Returns:
            Process definition data if found, None otherwise
        """
        url = f"{self.engine_rest_url}/process-definition/key/{process_key}"
        
        try:
            response = self.session.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.debug(f"Process definition not found: {process_key}")
            return None

    def delete_process_instance(
        self,
        process_instance_id: str,
        skip_custom_listeners: bool = False,
        skip_io_mappings: bool = False,
    ) -> bool:
        """
        Delete a process instance
        
        Args:
            process_instance_id: Process instance ID to delete
            skip_custom_listeners: Skip custom listeners during deletion
            skip_io_mappings: Skip IO mappings during deletion
            
        Returns:
            True if successful
        """
        url = f"{self.engine_rest_url}/process-instance/{process_instance_id}"
        
        params = {}
        if skip_custom_listeners:
            params["skipCustomListeners"] = "true"
        if skip_io_mappings:
            params["skipIoMappings"] = "true"
        
        try:
            response = self.session.delete(url, params=params)
            if response.status_code == 404:
                logger.warning(f"Process instance {process_instance_id} not found (may already be deleted)")
                return True  # Consider it successful if already gone
            response.raise_for_status()
            logger.info(f"Deleted process instance: {process_instance_id}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to delete process instance: {e}")
            return False

    def terminate_process_instance(
        self,
        process_instance_id: str,
        skip_custom_listeners: bool = False,
        skip_io_mappings: bool = False,
    ) -> bool:
        """
        Terminate a running process instance
        
        Args:
            process_instance_id: Process instance ID to terminate
            skip_custom_listeners: Skip custom listeners during termination
            skip_io_mappings: Skip IO mappings during termination
            
        Returns:
            True if successful
        """
        url = f"{self.engine_rest_url}/process-instance/{process_instance_id}/terminate"
        
        payload = {}
        if skip_custom_listeners:
            payload["skipCustomListeners"] = True
        if skip_io_mappings:
            payload["skipIoMappings"] = True
        
        try:
            response = self.session.put(url, json=payload)
            response.raise_for_status()
            logger.info(f"Terminated process instance: {process_instance_id}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to terminate process instance: {e}")
            return False

    def health_check(self) -> bool:
        """Check if Camunda is accessible"""
        try:
            url = f"{self.engine_rest_url}/version"
            response = self.session.get(url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Camunda health check failed: {e}")
            return False


# Global service instance
_camunda_service: Optional[CamundaService] = None


def get_camunda_service() -> CamundaService:
    """Get or create Camunda service instance"""
    global _camunda_service
    if _camunda_service is None:
        _camunda_service = CamundaService()
    return _camunda_service


