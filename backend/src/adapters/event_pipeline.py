"""Event-Driven Entity Pipeline — SpiderFoot-style pub/sub investigation engine.

Architecture overview:
    EntityEvent      — immutable payload: (entity_value, entity_type, source, depth)
    EventBus         — async publish/subscribe broker
    PipelineOrchestrator — wires the scanner registry to the bus

When a new entity is published on the bus, the orchestrator automatically finds
ALL registered scanners that understand that entity type and fires them
concurrently. Each scanner's output entities are re-published, creating a
self-driving investigation loop that terminates at max_depth.

This contrasts with MachineEngine which follows a fixed step sequence.
The pipeline is open-ended: you get depth-first breadth exploration of
every entity type the scanners can handle.

Usage::

    from src.adapters.event_pipeline import EventBus, PipelineOrchestrator, EntityEvent, EventType
    from src.adapters.scanners.registry import get_default_registry
    from src.core.domain.entities.types import ScanInputType

    bus = EventBus()
    orchestrator = PipelineOrchestrator(get_default_registry(), bus, max_depth=2)

    # Optional: subscribe a custom handler to scan completion events
    async def on_scan_done(event: EntityEvent) -> None:
        print(f"Scan complete: {event.source_scanner} → {event.entity_value}")

    bus.subscribe(EventType.SCAN_COMPLETED, on_scan_done)

    await orchestrator.start(
        seed_value="john.doe@example.com",
        seed_type=ScanInputType.EMAIL,
        investigation_id=uuid4(),
    )
    # Collect all discovered entities from bus event log
    entities = bus.get_events(EventType.ENTITY_DISCOVERED)
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Coroutine
from uuid import UUID, uuid4

import structlog

from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class EventType(StrEnum):
    ENTITY_DISCOVERED  = "entity.discovered"   # New entity found — triggers scanners
    ENTITY_ENRICHED    = "entity.enriched"      # Entity enriched with additional data
    SCAN_COMPLETED     = "scan.completed"        # A scanner finished successfully
    SCAN_FAILED        = "scan.failed"           # A scanner raised an exception
    RATE_LIMITED       = "scanner.rate_limited"  # A scanner was rate-limited
    PIPELINE_STARTED   = "pipeline.started"
    PIPELINE_COMPLETED = "pipeline.completed"


# ---------------------------------------------------------------------------
# EntityEvent
# ---------------------------------------------------------------------------


@dataclass
class EntityEvent:
    """Immutable event payload passed between the bus and subscribers."""

    event_type: EventType
    entity_value: str
    entity_input_type: ScanInputType
    investigation_id: UUID
    id: UUID = field(default_factory=uuid4)
    source_scanner: str = ""
    scan_data: dict[str, Any] = field(default_factory=dict)
    depth: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: __import__("time").monotonic())


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

AsyncHandler = Callable[[EntityEvent], Coroutine[Any, Any, None]]


class EventBus:
    """Async publish/subscribe event bus.

    Subscribers register for specific EventTypes. When an event is published,
    all matching handlers are invoked concurrently under a shared semaphore.
    """

    def __init__(self, max_handler_concurrency: int = 10) -> None:
        self._subscribers: dict[EventType, list[AsyncHandler]] = defaultdict(list)
        self._semaphore = asyncio.Semaphore(max_handler_concurrency)
        self._log: list[EntityEvent] = []

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def subscribe(self, event_type: EventType, handler: AsyncHandler) -> None:
        """Register an async handler for a specific EventType."""
        self._subscribers[event_type].append(handler)
        log.debug("Bus subscriber registered", event_type=event_type)

    def subscribe_all(self, handler: AsyncHandler) -> None:
        """Register an async handler for every EventType."""
        for et in EventType:
            self.subscribe(et, handler)

    def unsubscribe(self, event_type: EventType, handler: AsyncHandler) -> None:
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish(self, event: EntityEvent) -> None:
        """Publish an event and invoke all subscribers concurrently."""
        self._log.append(event)
        handlers = list(self._subscribers.get(event.event_type, []))
        if not handlers:
            return

        async def _invoke(handler: AsyncHandler) -> None:
            async with self._semaphore:
                try:
                    await handler(event)
                except Exception as exc:
                    log.error(
                        "Event handler raised exception",
                        event_type=event.event_type,
                        handler=getattr(handler, "__name__", repr(handler)),
                        error=str(exc),
                    )

        await asyncio.gather(*(_invoke(h) for h in handlers), return_exceptions=True)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def get_events(self, event_type: EventType | None = None) -> list[EntityEvent]:
        if event_type is None:
            return list(self._log)
        return [e for e in self._log if e.event_type == event_type]

    @property
    def event_count(self) -> int:
        return len(self._log)

    def summary(self) -> dict[str, int]:
        """Return per-EventType counts for the full log."""
        counts: dict[str, int] = defaultdict(int)
        for event in self._log:
            counts[event.event_type] += 1
        return dict(counts)


# ---------------------------------------------------------------------------
# Identifier type mapping
# ---------------------------------------------------------------------------

_PREFIX_MAP: dict[str, ScanInputType] = {
    "domain":   ScanInputType.DOMAIN,
    "ip":       ScanInputType.IP_ADDRESS,
    "email":    ScanInputType.EMAIL,
    "username": ScanInputType.USERNAME,
    "url":      ScanInputType.URL,
    "phone":    ScanInputType.PHONE,
}


def _parse_identifier(identifier: str) -> tuple[ScanInputType, str] | None:
    """Parse "prefix:value" → (ScanInputType, value) or None if unknown prefix."""
    if ":" not in identifier:
        return None
    prefix, _, value = identifier.partition(":")
    mapped = _PREFIX_MAP.get(prefix.lower())
    return (mapped, value) if mapped and value else None


# ---------------------------------------------------------------------------
# Pipeline Orchestrator
# ---------------------------------------------------------------------------


class PipelineOrchestrator:
    """Wires the scanner registry to the event bus.

    On ENTITY_DISCOVERED events the orchestrator:
    1. Deduplicates the entity (global seen set).
    2. Enforces per-type entity caps to prevent runaway expansion.
    3. Fires all scanners that support the entity type concurrently.
    4. Publishes SCAN_COMPLETED / ENTITY_DISCOVERED events for each result.

    The feedback loop terminates when:
    - max_depth is reached for a chain of entities, OR
    - max_entities_per_type cap is hit, OR
    - No scanner accepts the current entity type.
    """

    def __init__(
        self,
        registry: Any,                  # ScannerRegistry
        bus: EventBus,
        max_depth: int = 2,
        max_entities_per_type: int = 30,
        scanner_concurrency: int = 5,
    ) -> None:
        self._registry = registry
        self._bus = bus
        self._max_depth = max_depth
        self._max_entities_per_type = max_entities_per_type
        self._scan_semaphore = asyncio.Semaphore(scanner_concurrency)
        self._seen: set[str] = set()
        self._entity_counts: dict[ScanInputType, int] = defaultdict(int)

        # Wire the discovery handler
        bus.subscribe(EventType.ENTITY_DISCOVERED, self._on_entity_discovered)

    async def start(
        self,
        seed_value: str,
        seed_type: ScanInputType,
        investigation_id: UUID,
    ) -> None:
        """Seed the pipeline and let it run to completion."""
        await self._bus.publish(EntityEvent(
            event_type=EventType.PIPELINE_STARTED,
            entity_value=seed_value,
            entity_input_type=seed_type,
            investigation_id=investigation_id,
        ))
        # Seed the discovery event
        await self._bus.publish(EntityEvent(
            event_type=EventType.ENTITY_DISCOVERED,
            entity_value=seed_value,
            entity_input_type=seed_type,
            investigation_id=investigation_id,
            depth=0,
        ))
        # Signal completion (pipeline is async so this fires after initial wave)
        await self._bus.publish(EntityEvent(
            event_type=EventType.PIPELINE_COMPLETED,
            entity_value=seed_value,
            entity_input_type=seed_type,
            investigation_id=investigation_id,
        ))

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    async def _on_entity_discovered(self, event: EntityEvent) -> None:
        """Triggered for every ENTITY_DISCOVERED event on the bus."""
        dedup_key = f"{event.entity_input_type}:{event.entity_value}"

        if dedup_key in self._seen:
            return
        if event.depth >= self._max_depth:
            log.debug("Max depth reached", depth=event.depth, entity=event.entity_value)
            return
        if self._entity_counts[event.entity_input_type] >= self._max_entities_per_type:
            log.warning(
                "Entity type cap reached",
                input_type=event.entity_input_type,
                cap=self._max_entities_per_type,
            )
            return

        self._seen.add(dedup_key)
        self._entity_counts[event.entity_input_type] += 1

        scanners = self._registry.get_for_input_type(event.entity_input_type)
        if not scanners:
            return

        log.info(
            "Pipeline dispatching",
            entity=event.entity_value,
            type=event.entity_input_type,
            scanners=[s.scanner_name for s in scanners],
            depth=event.depth,
        )

        await asyncio.gather(
            *(self._run_scanner(scanner, event) for scanner in scanners),
            return_exceptions=True,
        )

    async def _run_scanner(self, scanner: Any, event: EntityEvent) -> None:
        """Run a single scanner and re-publish resulting entities."""
        async with self._scan_semaphore:
            try:
                scan_result = await scanner.scan(
                    event.entity_value,
                    event.entity_input_type,
                    event.investigation_id,
                )

                await self._bus.publish(EntityEvent(
                    event_type=EventType.SCAN_COMPLETED,
                    entity_value=event.entity_value,
                    entity_input_type=event.entity_input_type,
                    investigation_id=event.investigation_id,
                    source_scanner=scanner.scanner_name,
                    scan_data=scan_result.raw_data,
                    depth=event.depth,
                ))

                # Publish each extracted identifier as a new entity event
                for identifier in scan_result.extracted_identifiers or []:
                    parsed = _parse_identifier(identifier)
                    if parsed is None:
                        continue
                    mapped_type, id_value = parsed

                    await self._bus.publish(EntityEvent(
                        event_type=EventType.ENTITY_DISCOVERED,
                        entity_value=id_value,
                        entity_input_type=mapped_type,
                        investigation_id=event.investigation_id,
                        source_scanner=scanner.scanner_name,
                        depth=event.depth + 1,
                    ))

            except Exception as exc:
                log.error(
                    "Scanner error in pipeline",
                    scanner=scanner.scanner_name,
                    entity=event.entity_value,
                    error=str(exc),
                )
                await self._bus.publish(EntityEvent(
                    event_type=EventType.SCAN_FAILED,
                    entity_value=event.entity_value,
                    entity_input_type=event.entity_input_type,
                    investigation_id=event.investigation_id,
                    source_scanner=scanner.scanner_name,
                    metadata={"error": str(exc)},
                    depth=event.depth,
                ))
