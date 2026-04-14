"""Pydantic schemas for investigations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.core.domain.entities.investigation import InvestigationStatus


class InvestigationCreate(BaseModel):
    """Request body for creating an investigation."""

    title: str
    description: str = ""


class InvestigationUpdate(BaseModel):
    """Request body for updating an investigation (all fields optional)."""

    title: str | None = None
    description: str | None = None
    status: InvestigationStatus | None = None


class InvestigationResponse(BaseModel):
    """Response schema for an investigation."""

    model_config = {"from_attributes": True}

    id: UUID
    title: str
    description: str
    status: InvestigationStatus
    owner_id: UUID
    created_at: datetime
    updated_at: datetime
