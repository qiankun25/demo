"""Message protocol models for RabbitMQ communication"""

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
    input_key: str
    params: Dict[str, Any] = Field(default_factory=dict)


class EventPayload(BaseModel):
    """Payload for event messages received from tool services"""
    status: str  # "SUCCESS" or "FAIL"
    output_key: Optional[str] = None
    input_key: Optional[str] = None
    error_msg: Optional[str] = None


class MessagePackage(BaseModel):
    """Standardized message format for all RabbitMQ messages"""
    header: MsgHeader
    payload: Dict[str, Any]
