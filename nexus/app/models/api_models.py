"""API request and response models"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List


class JobSubmitRequest(BaseModel):
    """Request model for job submission endpoint"""
    task_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class JobSubmitResponse(BaseModel):
    """Response model for job submission endpoint"""
    trace_id: str
    status: str = "submitted"
    message: str = "Job submitted successfully"


class WorkItemStatus(BaseModel):
    """Status information for a single work item"""
    work_key: str
    status: str  # "pending", "completed", "failed"
    stage: Optional[str] = None
    error_msg: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Response model for job status query endpoint"""
    trace_id: str
    task_type: str
    status: str  # "running", "completed", "failed"
    total_work_items: int
    completed_count: int
    failed_count: int
    pending_count: int
    artifacts: Dict[str, str] = Field(default_factory=dict, description="Map of artifact keys to download URLs")
    failures: List[Dict[str, Any]] = Field(default_factory=list)
