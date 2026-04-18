"""STIX 2.1 bundle exporter for OSINT investigation graphs.

Converts investigation nodes and edges into a standards-compliant STIX 2.1
bundle without requiring the stix2 library — the JSON structure is built
manually so there are zero heavy dependencies.

STIX object mapping:
    ip          → ipv4-addr
    domain      → domain-name
    email       → email-addr
    person      → identity (identity_class=individual)
    organization→ identity (identity_class=organization)
    hash        → file (with hashes dict)
    cve         → vulnerability
    url         → url
    malware     → malware
    threat_actor→ threat-actor

Usage::

    exporter = STIXExporter()
    bundle = exporter.export_investigation(
        investigation={"id": "...", "name": "...", ...},
        nodes=[...],
        edges=[...],
        scan_results=[...],
    )
    print(bundle.to_json())
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# STIX type constants
# ---------------------------------------------------------------------------

_NODE_TYPE_MAP: dict[str, str] = {
    "ip": "ipv4-addr",
    "ip_address": "ipv4-addr",
    "ipv4": "ipv4-addr",
    "domain": "domain-name",
    "email": "email-addr",
    "person": "identity",
    "individual": "identity",
    "organization": "identity",
    "org": "identity",
    "hash": "file",
    "md5": "file",
    "sha1": "file",
    "sha256": "file",
    "cve": "vulnerability",
    "vulnerability": "vulnerability",
    "url": "url",
    "malware": "malware",
    "threat_actor": "threat-actor",
    "threatactor": "threat-actor",
}

_IDENTITY_CLASS_MAP: dict[str, str] = {
    "person": "individual",
    "individual": "individual",
    "organization": "organization",
    "org": "organization",
}

# Hash field name normalisation: node type → STIX hashes key
_HASH_KEY_MAP: dict[str, str] = {
    "md5": "MD5",
    "sha1": "SHA-1",
    "sha256": "SHA-256",
    "hash": "SHA-256",
}


# ---------------------------------------------------------------------------
# Bundle dataclass
# ---------------------------------------------------------------------------


@dataclass
class STIXBundle:
    """Lightweight STIX 2.1 bundle container."""

    id: str = field(default_factory=lambda: f"bundle--{uuid4()}")
    objects: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self, indent: int = 2) -> str:
        """Serialise the bundle to a JSON string."""
        return json.dumps(
            {
                "type": "bundle",
                "id": self.id,
                "spec_version": "2.1",
                "objects": self.objects,
            },
            indent=indent,
            default=str,
        )


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------


class STIXExporter:
    """Converts an OSINT investigation graph to a STIX 2.1 bundle.

    All external calls are wrapped in try/except so a bad node or edge never
    aborts the entire export — it is skipped and logged instead.
    """

    def export_investigation(
        self,
        investigation: dict[str, Any],
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        scan_results: list[dict[str, Any]],
    ) -> STIXBundle:
        """Convert an investigation graph to a STIX 2.1 bundle.

        Args:
            investigation: Metadata dict with keys id, name, description,
                           created_at, tags.
            nodes:         Graph nodes with keys id, type, value, confidence,
                           properties.
            edges:         Graph edges with keys from_id, to_id, relation_type.
            scan_results:  Raw scanner output (currently unused in export but
                           included for future note/observed-data objects).

        Returns:
            A STIXBundle ready to serialise via ``to_json()``.
        """
        bundle = STIXBundle()

        # node_id (graph) → stix_id mapping for relationship resolution
        stix_id_map: dict[str, str] = {}

        # --- Convert nodes ---
        for node in nodes:
            try:
                stix_obj = self._node_to_stix(node)
                if stix_obj is None:
                    continue
                bundle.objects.append(stix_obj)
                stix_id_map[node["id"]] = stix_obj["id"]
            except Exception as exc:
                log.warning(
                    "STIX node conversion failed",
                    node_id=node.get("id"),
                    node_type=node.get("type"),
                    error=str(exc),
                )

        # --- Convert edges ---
        for edge in edges:
            try:
                from_stix = stix_id_map.get(edge.get("from_id", ""))
                to_stix = stix_id_map.get(edge.get("to_id", ""))
                if not from_stix or not to_stix:
                    log.debug(
                        "STIX edge skipped — missing node mapping",
                        from_id=edge.get("from_id"),
                        to_id=edge.get("to_id"),
                    )
                    continue
                rel = self._edge_to_stix_relationship(edge, from_stix, to_stix)
                bundle.objects.append(rel)
            except Exception as exc:
                log.warning(
                    "STIX edge conversion failed",
                    edge=edge,
                    error=str(exc),
                )

        # --- Wrap everything in a STIX Report ---
        object_refs = [obj["id"] for obj in bundle.objects]
        try:
            report = self._make_report(investigation, object_refs)
            bundle.objects.append(report)
        except Exception as exc:
            log.warning("STIX report creation failed", error=str(exc))

        log.info(
            "STIX bundle exported",
            bundle_id=bundle.id,
            objects=len(bundle.objects),
            nodes_converted=len(stix_id_map),
        )
        return bundle

    # ------------------------------------------------------------------
    # Node conversion
    # ------------------------------------------------------------------

    def _node_to_stix(self, node: dict[str, Any]) -> dict[str, Any] | None:
        """Map a single graph node to its STIX 2.1 SCO/SDO representation.

        Returns None for unmapped node types so callers can skip gracefully.
        """
        raw_type: str = (node.get("type") or "").lower().strip()
        stix_type = _NODE_TYPE_MAP.get(raw_type)

        if stix_type is None:
            log.debug("No STIX mapping for node type", node_type=raw_type)
            return None

        now = self._now()
        stix_id = f"{stix_type}--{uuid4()}"
        value: str = str(node.get("value", ""))
        confidence: int = int(node.get("confidence", 50))

        base: dict[str, Any] = {
            "type": stix_type,
            "id": stix_id,
            "spec_version": "2.1",
            "created": now,
            "modified": now,
        }

        if stix_type == "ipv4-addr":
            base["value"] = value

        elif stix_type == "domain-name":
            base["value"] = value

        elif stix_type == "email-addr":
            base["value"] = value

        elif stix_type == "identity":
            identity_class = _IDENTITY_CLASS_MAP.get(raw_type, "unknown")
            base.update(
                {
                    "name": value,
                    "identity_class": identity_class,
                    "confidence": confidence,
                }
            )

        elif stix_type == "file":
            # Determine the most specific hash key from the node type or properties
            hash_key = _HASH_KEY_MAP.get(raw_type, "SHA-256")
            base["hashes"] = {hash_key: value}
            base["name"] = value  # optional but helpful

        elif stix_type == "vulnerability":
            # CVE IDs are stored in external_references per STIX spec
            base["name"] = value
            base["external_references"] = [
                {
                    "source_name": "cve",
                    "external_id": value,
                    "url": f"https://nvd.nist.gov/vuln/detail/{value}",
                }
            ]

        elif stix_type == "url":
            base["value"] = value

        elif stix_type == "malware":
            base.update(
                {
                    "name": value,
                    "is_family": False,
                    "malware_types": ["unknown"],
                    "confidence": confidence,
                }
            )

        elif stix_type == "threat-actor":
            base.update(
                {
                    "name": value,
                    "threat_actor_types": ["unknown"],
                    "confidence": confidence,
                }
            )

        return base

    # ------------------------------------------------------------------
    # Edge conversion
    # ------------------------------------------------------------------

    def _edge_to_stix_relationship(
        self,
        edge: dict[str, Any],
        from_stix_id: str,
        to_stix_id: str,
    ) -> dict[str, Any]:
        """Create a STIX Relationship SRO linking two STIX objects.

        The relationship_type is taken from the edge's relation_type field,
        falling back to "related-to" which is always valid in STIX 2.1.
        """
        now = self._now()
        relation_type: str = (
            edge.get("relation_type") or "related-to"
        ).lower().replace("_", "-").strip()

        return {
            "type": "relationship",
            "id": f"relationship--{uuid4()}",
            "spec_version": "2.1",
            "created": now,
            "modified": now,
            "relationship_type": relation_type,
            "source_ref": from_stix_id,
            "target_ref": to_stix_id,
        }

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def _make_report(
        self,
        investigation: dict[str, Any],
        object_refs: list[str],
    ) -> dict[str, Any]:
        """Create a STIX Report SDO that wraps all exported objects.

        The report acts as a container/index for the full investigation,
        analogous to a finished intelligence product.
        """
        now = self._now()
        created_at: str = investigation.get("created_at") or now
        # Normalise to string in case it is a datetime object
        if not isinstance(created_at, str):
            created_at = str(created_at)

        tags: list[str] = investigation.get("tags") or []

        return {
            "type": "report",
            "id": f"report--{uuid4()}",
            "spec_version": "2.1",
            "created": created_at,
            "modified": now,
            "name": investigation.get("name") or "OSINT Investigation",
            "description": investigation.get("description") or "",
            "report_types": ["threat-report"],
            "published": now,
            "object_refs": object_refs,
            "labels": tags,
            "external_references": [
                {
                    "source_name": "osint-platform",
                    "external_id": str(investigation.get("id", "")),
                }
            ],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _now(self) -> str:
        """Return current UTC time formatted as a STIX timestamp string."""
        return (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        )
