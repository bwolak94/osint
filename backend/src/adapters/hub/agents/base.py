"""Protocol definition for Hub agent node functions.

Every agent must accept (state, **kwargs) and return a partial HubState dict.
This enforces SOLID Interface Segregation — the graph only cares about the contract.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.adapters.hub.state import HubState


class AgentFn(Protocol):
    """Callable protocol every agent node must satisfy."""

    async def __call__(self, state: HubState, **kwargs: Any) -> dict[str, Any]: ...
