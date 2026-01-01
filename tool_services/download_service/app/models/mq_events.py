"""Inbox/Outbox tables for reliable MQ processing (at-least-once + idempotency)."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Text

from app.database import Base


class InboxEvent(Base):
    __tablename__ = "inbox_event"

    id = Column(Text, primary_key=True)  # idempotency_key / message_id
    routing_key = Column(Text, nullable=False)
    trace_id = Column(Text, nullable=True)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class OutboxStatus(str):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class OutboxEvent(Base):
    __tablename__ = "outbox_event"

    event_id = Column(Text, primary_key=True)  # deterministic idempotency key
    routing_key = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default=OutboxStatus.PENDING)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)


