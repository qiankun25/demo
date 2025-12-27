"""Workflow registry for managing workflow definitions"""

from typing import Dict, Optional
import yaml
from pathlib import Path

from app.models.workflow_models import WorkflowDefinition, WorkflowStage


class WorkflowRegistry:
    """Registry for workflow definitions"""

    def __init__(self):
        self._workflows: Dict[str, WorkflowDefinition] = {}

    def register(self, workflow: WorkflowDefinition) -> None:
        """
        Register a workflow definition
        
        Args:
            workflow: WorkflowDefinition to register
        """
        self._workflows[workflow.task_type] = workflow

    def get_workflow(self, task_type: str) -> Optional[WorkflowDefinition]:
        """
        Retrieve workflow by task type
        
        Args:
            task_type: The task type identifier
            
        Returns:
            WorkflowDefinition if found, None otherwise
        """
        return self._workflows.get(task_type)

    def get_stage(self, task_type: str, stage_name: str) -> Optional[WorkflowStage]:
        """
        Get specific stage from workflow
        
        Args:
            task_type: The task type identifier
            stage_name: The name of the stage
            
        Returns:
            WorkflowStage if found, None otherwise
        """
        workflow = self.get_workflow(task_type)
        if not workflow:
            return None
        
        for stage in workflow.stages:
            if stage.name == stage_name:
                return stage
        
        return None

    @classmethod
    def from_yaml(cls, config_path: str) -> "WorkflowRegistry":
        """
        Load workflows from YAML configuration
        
        Args:
            config_path: Path to YAML configuration file
            
        Returns:
            WorkflowRegistry instance with loaded workflows
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If YAML is invalid or missing required fields
        """
        registry = cls()
        
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Workflow configuration file not found: {config_path}")
        
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        if not config_data or 'workflows' not in config_data:
            raise ValueError("Invalid workflow configuration: missing 'workflows' key")
        
        for workflow_data in config_data['workflows']:
            try:
                workflow = WorkflowDefinition(**workflow_data)
                registry.register(workflow)
            except Exception as e:
                raise ValueError(f"Failed to parse workflow '{workflow_data.get('name', 'unknown')}': {e}")
        
        return registry
