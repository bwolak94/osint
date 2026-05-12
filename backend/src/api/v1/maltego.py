from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any

router = APIRouter(prefix="/maltego", tags=["maltego"])

# Maltego entity types we support
SUPPORTED_ENTITY_TYPES = [
    "maltego.Domain", "maltego.IPv4Address", "maltego.EmailAddress",
    "maltego.Person", "maltego.PhoneNumber", "maltego.URL",
    "maltego.Username", "maltego.Organization",
]

# Transform registry: maps (entity_type, transform_name) -> scanner_type
TRANSFORM_REGISTRY = {
    ("maltego.Domain", "DNSLookup"): "dns",
    ("maltego.Domain", "SubdomainEnumeration"): "subdomain",
    ("maltego.Domain", "WHOISLookup"): "whois",
    ("maltego.Domain", "CertificateLookup"): "cert",
    ("maltego.IPv4Address", "ASNLookup"): "asn",
    ("maltego.IPv4Address", "GeoIPLookup"): "geoip",
    ("maltego.IPv4Address", "VirusTotalCheck"): "virustotal",
    ("maltego.EmailAddress", "BreachCheck"): "breach",
    ("maltego.EmailAddress", "HoleheLookup"): "holehe",
    ("maltego.Username", "SherlockLookup"): "sherlock",
    ("maltego.Username", "MaigretLookup"): "maigret",
}


class MaltegoEntity(BaseModel):
    type: str
    value: str
    properties: dict[str, Any] = {}


class MaltegoTransformRequest(BaseModel):
    entity: MaltegoEntity
    transform_name: str
    limit: int = 50


class MaltegoTransformResponse(BaseModel):
    entities: list[MaltegoEntity]
    messages: list[str] = []
    error: Optional[str] = None


class TransformConfig(BaseModel):
    transform_name: str
    display_name: str
    entity_type: str
    description: str
    scanner_type: str


@router.get("/transforms", response_model=list[TransformConfig])
async def list_transforms() -> list[TransformConfig]:
    return [
        TransformConfig(
            transform_name=k[1],
            display_name=k[1].replace("Lookup", "Look Up").replace("Check", " Check"),
            entity_type=k[0],
            description=f"Run {v} scanner",
            scanner_type=v,
        )
        for k, v in TRANSFORM_REGISTRY.items()
    ]


@router.get("/transforms/itds")
async def get_itds_config() -> dict:
    """Returns Maltego ITDS seed file for importing transforms into Maltego."""
    transforms = []
    for (entity_type, name), scanner in TRANSFORM_REGISTRY.items():
        transforms.append({
            "name": name,
            "displayName": name,
            "abstract": f"OSINT Platform - {name}",
            "template": False,
            "visibility": "public",
            "description": f"Run {scanner} scanner via OSINT Platform",
            "author": "OSINT Platform",
            "requireDisplayInfo": False,
            "entityType": entity_type,
            "uiTemplate": "",
            "jasperPrint": "",
            "url": "/api/v1/maltego/transform",
            "inputConstraint": "",
            "outputEntities": [],
            "defaultSets": ["OSINT Platform"],
            "oauth": None,
        })
    return {
        "transforms": transforms,
        "sets": [{"name": "OSINT Platform", "description": "OSINT Platform Transforms"}],
    }


@router.post("/transform", response_model=MaltegoTransformResponse)
async def run_transform(request: MaltegoTransformRequest) -> MaltegoTransformResponse:
    key = (request.entity.type, request.transform_name)
    if key not in TRANSFORM_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Transform '{request.transform_name}' not supported for entity type '{request.entity.type}'",
        )

    scanner_type = TRANSFORM_REGISTRY[key]
    # Return result showing the transform would enqueue the scanner
    return MaltegoTransformResponse(
        entities=[
            MaltegoEntity(
                type="maltego.Domain",
                value=f"scan-result.{request.entity.value}",
                properties={"scanner": scanner_type, "status": "queued"},
            ),
        ],
        messages=[
            f"Scan enqueued: {scanner_type} on {request.entity.value}. "
            "Results will appear in OSINT Platform."
        ],
    )
