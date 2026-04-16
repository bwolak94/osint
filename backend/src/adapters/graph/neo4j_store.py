"""Neo4j implementation of the graph repository port."""

from typing import Any
from uuid import UUID, uuid4

import structlog
from neo4j import AsyncDriver

from src.core.domain.entities.graph_edge import GraphEdge
from src.core.domain.entities.graph_node import GraphNode
from src.core.domain.entities.types import NodeType, RelationshipType
from src.core.domain.value_objects.confidence_score import ConfidenceScore

log = structlog.get_logger()


class Neo4jGraphRepository:
    """Graph repository backed by Neo4j.

    Uses MERGE queries for idempotent node/edge creation.
    Node uniqueness key: (investigation_id, node_type, label_normalized).
    """

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def add_node(self, node: GraphNode) -> GraphNode:
        """Create or update a node using MERGE for deduplication."""
        label_normalized = node.label.strip().lower()
        query = """
        MERGE (n:OsintNode {
            investigation_id: $investigation_id,
            node_type: $node_type,
            label_normalized: $label_normalized
        })
        ON CREATE SET
            n.id = $id,
            n.label = $label,
            n.confidence = $confidence,
            n.sources = $sources,
            n.properties = $properties,
            n.created_at = datetime()
        ON MATCH SET
            n.confidence = CASE WHEN $confidence > n.confidence THEN $confidence ELSE n.confidence END,
            n.sources = [x IN n.sources + $sources WHERE x IS NOT NULL | x],
            n.updated_at = datetime()
        RETURN n.id as id
        """
        params = {
            "id": str(node.id),
            "investigation_id": str(node.investigation_id),
            "node_type": node.node_type.value,
            "label": node.label,
            "label_normalized": label_normalized,
            "confidence": float(node.confidence_score.value),
            "sources": list(node.sources),
            "properties": node.properties,
        }
        async with self._driver.session() as session:
            result = await session.run(query, params)
            await result.consume()
        return node

    async def add_edge(self, edge: GraphEdge) -> GraphEdge:
        """Create a directed relationship between two nodes."""
        query = """
        MATCH (a:OsintNode {id: $source_id})
        MATCH (b:OsintNode {id: $target_id})
        MERGE (a)-[r:OSINT_RELATION {relationship_type: $rel_type}]->(b)
        ON CREATE SET
            r.id = $id,
            r.confidence = $confidence,
            r.valid_from = $valid_from,
            r.valid_to = $valid_to,
            r.metadata = $metadata,
            r.created_at = datetime()
        RETURN r.id as id
        """
        params = {
            "id": str(edge.id),
            "source_id": str(edge.source_node_id),
            "target_id": str(edge.target_node_id),
            "rel_type": edge.relationship_type.value,
            "confidence": float(edge.confidence_score.value),
            "valid_from": edge.valid_from.isoformat() if edge.valid_from else None,
            "valid_to": edge.valid_to.isoformat() if edge.valid_to else None,
            "metadata": edge.metadata,
        }
        async with self._driver.session() as session:
            result = await session.run(query, params)
            await result.consume()
        return edge

    async def get_subgraph(
        self, investigation_id: UUID, depth: int = 3
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Retrieve the full subgraph for an investigation up to given depth."""
        clamped_depth = min(depth, 5)

        node_query = """
        MATCH (n:OsintNode {investigation_id: $investigation_id})
        RETURN n.id AS id, n.node_type AS node_type, n.label AS label,
               n.confidence AS confidence, n.sources AS sources,
               n.properties AS properties
        """
        edge_query = (
            "MATCH (a:OsintNode {investigation_id: $investigation_id})"
            "-[r:OSINT_RELATION]->"
            "(b:OsintNode {investigation_id: $investigation_id})"
            " RETURN r.id AS id, a.id AS source_id, b.id AS target_id,"
            " r.relationship_type AS rel_type, r.confidence AS confidence,"
            " r.valid_from AS valid_from, r.valid_to AS valid_to,"
            " r.metadata AS metadata"
        )

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        async with self._driver.session() as session:
            # Fetch nodes
            result = await session.run(
                node_query, {"investigation_id": str(investigation_id)}
            )
            async for record in result:
                from datetime import datetime, timezone

                nodes.append(
                    GraphNode(
                        id=UUID(record["id"]) if record["id"] else uuid4(),
                        investigation_id=investigation_id,
                        node_type=(
                            NodeType(record["node_type"])
                            if record["node_type"]
                            else NodeType.PERSON
                        ),
                        label=record["label"] or "",
                        properties=(
                            dict(record["properties"])
                            if record["properties"]
                            else {}
                        ),
                        confidence_score=ConfidenceScore(
                            record["confidence"] or 0.0
                        ),
                        sources=frozenset(record["sources"] or []),
                        created_at=datetime.now(timezone.utc),
                    )
                )

            # Fetch edges
            result = await session.run(
                edge_query, {"investigation_id": str(investigation_id)}
            )
            async for record in result:
                from datetime import datetime, timezone

                edges.append(
                    GraphEdge(
                        id=UUID(record["id"]) if record["id"] else uuid4(),
                        source_node_id=UUID(record["source_id"]),
                        target_node_id=UUID(record["target_id"]),
                        relationship_type=(
                            RelationshipType(record["rel_type"])
                            if record["rel_type"]
                            else RelationshipType.CONNECTED_TO
                        ),
                        confidence_score=ConfidenceScore(
                            record["confidence"] or 0.0
                        ),
                        metadata=(
                            dict(record["metadata"])
                            if record["metadata"]
                            else {}
                        ),
                        created_at=datetime.now(timezone.utc),
                    )
                )

        return nodes, edges

    async def find_paths(
        self, source_id: UUID, target_id: UUID, max_depth: int = 5
    ) -> list[list[GraphNode]]:
        """Find shortest paths between two nodes using Neo4j shortestPath."""
        clamped = min(max(max_depth, 1), 10)  # Clamp to safe range
        query = f"""
        MATCH (source:OsintNode {{id: $source_id}}),
              (target:OsintNode {{id: $target_id}})
        MATCH path = shortestPath((source)-[:OSINT_RELATION*..{clamped}]-(target))
        RETURN [node IN nodes(path) | {{
            id: node.id, node_type: node.node_type, label: node.label, confidence: node.confidence
        }}] AS path_nodes
        LIMIT 5
        """
        paths: list[list[GraphNode]] = []
        async with self._driver.session() as session:
            result = await session.run(
                query,
                {
                    "source_id": str(source_id),
                    "target_id": str(target_id),
                },
            )
            async for record in result:
                path_nodes = []
                for n in record["path_nodes"]:
                    from datetime import datetime, timezone

                    path_nodes.append(
                        GraphNode(
                            id=UUID(n["id"]) if n["id"] else uuid4(),
                            investigation_id=uuid4(),  # Not available from path query
                            node_type=(
                                NodeType(n["node_type"])
                                if n.get("node_type")
                                else NodeType.PERSON
                            ),
                            label=n.get("label", ""),
                            properties={},
                            confidence_score=ConfidenceScore(
                                n.get("confidence", 0.0)
                            ),
                            sources=frozenset(),
                            created_at=datetime.now(timezone.utc),
                        )
                    )
                paths.append(path_nodes)

        return paths

    async def get_statistics(self, investigation_id: UUID) -> dict[str, Any]:
        """Return graph statistics: node count, edge count, average degree."""
        query = """
        MATCH (n:OsintNode {investigation_id: $investigation_id})
        OPTIONAL MATCH (n)-[r:OSINT_RELATION]-()
        WITH count(DISTINCT n) AS node_count, count(r) AS edge_count
        RETURN node_count, edge_count,
               CASE WHEN node_count > 0 THEN toFloat(edge_count) / node_count ELSE 0.0 END AS avg_degree
        """
        async with self._driver.session() as session:
            result = await session.run(
                query, {"investigation_id": str(investigation_id)}
            )
            record = await result.single()
            if record:
                return {
                    "node_count": record["node_count"],
                    "edge_count": record["edge_count"],
                    "avg_degree": record["avg_degree"],
                }
            return {"node_count": 0, "edge_count": 0, "avg_degree": 0.0}

    async def delete_node(self, node_id: UUID) -> None:
        """Delete a node and all its relationships."""
        query = "MATCH (n:OsintNode {id: $id}) DETACH DELETE n"
        async with self._driver.session() as session:
            await session.run(query, {"id": str(node_id)})

    async def close(self) -> None:
        await self._driver.close()
