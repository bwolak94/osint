"""Publishes scan progress to Redis Pub/Sub for WebSocket consumers."""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog

log = structlog.get_logger()


class ProgressPublisher:
    """Publishes investigation progress events to Redis Pub/Sub.

    Used by Celery workers to notify WebSocket connections of scan progress.
    """

    def __init__(self, redis: Any) -> None:
        self._redis = redis

    def _channel(self, investigation_id: UUID) -> str:
        return f"investigation:{investigation_id}:progress"

    async def publish_progress(
        self, investigation_id: UUID, completed: int, total: int, current_scanner: str | None = None
    ) -> None:
        percentage = (completed / total * 100) if total > 0 else 0.0
        await self._publish(investigation_id, {
            "type": "progress",
            "completed": completed,
            "total": total,
            "percentage": round(percentage, 1),
            "current_scanner": current_scanner,
        })

    async def publish_node_discovered(
        self, investigation_id: UUID, node_id: str, node_type: str, label: str
    ) -> None:
        await self._publish(investigation_id, {
            "type": "node_discovered",
            "node": {"id": node_id, "type": node_type, "label": label},
        })

    async def publish_edge_discovered(
        self, investigation_id: UUID, source: str, target: str, rel_type: str
    ) -> None:
        await self._publish(investigation_id, {
            "type": "edge_discovered",
            "edge": {"source": source, "target": target, "type": rel_type},
        })

    async def publish_scan_complete(
        self, investigation_id: UUID, scanner: str, findings_count: int
    ) -> None:
        await self._publish(investigation_id, {
            "type": "scan_complete",
            "scanner": scanner,
            "findings_count": findings_count,
        })

    async def publish_investigation_complete(
        self, investigation_id: UUID, summary: dict[str, Any]
    ) -> None:
        await self._publish(investigation_id, {
            "type": "investigation_complete",
            "summary": summary,
        })

    async def publish_error(
        self, investigation_id: UUID, scanner: str, message: str
    ) -> None:
        await self._publish(investigation_id, {
            "type": "error",
            "scanner": scanner,
            "message": message,
        })

    async def _publish(self, investigation_id: UUID, data: dict[str, Any]) -> None:
        channel = self._channel(investigation_id)
        payload = {
            **data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self._redis.publish(channel, json.dumps(payload, default=str))
        except Exception as exc:
            log.warning("Failed to publish progress", channel=channel, error=str(exc))
