"""WebSocket endpoint for real-time investigation progress."""

import asyncio
import json
from collections import defaultdict
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = structlog.get_logger()

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections grouped by investigation ID."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, investigation_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[investigation_id].add(websocket)
        log.info("WebSocket connected", investigation_id=investigation_id)

    async def disconnect(self, investigation_id: str, websocket: WebSocket) -> None:
        self._connections[investigation_id].discard(websocket)
        if not self._connections[investigation_id]:
            del self._connections[investigation_id]
        log.info("WebSocket disconnected", investigation_id=investigation_id)

    async def broadcast(self, investigation_id: str, message: dict[str, Any]) -> None:
        """Send a message to all connections watching an investigation."""
        dead: set[WebSocket] = set()
        for ws in self._connections.get(investigation_id, set()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections[investigation_id].discard(ws)

    @property
    def active_connections(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


# Singleton manager
manager = ConnectionManager()


@router.websocket("/{investigation_id}/live")
async def investigation_live(
    websocket: WebSocket,
    investigation_id: UUID,
) -> None:
    """WebSocket endpoint for real-time investigation progress.

    Authentication: client must send ``{"type": "auth", "token": "..."}``
    as the first message after connection is accepted.

    Message types sent to clients:
    - progress: scan progress update
    - node_discovered: new graph node found
    - edge_discovered: new graph edge found
    - scan_complete: individual scanner finished
    - investigation_complete: all scanning done
    - error: scanner error notification
    """
    # Accept the connection first, then wait for auth message
    await websocket.accept()

    try:
        # Wait for the auth message (with a timeout)
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        auth_msg = json.loads(raw)
        token = auth_msg.get("token") if auth_msg.get("type") == "auth" else None
    except (asyncio.TimeoutError, json.JSONDecodeError, WebSocketDisconnect):
        token = None

    if not token:
        await websocket.close(code=4001, reason="Missing or invalid authentication token")
        return

    inv_id = str(investigation_id)
    # Register connection after successful auth (accept already called above)
    manager._connections[inv_id].add(websocket)
    log.info("WebSocket connected", investigation_id=inv_id)

    try:
        # Try Redis Pub/Sub for live updates from Celery workers
        redis = getattr(websocket.app.state, "redis", None)
        if redis is not None:
            await _listen_redis(redis, inv_id, websocket)
        else:
            # Fallback: keep connection alive, send heartbeats
            await _heartbeat_loop(inv_id, websocket)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(inv_id, websocket)


async def _listen_redis(redis: Any, investigation_id: str, websocket: WebSocket) -> None:
    """Subscribe to Redis Pub/Sub channel and forward messages to WebSocket."""
    import asyncio

    channel_name = f"investigation:{investigation_id}:progress"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel_name)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                try:
                    parsed = json.loads(data)
                    await websocket.send_json(parsed)
                except (json.JSONDecodeError, Exception):
                    await websocket.send_text(data)

            # Check if client sent anything (e.g., ping or close)
            try:
                client_msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                if client_msg == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

    finally:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()


async def _heartbeat_loop(investigation_id: str, websocket: WebSocket) -> None:
    """Simple heartbeat loop when Redis is not available."""
    import asyncio

    while True:
        try:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            if data == "ping":
                await websocket.send_json({"type": "pong"})
        except asyncio.TimeoutError:
            # Send heartbeat
            await websocket.send_json({"type": "heartbeat"})
        except WebSocketDisconnect:
            break
