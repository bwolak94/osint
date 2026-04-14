"""Legacy graph router — graph endpoints are now under /investigations/{id}/graph."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def graph_health() -> dict[str, str]:
    return {"status": "ok", "note": "Graph endpoints moved to /api/v1/investigations/{id}/graph"}
