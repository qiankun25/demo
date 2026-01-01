"""Shared message contracts for Nexus microservices.

This package is intentionally dependency-light and only uses pydantic models.
It is imported by both `nexus/` (orchestration-service) and tool services.
"""

from .models import (  # noqa: F401
    ErrorInfo,
    EventPayloadV1,
    CommandPayloadV1,
    ResultRef,
    Status,
)


