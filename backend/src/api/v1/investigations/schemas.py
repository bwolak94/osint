"""Pydantic schemas for the investigations API."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SeedInputSchema(BaseModel):
    type: Literal["email", "username", "nip", "phone", "url", "domain"]
    value: str = Field(..., min_length=1, max_length=500)
    label: str | None = None


class CreateInvestigationRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field("", max_length=2000)
    seed_inputs: list[SeedInputSchema] = Field(..., min_length=1, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=20)
    enabled_scanners: list[str] | None = Field(
        default=None,
        description="Optional list of scanner names to run. If None, all applicable scanners are used.",
    )


class UpdateInvestigationRequest(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=2000)
    tags: list[str] | None = None


class ScanProgressSchema(BaseModel):
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    percentage: float = 0.0
    current_scanner: str | None = None
    nodes_discovered: int = 0
    edges_discovered: int = 0


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    status: str
    owner_id: UUID
    seed_inputs: list[SeedInputSchema]
    tags: list[str]
    scan_progress: ScanProgressSchema = Field(default_factory=ScanProgressSchema)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class InvestigationListResponse(BaseModel):
    items: list[InvestigationResponse]
    total: int
    has_next: bool
    next_cursor: str | None = None


class ScanResultResponse(BaseModel):
    id: UUID
    scanner_name: str
    input_value: str
    status: str
    findings_count: int
    duration_ms: int
    created_at: datetime
    error_message: str | None = None
    raw_data: dict[str, Any] = {}
    extracted_identifiers: list[str] = []


class IdentityResponse(BaseModel):
    """Structured identity extracted from scan results."""

    id: str
    name: str
    type: str  # "person" or "company"
    confidence: float
    data: dict[str, Any]  # All extracted fields
    sources: list[str]


class InvestigationResultsResponse(BaseModel):
    investigation_id: UUID
    scan_results: list[ScanResultResponse]
    total_scans: int
    successful_scans: int
    failed_scans: int
    identities: list[IdentityResponse] = []


class GraphNodeSchema(BaseModel):
    id: str
    type: str
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    sources: list[str] = Field(default_factory=list)
    x: float | None = None
    y: float | None = None


class GraphEdgeSchema(BaseModel):
    id: str
    source: str
    target: str
    type: str
    label: str = ""
    confidence: float = 0.0
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class GraphMetaSchema(BaseModel):
    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0


class GraphResponse(BaseModel):
    nodes: list[GraphNodeSchema]
    edges: list[GraphEdgeSchema]
    meta: GraphMetaSchema


class AddNodeRequest(BaseModel):
    type: str
    label: str = Field(..., min_length=1, max_length=500)
    properties: dict[str, Any] = Field(default_factory=dict)


class AddEdgeRequest(BaseModel):
    source_node_id: str
    target_node_id: str
    type: str
    label: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)


class PathsResponse(BaseModel):
    paths: list[list[GraphNodeSchema]]
    path_count: int


class ExportRequest(BaseModel):
    format: Literal["json", "pdf"] = "json"


class MessageResponse(BaseModel):
    message: str
