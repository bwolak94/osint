"""SQLAlchemy model for Hub agent conversation history."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID

from src.adapters.db.database import Base


class HubConversation(Base):
    __tablename__ = "hub_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    task_id = Column(String, nullable=False, unique=True, index=True)
    module = Column(String, nullable=False, default="chat")
    query = Column(Text, nullable=False)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    thoughts = Column(JSON, default=list)
    result_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
