"""STIX 2.1 export endpoint for investigations.

Exports investigation graph nodes and identities as a STIX 2.1 Bundle
containing Indicators, Identity objects, and Relationships.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.database import async_session_factory
from src.adapters.db.models import IdentityModel, InvestigationModel, ScanResultModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.utils.time import utcnow

router = APIRouter()

_STIX_VERSION = "2.1"
_STIX_SPEC_VERSION = "2.1"


def _stix_id(obj_type: str, seed: str) -> str:
    """Generate a deterministic STIX ID from type and seed."""
    namespace = uuid.UUID("00abedb4-aa42-466c-9c01-fed23315a9b7")
    return f"{obj_type}--{uuid.uuid5(namespace, seed)}"


def _ts(dt: datetime | None = None) -> str:
    t = dt or utcnow()
    return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _identity_to_stix(identity: IdentityModel) -> dict[str, Any]:
    """Convert an IdentityModel to a STIX 2.1 Identity object."""
    return {
        "type": "identity",
        "spec_version": _STIX_SPEC_VERSION,
        "id": _stix_id("identity", str(identity.id)),
        "created": _ts(identity.created_at),
        "modified": _ts(identity.created_at),
        "name": identity.display_name,
        "identity_class": "individual",
        "contact_information": ", ".join(
            [*identity.emails, *identity.phones, *identity.usernames]
        ),
        "confidence": int(identity.confidence_score * 100),
        "labels": identity.sources,
    }


def _email_to_indicator(email: str, investigation_id: str) -> dict[str, Any]:
    return {
        "type": "indicator",
        "spec_version": _STIX_SPEC_VERSION,
        "id": _stix_id("indicator", f"email:{email}:{investigation_id}"),
        "created": _ts(),
        "modified": _ts(),
        "name": f"Email: {email}",
        "pattern": f"[email-message:from_ref.value = '{email}']",
        "pattern_type": "stix",
        "valid_from": _ts(),
        "indicator_types": ["malicious-activity"],
    }


def _domain_to_indicator(domain: str, investigation_id: str) -> dict[str, Any]:
    return {
        "type": "indicator",
        "spec_version": _STIX_SPEC_VERSION,
        "id": _stix_id("indicator", f"domain:{domain}:{investigation_id}"),
        "created": _ts(),
        "modified": _ts(),
        "name": f"Domain: {domain}",
        "pattern": f"[domain-name:value = '{domain}']",
        "pattern_type": "stix",
        "valid_from": _ts(),
        "indicator_types": ["anomalous-activity"],
    }


def _build_bundle(objects: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "bundle",
        "id": _stix_id("bundle", str(uuid.uuid4())),
        "spec_version": _STIX_SPEC_VERSION,
        "objects": objects,
    }


@router.get(
    "/investigations/{investigation_id}/export/stix",
    tags=["stix-export"],
    summary="Export investigation as a STIX 2.1 bundle",
    responses={
        200: {
            "content": {"application/stix+json": {}},
            "description": "STIX 2.1 Bundle containing Report, Identity, Indicator, and Relationship objects.",
            "headers": {
                "Content-Disposition": {
                    "description": "attachment; filename=\"investigation-{id}.stix.json\"",
                    "schema": {"type": "string"},
                }
            },
        },
        403: {"description": "Access denied — not owner and no ACL entry."},
        404: {"description": "Investigation not found."},
    },
)
async def export_stix(
    investigation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(lambda: async_session_factory()),
) -> JSONResponse:
    """Export all identities and extracted IOCs as a STIX 2.1 Bundle JSON."""
    inv_id = uuid.UUID(investigation_id)

    inv = (
        await db.execute(select(InvestigationModel).where(InvestigationModel.id == inv_id))
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    if str(inv.owner_id) != str(current_user.id):
        # Check ACL table for view/edit/admin permission
        from src.adapters.db.models import InvestigationACLModel
        acl = (
            await db.execute(
                select(InvestigationACLModel).where(
                    InvestigationACLModel.investigation_id == inv_id,
                    InvestigationACLModel.user_id == current_user.id,
                )
            )
        ).scalar_one_or_none()
        if acl is None:
            raise HTTPException(status_code=403, detail="Access denied")

    identities = (
        await db.execute(select(IdentityModel).where(IdentityModel.investigation_id == inv_id))
    ).scalars().all()

    scan_results = (
        await db.execute(select(ScanResultModel).where(ScanResultModel.investigation_id == inv_id))
    ).scalars().all()

    stix_objects: list[dict[str, Any]] = []

    # Build investigation as a STIX Report
    stix_objects.append({
        "type": "report",
        "spec_version": _STIX_SPEC_VERSION,
        "id": _stix_id("report", investigation_id),
        "created": _ts(inv.created_at),
        "modified": _ts(inv.updated_at),
        "name": inv.title,
        "description": inv.description,
        "published": _ts(inv.created_at),
        "report_types": ["threat-actor"],
        "object_refs": [],
    })

    # Convert identities
    identity_stix_ids = []
    for identity in identities:
        obj = _identity_to_stix(identity)
        stix_objects.append(obj)
        identity_stix_ids.append(obj["id"])

        # Derive indicators from emails
        for email in identity.emails:
            ind = _email_to_indicator(email, investigation_id)
            stix_objects.append(ind)
            # Relationship: identity "attributed-to" indicator
            stix_objects.append({
                "type": "relationship",
                "spec_version": _STIX_SPEC_VERSION,
                "id": _stix_id("relationship", f"{obj['id']}:{ind['id']}"),
                "created": _ts(),
                "modified": _ts(),
                "relationship_type": "attributed-to",
                "source_ref": ind["id"],
                "target_ref": obj["id"],
            })

    # Derive domain indicators from scan results
    for result in scan_results:
        if result.scanner_name in ("dns_scanner", "subdomain_scanner", "subfinder_scanner"):
            for domain in result.extracted_identifiers:
                if "." in domain and not domain.startswith("@"):
                    ind = _domain_to_indicator(domain, investigation_id)
                    stix_objects.append(ind)

    # Patch report object_refs
    stix_objects[0]["object_refs"] = [o["id"] for o in stix_objects[1:]]

    # Compute a version hash from the current graph state so consumers can
    # detect stale exports.  Hash is over all scan result IDs + identities.
    import hashlib
    version_payload = "|".join(
        sorted([str(r.id) for r in scan_results] + [str(i.id) for i in identities])
    )
    version_hash = hashlib.sha256(version_payload.encode()).hexdigest()[:16]

    bundle = _build_bundle(stix_objects)

    # Embed version metadata in custom STIX extension
    bundle["x_osint_version_hash"] = version_hash
    bundle["x_osint_exported_at"] = _ts()
    bundle["x_osint_investigation_status"] = inv.status

    return JSONResponse(
        content=bundle,
        media_type="application/stix+json",
        headers={
            "Content-Disposition": f'attachment; filename="investigation-{investigation_id}.stix.json"',
            "X-OSINT-Version-Hash": version_hash,
        },
    )
