"""Pydantic schemas for the investigations API."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import re

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SeedInputSchema(BaseModel):
    type: Literal["email", "username", "nip", "phone", "url", "domain", "ip_address"]
    value: str = Field(..., min_length=1, max_length=500)
    label: str | None = None

    @model_validator(mode="after")
    def _validate_value_format(self) -> "SeedInputSchema":
        if self.type == "email" and "@" not in self.value:
            raise ValueError("Email must contain @")
        if self.type == "nip":
            cleaned = self.value.replace("-", "").replace(" ", "")
            if not cleaned.isdigit() or len(cleaned) != 10:
                raise ValueError("NIP must be 10 digits")
        if self.type == "phone" and not re.match(r"^\+?\d{7,15}$", self.value.replace(" ", "")):
            raise ValueError("Phone must be in E.164 format")
        if self.type == "url" and not self.value.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return self


class CreateInvestigationRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {
                "title": "Investigate ACME Corp",
                "description": "Check public records for ACME Corp",
                "seed_inputs": [
                    {"type": "nip", "value": "1234567890"},
                    {"type": "email", "value": "contact@acme.example.com"},
                ],
                "tags": ["acme", "due-diligence"],
                "enabled_scanners": ["holehe", "playwright_krs"],
            }
        ]
    })

    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field("", max_length=2000)
    seed_inputs: list[SeedInputSchema] = Field(..., min_length=1, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=20)
    enabled_scanners: list[str] | None = Field(
        default=None,
        description="Optional list of scanner names to run. If None, all applicable scanners are used.",
    )
    schedule_cron: str | None = None  # e.g., "0 0 * * 1" for weekly Monday


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
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "title": "Investigate ACME Corp",
                    "description": "Check public records for ACME Corp",
                    "status": "running",
                    "owner_id": "11111111-2222-3333-4444-555555555555",
                    "seed_inputs": [{"type": "nip", "value": "1234567890"}],
                    "tags": ["acme", "due-diligence"],
                    "scan_progress": {"total_tasks": 3, "completed_tasks": 1, "percentage": 33.3},
                    "created_at": "2026-01-15T10:30:00Z",
                    "updated_at": "2026-01-15T10:31:00Z",
                    "completed_at": None,
                }
            ]
        },
    )

    id: UUID
    title: str
    description: str
    status: str
    owner_id: UUID
    seed_inputs: list[SeedInputSchema]
    tags: list[str]
    scan_progress: ScanProgressSchema = Field(default_factory=ScanProgressSchema)
    schedule_cron: str | None = None
    next_run_at: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class InvestigationListResponse(BaseModel):
    items: list[InvestigationResponse]
    total: int
    has_next: bool
    next_cursor: str | None = None


class ScanResultResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {
                "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "scanner_name": "holehe",
                "input_value": "user@example.com",
                "status": "success",
                "findings_count": 5,
                "duration_ms": 1200,
                "created_at": "2026-01-15T10:31:00Z",
                "error_message": None,
                "raw_data": {"registered_count": 5, "registered_on": ["twitter.com", "github.com"]},
                "extracted_identifiers": ["twitter.com", "github.com"],
            }
        ]
    })

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
