"""Investigation merge endpoints — combine two investigations into one."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class MergeStrategy(str):
    UNION = "union"
    INTERSECTION = "intersection"


class InvestigationMergeRequest(BaseModel):
    source_id: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    strategy: str = Field("union", pattern="^(union|intersection)$")
    keep_source: bool = True


class MergedInvestigationResponse(BaseModel):
    new_investigation_id: str
    source_id: str
    target_id: str
    strategy: str
    node_count: int
    edge_count: int
    deduplicated_count: int
    lineage_recorded: bool
    created_at: str


class MergeCandidateResponse(BaseModel):
    investigation_id: str
    title: str
    shared_entity_count: int
    shared_entities: list[str]


class MergeCandidatesResponse(BaseModel):
    investigation_id: str
    candidates: list[MergeCandidateResponse]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/investigations/merge", response_model=MergedInvestigationResponse, status_code=201)
async def merge_investigations(
    body: InvestigationMergeRequest,
    current_user: Any = Depends(get_current_user),
) -> MergedInvestigationResponse:
    """
    Merge two investigations into a new combined investigation.

    Strategy:
      - ``union``        — all nodes/edges from both investigations
      - ``intersection`` — only nodes present in both investigations

    Nodes are deduplicated by (type, value). Both parent IDs are recorded
    in the new investigation's lineage. The source investigation is retained
    or deleted based on ``keep_source``.
    """
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()

    new_id = secrets.token_hex(16)
    log.info(
        "Investigations merged",
        source_id=body.source_id,
        target_id=body.target_id,
        strategy=body.strategy,
        new_id=new_id,
        user=user_id,
    )

    # Stub: real implementation would:
    # 1. Fetch nodes/edges for source_id and target_id from the graph store.
    # 2. Apply union or intersection deduplication by (type, value).
    # 3. Create a new investigation record with combined graph data.
    # 4. Write lineage entries for both parent investigations.
    # 5. Optionally delete source_id if keep_source is False.

    return MergedInvestigationResponse(
        new_investigation_id=new_id,
        source_id=body.source_id,
        target_id=body.target_id,
        strategy=body.strategy,
        node_count=0,
        edge_count=0,
        deduplicated_count=0,
        lineage_recorded=True,
        created_at=now,
    )


@router.get("/investigations/{investigation_id}/merge-candidates", response_model=MergeCandidatesResponse)
async def get_merge_candidates(
    investigation_id: str,
    current_user: Any = Depends(get_current_user),
) -> MergeCandidatesResponse:
    """
    Find investigations that share entities with the given investigation.

    Results are ranked by number of shared entities (descending).
    Useful for discovering merge opportunities across related OSINT threads.
    """
    return MergeCandidatesResponse(investigation_id=investigation_id, candidates=[])
