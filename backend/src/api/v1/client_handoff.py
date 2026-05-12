from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/v1/client-handoff", tags=["client-handoff"])

_packages: dict[str, dict] = {}

class HandoffItem(BaseModel):
    type: str  # report, remediation_guide, evidence_archive, scan_logs, executive_slides
    title: str
    description: str
    size_mb: float
    included: bool

class HandoffPackage(BaseModel):
    id: str
    name: str
    engagement_id: str
    client_name: str
    status: str  # preparing, ready, delivered
    items: list[HandoffItem]
    download_token: Optional[str]
    created_at: str
    delivered_at: Optional[str]
    pgp_signed: bool
    checksum_sha256: Optional[str]

class CreateHandoffInput(BaseModel):
    name: str
    engagement_id: str
    client_name: str
    include_items: list[str] = ["report", "remediation_guide", "executive_slides"]

@router.get("/packages", response_model=list[HandoffPackage])
async def list_packages():
    return [HandoffPackage(**p) for p in _packages.values()]

@router.post("/packages", response_model=HandoffPackage)
async def create_package(data: CreateHandoffInput):
    pid = str(uuid.uuid4())
    all_items = [
        HandoffItem(type="report", title="Full Penetration Test Report", description="Complete technical findings with remediation guidance", size_mb=2.4, included="report" in data.include_items),
        HandoffItem(type="executive_slides", title="Executive Presentation", description="Board-level summary with risk metrics", size_mb=1.1, included="executive_slides" in data.include_items),
        HandoffItem(type="remediation_guide", title="Remediation Roadmap", description="Prioritized remediation steps with effort estimates", size_mb=0.8, included="remediation_guide" in data.include_items),
        HandoffItem(type="evidence_archive", title="Evidence Archive", description="Screenshots and artifacts supporting all findings", size_mb=45.2, included="evidence_archive" in data.include_items),
        HandoffItem(type="scan_logs", title="Raw Scan Logs", description="Complete technical scan output for internal review", size_mb=12.8, included="scan_logs" in data.include_items),
    ]
    now = datetime.utcnow().isoformat()
    package = {
        "id": pid, "name": data.name, "engagement_id": data.engagement_id,
        "client_name": data.client_name, "status": "preparing",
        "items": [i.model_dump() for i in all_items], "download_token": None,
        "created_at": now, "delivered_at": None, "pgp_signed": False, "checksum_sha256": None
    }
    _packages[pid] = package
    return HandoffPackage(**package)

@router.post("/packages/{package_id}/prepare", response_model=HandoffPackage)
async def prepare_package(package_id: str, sign_with_pgp: bool = True):
    if package_id not in _packages:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Package not found")
    import hashlib
    p = _packages[package_id]
    p["status"] = "ready"
    p["download_token"] = uuid.uuid4().hex
    p["pgp_signed"] = sign_with_pgp
    p["checksum_sha256"] = hashlib.sha256(package_id.encode()).hexdigest()
    return HandoffPackage(**p)
