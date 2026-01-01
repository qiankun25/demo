from __future__ import annotations

import time
from sqlalchemy import Column, String, Text, Integer

from app.database.session import Base


class InboxEvent(Base):
    __tablename__ = "inbox_events"

    event_id = Column(String(256), primary_key=True)
    routing_key = Column(String(256), nullable=False)
    trace_id = Column(String(64), nullable=False)
    received_at_unix = Column(Integer, nullable=False, default=lambda: int(time.time()))


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    event_id = Column(String(256), primary_key=True)
    routing_key = Column(String(256), nullable=False)
    payload_json = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="PENDING")  # PENDING/PUBLISHED/FAILED
    created_at_unix = Column(Integer, nullable=False, default=lambda: int(time.time()))
    published_at_unix = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)


