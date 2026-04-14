"""Neo4j implementation of the graph store port."""

from typing import Any
from uuid import UUID

from neo4j import AsyncGraphDatabase

from src.config import get_settings
from src.core.ports.graph_store import IGraphStore


class Neo4jGraphStore(IGraphStore):
    """Graph store backed by Neo4j."""

    def __init__(self) -> None:
        settings = get_settings()
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    async def close(self) -> None:
        """Close the Neo4j driver connection."""
        await self._driver.close()

    async def add_node(self, node_id: UUID, labels: list[str], properties: dict[str, Any]) -> None:
        """Create or merge a node in Neo4j."""
        label_str = ":".join(labels) if labels else "Node"
        query = f"MERGE (n:{label_str} {{id: $node_id}}) SET n += $props"
        async with self._driver.session() as session:
            await session.run(query, node_id=str(node_id), props=properties)

    async def add_edge(
        self,
        source_id: UUID,
        target_id: UUID,
        relationship: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create a directed relationship between two nodes."""
        props = properties or {}
        query = (
            "MATCH (a {id: $source_id}), (b {id: $target_id}) "
            f"MERGE (a)-[r:{relationship}]->(b) SET r += $props"
        )
        async with self._driver.session() as session:
            await session.run(
                query,
                source_id=str(source_id),
                target_id=str(target_id),
                props=props,
            )

    async def get_subgraph(self, root_id: UUID, depth: int = 2) -> dict[str, Any]:
        """Retrieve a subgraph rooted at the given node up to a specified depth."""
        query = (
            "MATCH path = (root {id: $root_id})-[*0..$depth]-(connected) "
            "RETURN nodes(path) AS nodes, relationships(path) AS edges"
        )
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen_nodes: set[str] = set()
        seen_edges: set[str] = set()

        async with self._driver.session() as session:
            result = await session.run(query, root_id=str(root_id), depth=depth)
            async for record in result:
                for node in record["nodes"]:
                    node_id = dict(node).get("id", "")
                    if node_id not in seen_nodes:
                        seen_nodes.add(node_id)
                        nodes.append({"id": node_id, "labels": list(node.labels), "properties": dict(node)})
                for edge in record["edges"]:
                    edge_key = f"{edge.start_node['id']}-{edge.type}-{edge.end_node['id']}"
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        edges.append({
                            "source": edge.start_node["id"],
                            "target": edge.end_node["id"],
                            "type": edge.type,
                            "properties": dict(edge),
                        })

        return {"nodes": nodes, "edges": edges}
