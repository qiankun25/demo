"""Message protocol models for RabbitMQ communication.

This module supports both:
- Legacy v0 payloads used by existing tool services (input_key/output_key)
- New v1 payloads using claim-check `result_ref` (see tool_services/libs/contracts)
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import time


class MsgHeader(BaseModel):
    """Message header containing trace context and metadata"""
    trace_id: str
    task_type: str
    sender: str
    timestamp: float = Field(default_factory=time.time)


class CommandPayload(BaseModel):
    """Payload for command messages sent to tool services"""
    task_id: str
    # Legacy field; in ref-only mode services must rely on `input_ref`.
    input_key: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    # Optional migration fields (v1-ish); tool services may ignore safely.
    trace_id: Optional[str] = None
    work_key: Optional[str] = None
    version: Optional[str] = None
    command: Optional[str] = None
    input_ref: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None


class EventPayload(BaseModel):
    """Payload for event messages received from tool services"""
    status: str  # "SUCCESS" or "FAIL"
    # Legacy fields; in ref-only mode services must rely on `result_ref`.
    output_key: Optional[str] = None
    input_key: Optional[str] = None
    error_msg: Optional[str] = None
    # Optional v1 fields
    version: Optional[str] = None
    event: Optional[str] = None
    work_key: Optional[str] = None
    result_ref: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None


class MessagePackage(BaseModel):
    """Standardized message format for all RabbitMQ messages"""
    header: MsgHeader
    payload: Dict[str, Any]
