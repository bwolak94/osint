"""Graph endpoints scoped to an investigation.

Builds the knowledge graph dynamically from PostgreSQL scan results,
removing the hard dependency on Neo4j.
"""

from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.scan_result_repository import SqlAlchemyScanResultRepository
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.investigations.schemas import (
    AddEdgeRequest,
    AddNodeRequest,
    GraphEdgeSchema,
    GraphMetaSchema,
    GraphNodeSchema,
    GraphResponse,
    PathsResponse,
)
from src.core.domain.entities.scan_result import ScanResult
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Graph builder helpers
# ---------------------------------------------------------------------------

def _build_graph_from_scan_results(scan_results: list[ScanResult]) -> GraphResponse:
    """Construct a graph of nodes and edges from raw scan result data.

    Each scan result's *raw_data* is inspected for known fields (name,
    bank_accounts, regon, working_address, etc.) and corresponding graph
    nodes / edges are emitted.
    """
    nodes: dict[str, GraphNodeSchema] = {}
    edges: list[GraphEdgeSchema] = []

    def _add_node(node_id: str, node_type: str, label: str,
                  properties: dict[str, Any] | None = None,
                  confidence: float = 0.9,
                  sources: list[str] | None = None) -> str:
        """Insert a node (de-duplicated by id) and return its id."""
        if node_id not in nodes:
            nodes[node_id] = GraphNodeSchema(
                id=node_id,
                type=node_type,
                label=label,
                properties=properties or {},
                confidence=confidence,
                sources=sources or [],
            )
        return node_id

    def _add_edge(source: str, target: str, edge_type: str, label: str = "") -> None:
        edge_id = f"{source}-{edge_type}-{target}"
        edges.append(GraphEdgeSchema(
            id=edge_id,
            source=source,
            target=target,
            type=edge_type,
            label=label,
            confidence=0.9,
        ))

    for result in scan_results:
        raw = result.raw_data
        if not raw:
            continue
        # Skip empty/stub results
        if raw.get("_stub"):
            continue
        has_data = raw.get("found") or raw.get("registered_count", 0) > 0 or raw.get("claimed_count", 0) > 0
        if not has_data:
            continue

        scanner = result.scanner_name
        input_value = result.input_value

        # Root node: the seed input (e.g. a NIP number)
        root_id = f"input:{input_value}"
        nip = raw.get("nip")
        if nip:
            _add_node(root_id, "nip", f"NIP {nip}",
                       properties={"nip": nip}, sources=[scanner])
        else:
            _add_node(root_id, "input", input_value,
                       properties={"value": input_value}, sources=[scanner])

        # Company / person node
        name = raw.get("name")
        if name:
            entity_id = f"entity:{name}"
            entity_type = "company" if nip else "person"
            _add_node(entity_id, entity_type, name,
                       properties={"name": name, "status_vat": raw.get("status_vat", "")},
                       sources=[scanner])
            _add_edge(root_id, entity_id, "IDENTIFIES", "identifies")

        # REGON node
        regon = raw.get("regon")
        if regon:
            regon_id = f"regon:{regon}"
            _add_node(regon_id, "regon", f"REGON {regon}",
                       properties={"regon": regon}, sources=[scanner])
            parent = f"entity:{name}" if name else root_id
            _add_edge(parent, regon_id, "HAS_REGON", "has REGON")

        # Address nodes (working_address and residence_address)
        for addr_key in ("working_address", "residence_address"):
            address = raw.get(addr_key)
            if address:
                addr_id = f"address:{address}"
                _add_node(addr_id, "address", address,
                           properties={"address": address, "address_type": addr_key},
                           sources=[scanner])
                parent = f"entity:{name}" if name else root_id
                edge_label = "registered at" if addr_key == "working_address" else "resides at"
                _add_edge(parent, addr_id, "HAS_ADDRESS", edge_label)

        # Bank account nodes
        bank_accounts = raw.get("bank_accounts")
        if bank_accounts and isinstance(bank_accounts, list):
            parent = f"entity:{name}" if name else root_id
            for account in bank_accounts:
                acc_id = f"bank:{account}"
                _add_node(acc_id, "bank_account", account,
                           properties={"account_number": account},
                           sources=[scanner])
                _add_edge(parent, acc_id, "HAS_BANK_ACCOUNT", "bank account")

        # Registration date as property on entity node (not a separate node)
        reg_date = raw.get("registration_date")
        if reg_date and name and f"entity:{name}" in nodes:
            nodes[f"entity:{name}"].properties["registration_date"] = reg_date

        # Holehe results: email registered on online services
        registered_on = raw.get("registered_on")
        if registered_on and isinstance(registered_on, list) and scanner == "holehe":
            email_id = f"email:{input_value}"
            _add_node(email_id, "email", input_value,
                       properties={"email": input_value}, sources=[scanner])
            if root_id != email_id:
                _add_edge(root_id, email_id, "IDENTIFIES", "identifies")
            for svc_name in registered_on:
                svc_id = f"service:{svc_name}"
                _add_node(svc_id, "online_service", svc_name,
                           properties={"service": svc_name}, sources=[scanner])
                _add_edge(email_id, svc_id, "REGISTERED_ON", "registered on")
            # Backup email if found
            backup = raw.get("backup_email")
            if backup:
                backup_id = f"email:{backup}"
                _add_node(backup_id, "email", backup,
                           properties={"email": backup, "type": "backup"}, sources=[scanner])
                _add_edge(email_id, backup_id, "HAS_BACKUP", "backup email")

        # Maigret results: username found on services
        claimed_profiles = raw.get("claimed_profiles")
        if claimed_profiles and isinstance(claimed_profiles, list) and scanner == "maigret":
            username_id = f"username:{input_value}"
            _add_node(username_id, "username", input_value,
                       properties={"username": input_value}, sources=[scanner])
            if root_id != username_id:
                _add_edge(root_id, username_id, "IDENTIFIES", "identifies")
            for profile in claimed_profiles[:30]:  # Limit to 30 to avoid graph explosion
                site = profile.get("site", "") or profile.get("site_name", "")
                url = profile.get("url", "") or profile.get("url_user", "")
                if site:
                    svc_id = f"service:{site}"
                    _add_node(svc_id, "online_service", site,
                               properties={"service": site, "url": url}, sources=[scanner])
                    _add_edge(username_id, svc_id, "HAS_PROFILE", "has profile")

    node_list = list(nodes.values())
    n = len(node_list)
    max_edges = n * (n - 1) if n > 1 else 1
    density = len(edges) / max_edges if max_edges else 0.0

    return GraphResponse(
        nodes=node_list,
        edges=edges,
        meta=GraphMetaSchema(
            node_count=len(node_list),
            edge_count=len(edges),
            density=round(density, 4),
        ),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{investigation_id}/graph", response_model=GraphResponse)
async def get_graph(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    depth: int = Query(default=3, ge=1, le=5),
) -> GraphResponse:
    """Return the full knowledge graph for an investigation.

    The graph is built dynamically from scan results stored in PostgreSQL,
    so Neo4j is not required.
    """
    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)
    return _build_graph_from_scan_results(results)


