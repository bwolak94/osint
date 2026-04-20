"""Machine Engine — automated transform chaining for OSINT investigations.

A Machine is a pre-defined sequence of transforms (scanners) where the output
entities of one step feed the input of the next, building an investigation graph
automatically from a single seed entity.

Architecture:
    MachineStep      — binds a scanner to an expected input type + output filter
    Machine          — ordered list of steps with depth / dedup controls
    MachineEngine    — executes a machine against a scanner registry
    BUILTIN_MACHINES — four ready-made investigation playbooks

Example usage::

    from src.adapters.machine_engine import MachineEngine, INFRASTRUCTURE_FOOTPRINT
    from src.adapters.scanners.registry import get_default_registry
    from src.core.domain.entities.types import ScanInputType

    engine = MachineEngine(get_default_registry())
    result = await engine.run(
        machine=INFRASTRUCTURE_FOOTPRINT,
        seed_value="example.com",
        seed_type=ScanInputType.DOMAIN,
    )
    print(result.entities_discovered)
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

from src.core.domain.entities.types import ScanInputType

if TYPE_CHECKING:
    from src.adapters.scanners.base import BaseOsintScanner
    from src.adapters.scanners.registry import ScannerRegistry

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Machine definition primitives
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MachineStep:
    """A single transform step within a Machine.

    Attributes:
        scanner_name:  Registered scanner name (e.g. "shodan", "dns_bruteforce").
        input_type:    ScanInputType the scanner consumes.
        label:         Human-readable description for logs/UI.
        filter_prefix: When set, only pass identifiers starting with this prefix
                       (e.g. "domain:" or "ip:") to the next step.
                       None means pass all extracted identifiers.
    """

    scanner_name: str
    input_type: ScanInputType
    label: str = ""
    filter_prefix: str | None = None


@dataclass
class Machine:
    """An ordered pipeline of OSINT transforms.

    Attributes:
        name:           Machine identifier (used for registry lookups).
        description:    One-line description shown in UI.
        steps:          Ordered list of MachineStep objects.
        max_depth:      Maximum number of transform levels to execute.
        deduplicate:    Skip entities already seen in this run.
        step_delay_s:   Optional pause between steps to avoid rate-limiting.
    """

    name: str
    description: str
    steps: list[MachineStep]
    max_depth: int = 3
    deduplicate: bool = True
    step_delay_s: float = 0.0


@dataclass
class DiscoveredEntity:
    """A single entity found during machine execution."""

    value: str
    type_prefix: str  # e.g. "domain", "ip", "username"
    source_scanner: str
    depth: int
    scan_input_type: ScanInputType

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "type": self.type_prefix,
            "source_scanner": self.source_scanner,
            "depth": self.depth,
        }


@dataclass
class MachineResult:
    """Accumulated output from a complete machine execution."""

    machine_name: str
    investigation_id: UUID | None
    seed_value: str
    seed_type: ScanInputType
    entities_discovered: list[DiscoveredEntity] = field(default_factory=list)
    scan_log: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    total_steps_run: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "machine_name": self.machine_name,
            "investigation_id": str(self.investigation_id) if self.investigation_id else None,
            "seed_value": self.seed_value,
            "seed_type": self.seed_type,
            "entities_discovered": [e.to_dict() for e in self.entities_discovered],
            "scan_log": self.scan_log,
            "errors": self.errors,
            "total_steps_run": self.total_steps_run,
        }


# ---------------------------------------------------------------------------
# Built-in machines
# ---------------------------------------------------------------------------

INFRASTRUCTURE_FOOTPRINT = Machine(
    name="infrastructure_footprint",
    description="Domain → subdomains → DNS brute-force → IPs → Shodan → CVEs → GeoIP",
    steps=[
        MachineStep("subdomain",      ScanInputType.DOMAIN,     "Enumerate subdomains (passive)",  "domain:"),
        MachineStep("dns_bruteforce", ScanInputType.DOMAIN,     "DNS brute-force (active)",        "domain:"),
        MachineStep("cert_transparency", ScanInputType.DOMAIN,  "Certificate transparency logs",   "domain:"),
        MachineStep("dns",            ScanInputType.DOMAIN,     "Resolve A/MX/NS/TXT records",     "ip:"),
        MachineStep("whois",          ScanInputType.DOMAIN,     "WHOIS registration data"),
        MachineStep("tracking_codes", ScanInputType.DOMAIN,     "Tracking code pivot",             "domain:"),
        MachineStep("shodan",         ScanInputType.IP_ADDRESS, "Shodan port/banner/CVE scan",     "vuln:"),
        MachineStep("virustotal",     ScanInputType.IP_ADDRESS, "VirusTotal reputation"),
        MachineStep("geoip",          ScanInputType.IP_ADDRESS, "Geolocate discovered IPs"),
        MachineStep("asn",            ScanInputType.IP_ADDRESS, "ASN / BGP prefix data"),
    ],
    max_depth=3,
)

EMAIL_TO_IDENTITY = Machine(
    name="email_to_identity",
    description="Email → breach check → social presence → username pivot → profile enrichment",
    steps=[
        MachineStep("breach",        ScanInputType.EMAIL,    "Data breach lookup (HIBP)"),
        MachineStep("holehe",        ScanInputType.EMAIL,    "Social platform registration check", "username:"),
        MachineStep("google_account", ScanInputType.EMAIL,   "Google account linkage"),
        MachineStep("github",        ScanInputType.EMAIL,    "GitHub account search",              "username:"),
        MachineStep("maigret",       ScanInputType.USERNAME, "Cross-platform username search"),
        MachineStep("linkedin",      ScanInputType.USERNAME, "LinkedIn profile lookup"),
        MachineStep("twitter",       ScanInputType.USERNAME, "X/Twitter profile lookup"),
        MachineStep("instagram",     ScanInputType.USERNAME, "Instagram profile lookup"),
    ],
    max_depth=2,
)

THREAT_INTEL_PIVOT = Machine(
    name="threat_intel_pivot",
    description="IP/Domain → VirusTotal → Shodan → ASN → related infrastructure pivot",
    steps=[
        MachineStep("virustotal",       ScanInputType.IP_ADDRESS, "VirusTotal threat analysis",  "threat:"),
        MachineStep("shodan",           ScanInputType.IP_ADDRESS, "Shodan host intelligence",    "domain:"),
        MachineStep("asn",              ScanInputType.IP_ADDRESS, "ASN / netblock mapping"),
        MachineStep("cert_transparency",ScanInputType.DOMAIN,     "Certificate linkage",         "domain:"),
        MachineStep("tracking_codes",   ScanInputType.DOMAIN,     "Tracking code pivot",         "domain:"),
        MachineStep("subdomain",        ScanInputType.DOMAIN,     "Passive subdomain enum",      "domain:"),
    ],
    max_depth=3,
)

DOCUMENT_ATTRIBUTION = Machine(
    name="document_attribution",
    description="URL (PDF/image) → metadata extraction → username pivot → social/infra enrichment",
    steps=[
        MachineStep("metadata_extractor", ScanInputType.URL,      "Extract EXIF / PDF metadata", "username:"),
        MachineStep("maigret",            ScanInputType.USERNAME, "Cross-platform username scan"),
        MachineStep("github",             ScanInputType.USERNAME, "GitHub profile search"),
        MachineStep("linkedin",           ScanInputType.USERNAME, "LinkedIn profile search"),
        MachineStep("twitter",            ScanInputType.USERNAME, "X/Twitter search"),
    ],
    max_depth=2,
)

BUILTIN_MACHINES: dict[str, Machine] = {
    m.name: m for m in [
        INFRASTRUCTURE_FOOTPRINT,
        EMAIL_TO_IDENTITY,
        THREAT_INTEL_PIVOT,
        DOCUMENT_ATTRIBUTION,
    ]
}

# ---------------------------------------------------------------------------
# Identifier-type mapping (prefix → ScanInputType)
# ---------------------------------------------------------------------------

_PREFIX_TO_INPUT_TYPE: dict[str, ScanInputType] = {
    "domain":   ScanInputType.DOMAIN,
    "ip":       ScanInputType.IP_ADDRESS,
    "email":    ScanInputType.EMAIL,
    "username": ScanInputType.USERNAME,
    "url":      ScanInputType.URL,
    "phone":    ScanInputType.PHONE,
}


def _parse_identifier(identifier: str) -> tuple[str, str] | None:
    """Parse "prefix:value" identifiers. Return (prefix, value) or None."""
    if ":" not in identifier:
        return None
    prefix, _, value = identifier.partition(":")
    return (prefix.lower(), value) if value else None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class MachineEngine:
    """Executes a Machine by chaining transforms and feeding outputs as new inputs.

    Execution model (BFS with step index):
    - Maintain a queue of (entity_value, input_type, depth, next_step_index).
    - For each queue entry, run the scanner at steps[step_index].
    - Collect extracted identifiers, filter by step.filter_prefix.
    - Map identifiers to ScanInputType and enqueue at depth+1, step_index+1.
    - Continue until queue exhausted or max_depth reached.
    """

    def __init__(self, registry: ScannerRegistry) -> None:
        self._registry = registry

    async def run(
        self,
        machine: Machine,
        seed_value: str,
        seed_type: ScanInputType,
        investigation_id: UUID | None = None,
    ) -> MachineResult:
        """Execute a machine synchronously (collect all results before returning)."""
        result = MachineResult(
            machine_name=machine.name,
            investigation_id=investigation_id,
            seed_value=seed_value,
            seed_type=seed_type,
        )
        seen: set[str] = {f"{seed_type}:{seed_value}"}

        # Queue entries: (value, input_type, depth, step_index)
        queue: list[tuple[str, ScanInputType, int, int]] = [
            (seed_value, seed_type, 0, 0)
        ]

        while queue:
            value, current_type, depth, step_idx = queue.pop(0)

            if depth >= machine.max_depth or step_idx >= len(machine.steps):
                continue

            step = machine.steps[step_idx]
            scanner = self._registry.get_by_name(step.scanner_name)

            if scanner is None:
                msg = f"Scanner '{step.scanner_name}' not registered"
                result.errors.append(msg)
                log.warning(msg, machine=machine.name)
                continue

            if not scanner.supports(current_type):
                continue

            log.info(
                "Machine step",
                machine=machine.name,
                step=step.label or step.scanner_name,
                value=value,
                depth=depth,
            )

            new_entities = await self._execute_step(
                scanner=scanner,
                step=step,
                value=value,
                current_type=current_type,
                depth=depth,
                investigation_id=investigation_id,
                result=result,
            )

            if machine.step_delay_s > 0:
                await asyncio.sleep(machine.step_delay_s)

            # Enqueue next step for newly discovered entities
            for entity in new_entities:
                dedup_key = f"{entity.scan_input_type}:{entity.value}"
                if machine.deduplicate and dedup_key in seen:
                    continue
                seen.add(dedup_key)
                result.entities_discovered.append(entity)

                if step_idx + 1 < len(machine.steps):
                    queue.append((entity.value, entity.scan_input_type, depth + 1, step_idx + 1))

        log.info(
            "Machine complete",
            machine=machine.name,
            entities=len(result.entities_discovered),
            steps_run=result.total_steps_run,
            errors=len(result.errors),
        )
        return result

    async def stream(
        self,
        machine: Machine,
        seed_value: str,
        seed_type: ScanInputType,
        investigation_id: UUID | None = None,
    ) -> AsyncGenerator[DiscoveredEntity, None]:
        """Stream discovered entities one-by-one as they are produced."""
        # Simplified: run to completion and yield. A true streaming version
        # would use asyncio.Queue and yield from the queue in real-time.
        result = await self.run(machine, seed_value, seed_type, investigation_id)
        for entity in result.entities_discovered:
            yield entity

    async def _execute_step(
        self,
        scanner: BaseOsintScanner,
        step: MachineStep,
        value: str,
        current_type: ScanInputType,
        depth: int,
        investigation_id: UUID | None,
        result: MachineResult,
    ) -> list[DiscoveredEntity]:
        """Run one scanner step and return new entities."""
        try:
            scan_result = await scanner.scan(value, current_type, investigation_id)
            result.total_steps_run += 1
            result.scan_log.append({
                "scanner": step.scanner_name,
                "input": value,
                "status": scan_result.status,
                "depth": depth,
                "findings": len(scan_result.extracted_identifiers or []),
            })

            identifiers = scan_result.extracted_identifiers or []

            # Apply output filter
            if step.filter_prefix:
                identifiers = [i for i in identifiers if i.startswith(step.filter_prefix)]

            entities: list[DiscoveredEntity] = []
            for identifier in identifiers:
                parsed = _parse_identifier(identifier)
                if parsed is None:
                    continue
                prefix, id_value = parsed
                mapped_type = _PREFIX_TO_INPUT_TYPE.get(prefix)
                if mapped_type is None:
                    continue
                entities.append(DiscoveredEntity(
                    value=id_value,
                    type_prefix=prefix,
                    source_scanner=step.scanner_name,
                    depth=depth + 1,
                    scan_input_type=mapped_type,
                ))
            return entities

        except Exception as exc:
            error_msg = f"Step '{step.scanner_name}' on '{value}': {exc}"
            result.errors.append(error_msg)
            log.error("Machine step error", scanner=step.scanner_name, value=value, error=str(exc))
            return []
