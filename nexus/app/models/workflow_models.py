"""Workflow definition models for configurable DAG execution"""

from pydantic import BaseModel
from typing import List, Optional
from enum import Enum


class StageType(str, Enum):
    """Type of workflow stage execution pattern"""
    SINGLE = "single"
    FAN_OUT = "fan_out"
    FAN_IN = "fan_in"


class WorkflowStage(BaseModel):
    """Definition of a single stage in a workflow"""
    name: str
    stage_type: StageType
    command_routing_key: str
    success_event: str
    failure_event: str
    next_stage: Optional[str] = None
    filter_function: Optional[str] = None  # For fan-out filtering


class WorkflowDefinition(BaseModel):
    """Complete workflow definition with all stages"""
    name: str
    task_type: str
    stages: List[WorkflowStage]
    initial_stage: str
