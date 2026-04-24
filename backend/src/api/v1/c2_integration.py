"""C2 Framework Integration — reference and tracking for authorized pentest engagements."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/c2", tags=["c2-integration"])


class C2Framework(BaseModel):
    id: str
    name: str
    type: str  # commercial, open_source
    status: str  # connected, disconnected, not_configured
    description: str
    supported_protocols: list[str]
    documentation_url: str


class C2Listener(BaseModel):
    id: str
    framework: str
    protocol: str
    host: str
    port: int
    status: str
    active_sessions: int
    engagement_id: str


C2_FRAMEWORKS: list[C2Framework] = [
    C2Framework(
        id="cobalt-strike",
        name="Cobalt Strike",
        type="commercial",
        status="not_configured",
        description="Commercial adversary simulation platform",
        supported_protocols=["HTTP", "HTTPS", "SMB", "DNS"],
        documentation_url="https://www.cobaltstrike.com/",
    ),
    C2Framework(
        id="metasploit",
        name="Metasploit Framework",
        type="open_source",
        status="not_configured",
        description="Open source penetration testing framework",
        supported_protocols=["TCP", "HTTP", "HTTPS", "SMB"],
        documentation_url="https://www.metasploit.com/",
    ),
    C2Framework(
        id="sliver",
        name="Sliver",
        type="open_source",
        status="not_configured",
        description="Modern cross-platform C2 framework",
        supported_protocols=["mTLS", "WireGuard", "HTTP/S", "DNS"],
        documentation_url="https://github.com/BishopFox/sliver",
    ),
    C2Framework(
        id="havoc",
        name="Havoc",
        type="open_source",
        status="not_configured",
        description="Modern and malleable post-exploitation framework",
        supported_protocols=["HTTP", "HTTPS", "SMB"],
        documentation_url="https://github.com/HavocFramework/Havoc",
    ),
]


@router.get("/frameworks", response_model=list[C2Framework])
async def list_frameworks() -> list[C2Framework]:
    """List supported C2 frameworks for authorized engagements."""
    return C2_FRAMEWORKS


@router.get("/listeners", response_model=list[C2Listener])
async def list_listeners() -> list[C2Listener]:
    """List active C2 listeners (tracking only — not creating actual listeners)."""
    return []


@router.get("/status")
async def c2_status() -> dict:
    return {
        "connected_frameworks": 0,
        "active_listeners": 0,
        "active_sessions": 0,
        "note": "Connect your authorized C2 infrastructure via API keys in Settings",
    }