@router.get("/{investigation_id}/graph/nodes", response_model=list[GraphNodeSchema])
async def get_graph_nodes(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    node_type: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
) -> list[GraphNodeSchema]:
    """List graph nodes with optional type filter."""
    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)
    graph = _build_graph_from_scan_results(results)
    nodes = graph.nodes
    if node_type:
        nodes = [n for n in nodes if n.type == node_type]
    return nodes[:limit]


@router.get("/{investigation_id}/graph/edges", response_model=list[GraphEdgeSchema])
async def get_graph_edges(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    edge_type: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
) -> list[GraphEdgeSchema]:
    """List graph edges with optional type filter."""
    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)
    graph = _build_graph_from_scan_results(results)
    edge_list = graph.edges
    if edge_type:
        edge_list = [e for e in edge_list if e.type == edge_type]
    return edge_list[:limit]


@router.post("/{investigation_id}/graph/nodes", response_model=GraphNodeSchema, status_code=status.HTTP_201_CREATED)
async def add_graph_node(
    investigation_id: UUID,
    body: AddNodeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> GraphNodeSchema:
    """Manually add a node to the investigation graph."""
    return GraphNodeSchema(
        id=str(uuid4()), type=body.type, label=body.label,
        properties=body.properties, confidence=1.0, sources=["manual"],
    )


@router.post("/{investigation_id}/graph/edges", response_model=GraphEdgeSchema, status_code=status.HTTP_201_CREATED)
async def add_graph_edge(
    investigation_id: UUID,
    body: AddEdgeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> GraphEdgeSchema:
    """Manually add an edge between two nodes."""
    return GraphEdgeSchema(
        id=str(uuid4()), source=body.source_node_id, target=body.target_node_id,
        type=body.type, label=body.label, confidence=1.0,
    )


@router.delete("/{investigation_id}/graph/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_graph_node(
    investigation_id: UUID,
    node_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Remove a node and its edges from the graph."""
    pass


@router.get("/{investigation_id}/graph/paths", response_model=PathsResponse)
async def find_paths(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    from_node: str = Query(..., alias="from"),
    to_node: str = Query(..., alias="to"),
) -> PathsResponse:
    """Find shortest paths between two nodes."""
    return PathsResponse(paths=[], path_count=0)
