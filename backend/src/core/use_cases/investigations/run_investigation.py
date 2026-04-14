"""Use case: orchestrate an OSINT investigation pipeline."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import structlog

from src.core.domain.entities.types import InvestigationStatus, ScanInputType
from src.core.domain.events.investigation import InvestigationStatusChanged
from src.core.ports.event_publisher import IEventPublisher
from src.core.ports.repositories import IInvestigationRepository

log = structlog.get_logger()

# Maximum recursion depth for following discovered identifiers
MAX_SCAN_DEPTH = 3


@dataclass
class RunInvestigationCommand:
    investigation_id: UUID
    max_depth: int = MAX_SCAN_DEPTH


class RunInvestigationUseCase:
    """Starts the scanning pipeline for an investigation.

    This use case validates the investigation state, marks it as RUNNING,
    and dispatches the Celery pipeline. The actual scanning is async.
    """

    def __init__(
        self,
        investigation_repo: IInvestigationRepository,
        event_publisher: IEventPublisher,
    ) -> None:
        self._investigation_repo = investigation_repo
        self._event_publisher = event_publisher

    async def execute(self, command: RunInvestigationCommand) -> None:
        investigation = await self._investigation_repo.get_by_id(command.investigation_id)
        if investigation is None:
            raise ValueError(f"Investigation {command.investigation_id} not found")

        if investigation.status not in {InvestigationStatus.DRAFT, InvestigationStatus.PAUSED}:
            raise ValueError(f"Investigation cannot be started from status {investigation.status}")

        # Mark as running
        running = investigation.mark_running()
        await self._investigation_repo.save(running)

        # Publish status change event
        await self._event_publisher.publish(
            InvestigationStatusChanged(
                investigation_id=investigation.id,
                old_status=investigation.status.value,
                new_status=InvestigationStatus.RUNNING.value,
            )
        )

        # Dispatch Celery pipeline
        from src.workers.tasks.investigation_tasks import run_investigation_task
        run_investigation_task.delay(str(command.investigation_id))

        log.info(
            "Investigation pipeline dispatched",
            investigation_id=str(command.investigation_id),
            seed_count=len(running.seed_inputs),
        )
