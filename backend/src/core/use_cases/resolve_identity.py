"""Use case: resolve an identity through OSINT scanning."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog

from src.core.ports.graph_store import IGraphStore
from src.core.ports.osint_scanner import IOsintScanner

log = structlog.get_logger()


@dataclass
class ResolveIdentityInput:
    """Input DTO for resolving an identity."""

    identity_id: UUID
    query: str
    depth: int = 2


class ResolveIdentity:
    """Orchestrates an OSINT lookup and stores results in the graph."""

    def __init__(self, scanner: IOsintScanner, graph: IGraphStore) -> None:
        self._scanner = scanner
        self._graph = graph

    async def execute(self, data: ResolveIdentityInput) -> dict[str, Any]:
        """Run the scan and populate the graph with findings."""
        log.info("Starting identity resolution", identity_id=str(data.identity_id), query=data.query)

        # Perform the OSINT scan
        scan_results = await self._scanner.scan(
            identity_id=data.identity_id,
            query=data.query,
            depth=data.depth,
        )

        # Store the root node in the graph
        await self._graph.add_node(
            node_id=data.identity_id,
            labels=["Identity"],
            properties={"query": data.query, "scan_depth": data.depth},
        )

        # Store any discovered related nodes and edges
        for node in scan_results.get("nodes", []):
            await self._graph.add_node(
                node_id=node["id"],
                labels=node.get("labels", ["Unknown"]),
                properties=node.get("properties", {}),
            )
            await self._graph.add_edge(
                source_id=data.identity_id,
                target_id=node["id"],
                relationship=node.get("relationship", "RELATED_TO"),
            )

        log.info(
            "Identity resolution complete",
            identity_id=str(data.identity_id),
            nodes_found=len(scan_results.get("nodes", [])),
        )

        return scan_results
