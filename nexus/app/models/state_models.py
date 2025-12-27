"""State management models for job context tracking"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class FailureRecord(BaseModel):
    """Record of a work item failure"""
    work_key: str
    stage: str
    routing_key: str
    input_key: str
    error_msg: str


class JobContext(BaseModel):
    """Persistent state context for a job throughout its lifecycle"""
    trace_id: str
    task_type: str
    init_key: str
    requested_limit: int = 5
    work_keys: List[str] = Field(default_factory=list)
    completed_work_keys: List[str] = Field(default_factory=list)
    failures: List[FailureRecord] = Field(default_factory=list)
    discovery_key: Optional[str] = None
    report_key: Optional[str] = None
    current_stage: str = "init"
    metadata: Dict[str, Any] = Field(default_factory=dict)
