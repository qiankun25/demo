"""Pydantic contracts for command/event envelopes and claim-check references.

P0 mode (ref-only):
- Commands MUST carry `input_ref` (no cross-service `input_key`)
- Events MUST carry `result_ref` (no cross-service `output_key`)

We keep some legacy fields for local debugging only, but services MUST NOT rely
on them for cross-service coordination.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class Status(str, Enum):
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"


class ResultRef(BaseModel):
    """Claim-check reference to an artifact owned by a specific service."""

    service: str = Field(..., description="Owning service name, e.g. download-service")
    type: str = Field(..., description="Artifact type, e.g. file/parsed_doc/search_result")
    id: str = Field(..., description="Service-scoped artifact identifier")
    version: str = Field(default="v1", description="Schema version for this ref")
    checksum: Optional[str] = Field(default=None, description="Optional checksum, e.g. sha256 hex")
    fetch: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional fetch hints, e.g. {'url': '...'} or {'path': '/v1/files/..'}",
    )


class ErrorInfo(BaseModel):
    code: str = Field(default="UNKNOWN", description="Machine-readable error code")
    message: str = Field(default="", description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Optional structured details")


class CommandPayloadV1(BaseModel):
    """Canonical command payload v1 (sent on `cmd.*`)."""

    version: str = Field(default="v1")

    # Routing information
    command: str = Field(..., description="Command name, usually equals RabbitMQ routing key")
    task_id: str = Field(..., description="Task identifier; typically trace_id or work_key")
    trace_id: str = Field(..., description="End-to-end trace identifier")
    work_key: Optional[str] = Field(default=None, description="Work item key within trace (fan-out)")

    # Data
    params: Dict[str, Any] = Field(default_factory=dict)

    # Ref-only contract: required
    input_ref: ResultRef = Field(..., description="Required claim-check input ref")

    # Legacy/debug fields (must not be used for cross-service integration)
    input_key: Optional[str] = Field(default=None, description="Legacy storage key (debug only)")

    # Idempotency (optional)
    idempotency_key: Optional[str] = Field(default=None)


class EventPayloadV1(BaseModel):
    """Canonical event payload v1 (sent on `evt.*`)."""

    version: str = Field(default="v1")

    event: str = Field(..., description="Event name, usually equals RabbitMQ routing key")
    trace_id: str = Field(..., description="End-to-end trace identifier")
    work_key: Optional[str] = Field(default=None)
    status: Status = Field(default=Status.SUCCESS)

    # Ref-only contract: required
    result_ref: ResultRef = Field(..., description="Required claim-check output ref")

    # Legacy/debug fields (must not be used for cross-service integration)
    output_key: Optional[str] = Field(default=None, description="Legacy storage key (debug only)")
    input_key: Optional[str] = Field(default=None, description="Legacy storage key (debug only)")
    error_msg: Optional[str] = Field(default=None, description="Legacy error message (debug only)")

    # New structured error and metrics
    error: Optional[ErrorInfo] = Field(default=None)
    metrics: Dict[str, Any] = Field(default_factory=dict)

    timestamp: float = Field(default_factory=time.time)


class EnvelopeHeader(BaseModel):
    """Optional header if a service wants to embed envelope data into the message payload."""

    trace_id: str
    sender: str
    timestamp: float = Field(default_factory=time.time)


class MQEnvelope(BaseModel):
    """Generic envelope for JSON messages.

    NOTE: `nexus/` currently uses its own header models. This wrapper is provided
    for services that want a single canonical shape.
    """

    header: EnvelopeHeader
    payload: Dict[str, Any]


