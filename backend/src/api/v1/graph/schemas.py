"""Legacy graph schemas — kept for backwards compatibility."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AddNodeRequest(BaseModel):
    node_id: UUID
    labels: list[str]
    properties: dict[str, Any] = {}


class SubgraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
