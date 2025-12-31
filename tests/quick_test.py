"""Unit tests for workflow registry"""

import pytest
import tempfile
from pathlib import Path

from app.engine.workflows import WorkflowRegistry
from app.models.workflow_models import WorkflowDefinition, WorkflowStage, StageType


class TestWorkflowRegistry:
    """Test WorkflowRegistry functionality"""

    def test_register_and_get_workflow(self):
        """Test workflow registration and retrieval"""
        registry = WorkflowRegistry()
        
        workflow = WorkflowDefinition(
            name="Test Workflow",
            task_type="TEST_TASK",
            initial_stage="stage1",
            stages=[
                WorkflowStage(
                    name="stage1",
                    stage_type=StageType.SINGLE,
                    command_routing_key="cmd.test.start",
                    success_event="evt.test.finished",
                    failure_event="evt.test.failed"
                )
            ]
        )
        
        registry.register(workflow)
        retrieved = registry.get_workflow("TEST_TASK")
        
        assert retrieved is not None
        assert retrieved.name == "Test Workflow"
        assert retrieved.task_type == "TEST_TASK"
        assert len(retrieved.stages) == 1

    def test_get_nonexistent_workflow(self):
        """Test retrieving a workflow that doesn't exist"""
        registry = WorkflowRegistry()
        result = registry.get_workflow("NONEXISTENT")
        assert result is None

    def test_get_stage(self):
        """Test stage lookup"""
        registry = WorkflowRegistry()
        
        workflow = WorkflowDefinition(
            name="Test Workflow",
            task_type="TEST_TASK",
            initial_stage="stage1",
            stages=[
                WorkflowStage(
                    name="stage1",
                    stage_type=StageType.SINGLE,
                    command_routing_key="cmd.test.start",
                    success_event="evt.test.finished",
                    failure_event="evt.test.failed"
                ),
                WorkflowStage(
                    name="stage2",
                    stage_type=StageType.FAN_OUT,
                    command_routing_key="cmd.test2.start",
                    success_event="evt.test2.finished",
                    failure_event="evt.test2.failed"
                )
            ]
        )
        
        registry.register(workflow)
        
        stage = registry.get_stage("TEST_TASK", "stage2")
        assert stage is not None
        assert stage.name == "stage2"
        assert stage.stage_type == StageType.FAN_OUT

    def test_get_stage_nonexistent_workflow(self):
        """Test getting stage from nonexistent workflow"""
        registry = WorkflowRegistry()
        stage = registry.get_stage("NONEXISTENT", "stage1")
        assert stage is None

    def test_get_stage_nonexistent_stage(self):
        """Test getting nonexistent stage from existing workflow"""
        registry = WorkflowRegistry()
        
        workflow = WorkflowDefinition(
            name="Test Workflow",
            task_type="TEST_TASK",
            initial_stage="stage1",
            stages=[
                WorkflowStage(
                    name="stage1",
                    stage_type=StageType.SINGLE,
                    command_routing_key="cmd.test.start",
                    success_event="evt.test.finished",
                    failure_event="evt.test.failed"
                )
            ]
        )
        
        registry.register(workflow)
        stage = registry.get_stage("TEST_TASK", "nonexistent_stage")
        assert stage is None

    def test_from_yaml_valid_config(self):
        """Test loading workflows from YAML"""
        yaml_content = """
workflows:
  - name: "Test Workflow"
    task_type: "TEST_TASK"
    initial_stage: "discovery"
    stages:
      - name: "discovery"
        stage_type: "single"
        command_routing_key: "cmd.discovery.start"
        success_event: "evt.discovery.finished"
        failure_event: "evt.discovery.failed"
        next_stage: "processing"
      - name: "processing"
        stage_type: "fan_out"
        command_routing_key: "cmd.processing.start"
        success_event: "evt.processing.finished"
        failure_event: "evt.processing.failed"
        next_stage: null
        filter_function: "test_filter"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            registry = WorkflowRegistry.from_yaml(temp_path)
            
            workflow = registry.get_workflow("TEST_TASK")
            assert workflow is not None
            assert workflow.name == "Test Workflow"
            assert len(workflow.stages) == 2
            
            stage1 = registry.get_stage("TEST_TASK", "discovery")
            assert stage1 is not None
            assert stage1.next_stage == "processing"
            
            stage2 = registry.get_stage("TEST_TASK", "processing")
            assert stage2 is not None
            assert stage2.stage_type == StageType.FAN_OUT
            assert stage2.filter_function == "test_filter"
        finally:
            Path(temp_path).unlink()

    def test_from_yaml_file_not_found(self):
        """Test loading from nonexistent file"""
        with pytest.raises(FileNotFoundError):
            WorkflowRegistry.from_yaml("nonexistent_file.yaml")

    def test_from_yaml_invalid_structure(self):
        """Test loading invalid YAML structure"""
        yaml_content = """
invalid_key:
  - name: "Test"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="missing 'workflows' key"):
                WorkflowRegistry.from_yaml(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_from_yaml_invalid_workflow_data(self):
        """Test loading YAML with invalid workflow data"""
        yaml_content = """
workflows:
  - name: "Test Workflow"
    task_type: "TEST_TASK"
    # Missing required fields like initial_stage and stages
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Failed to parse workflow"):
                WorkflowRegistry.from_yaml(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_morning_report_workflow(self):
        """Test loading the actual MORNING_REPORT workflow configuration"""
        config_path = "config/workflows.yaml"
        
        # Check if the config file exists
        if not Path(config_path).exists():
            pytest.skip(f"Config file not found: {config_path}")
        
        registry = WorkflowRegistry.from_yaml(config_path)
        
        workflow = registry.get_workflow("MORNING_REPORT")
        assert workflow is not None
        assert workflow.name == "Morning Report Workflow"
        assert workflow.initial_stage == "discovery"
        assert len(workflow.stages) == 4
        
        # Verify discovery stage
        discovery = registry.get_stage("MORNING_REPORT", "discovery")
        assert discovery is not None
        assert discovery.stage_type == StageType.SINGLE
        assert discovery.next_stage == "downloader"
        
        # Verify downloader stage (fan-out)
        downloader = registry.get_stage("MORNING_REPORT", "downloader")
        assert downloader is not None
        assert downloader.stage_type == StageType.FAN_OUT
        assert downloader.filter_function == "work_has_pdf_candidate"
        assert downloader.next_stage == "parser"
        
        # Verify parser stage
        parser = registry.get_stage("MORNING_REPORT", "parser")
        assert parser is not None
        assert parser.next_stage == "indexer"
        
        # Verify indexer stage (final)
        indexer = registry.get_stage("MORNING_REPORT", "indexer")
        assert indexer is not None
        assert indexer.next_stage is None
