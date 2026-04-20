"""Maltego transform compatibility endpoint (placeholder)."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/maltego/transform")
async def maltego_transform(body: dict) -> dict:
    """Placeholder for Maltego transform compatibility.

    Accepts Maltego iTDS-style requests and returns results.
    Full implementation requires Maltego transform XML format.
    """
    return {
        "status": "placeholder",
        "message": "Maltego transform endpoint — configure as remote transform in Maltego",
        "supported_transforms": ["NIPToCompany", "EmailToServices", "DomainToIP", "IPToGeoLocation"],
    }
