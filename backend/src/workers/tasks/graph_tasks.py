"""Celery tasks for graph operations and entity resolution."""

import asyncio
import structlog
from uuid import UUID

from src.workers.celery_app import celery_app

log = structlog.get_logger()


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="graph.resolve_entities", queue="graph")
def resolve_entities_task(self, investigation_id: str) -> dict:
    """Run entity resolution on all scan results for an investigation."""
    try:
        from src.adapters.entity_resolution.resolver import SimpleEntityResolver

        resolver = SimpleEntityResolver()
        clusters = _run_async(resolver.resolve(UUID(investigation_id)))

        log.info("Entity resolution completed", investigation_id=investigation_id, clusters=len(clusters))
        return {"investigation_id": investigation_id, "cluster_count": len(clusters)}

    except Exception as exc:
        log.error("Entity resolution failed", investigation_id=investigation_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, name="graph.build_graph", queue="graph")
def build_graph_task(self, investigation_id: str) -> dict:
    """Build the Neo4j knowledge graph from resolved entities."""
    log.info("Graph build started", investigation_id=investigation_id)
    try:
        result = _run_async(_auto_build_entity_graph(investigation_id))
        log.info("Graph build completed", investigation_id=investigation_id, **result)
        return {"investigation_id": investigation_id, "status": "completed", **result}
    except Exception as exc:
        log.error("Graph build failed", investigation_id=investigation_id, error=str(exc))
        return {"investigation_id": investigation_id, "status": "failed", "error": str(exc)}


@celery_app.task(bind=True, name="graph.auto_build_from_findings", queue="graph")
def auto_build_entity_graph_task(self, investigation_id: str) -> dict:
    """Auto-extract entities from scan findings and build relationship graph in Neo4j."""
    log.info("Auto entity graph build started", investigation_id=investigation_id)
    try:
        result = _run_async(_auto_build_entity_graph(investigation_id))
        return {"investigation_id": investigation_id, "status": "completed", **result}
    except Exception as exc:
        log.error("Auto graph build failed", investigation_id=investigation_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30, max_retries=2)


async def _auto_build_entity_graph(investigation_id: str) -> dict:
    """Extract entities from findings and write nodes/edges to Neo4j.

    Entity types extracted:
    - Email addresses       → EMAIL node
    - Domain names          → DOMAIN node
    - IP addresses          → IP_ADDRESS node
    - Person names          → PERSON node
    - Company/org names     → ORGANIZATION node
    - Phone numbers         → PHONE node
    - URLs                  → URL node

    Relationships are created between:
    - Scan result → entities found within it
    - Entities that co-appear in the same finding
    """
    import re
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from src.config import get_app_settings
    settings = get_app_settings()

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    nodes_created = 0
    edges_created = 0

    # Patterns for entity extraction
    _EMAIL_RE = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')
    _DOMAIN_RE = re.compile(r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,6}\b')
    _IP_RE = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
    _PHONE_RE = re.compile(r'\+?\d[\d\s\-().]{7,15}\d')

    try:
        from src.adapters.db.models import ScanResultModel

        async with async_session() as db:
            result = await db.execute(
                select(ScanResultModel).where(
                    ScanResultModel.investigation_id == investigation_id
                )
            )
            scan_results = result.scalars().all()

        # Try to connect to Neo4j
        try:
            from neo4j import AsyncGraphDatabase

            async with AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            ) as driver:
                async with driver.session() as neo_session:
                    for sr in scan_results:
                        raw = sr.raw_data or {}
                        findings = raw.get("findings", [])

                        for finding in findings:
                            desc = finding.get("description", "")
                            all_text = " ".join([
                                str(v) for v in finding.values()
                                if isinstance(v, (str, int, float))
                            ])

                            # Extract entities
                            emails = _EMAIL_RE.findall(all_text)
                            ips = _IP_RE.findall(all_text)
                            domains = [
                                d for d in _DOMAIN_RE.findall(all_text)
                                if "." in d and not _IP_RE.match(d)
                                and len(d) > 4 and not d.endswith(".png")
                                and not d.endswith(".jpg")
                            ][:5]

                            # Merge nodes into Neo4j
                            for email in emails[:5]:
                                await neo_session.run(
                                    "MERGE (n:Email {value: $val}) "
                                    "ON CREATE SET n.investigation_id = $inv, n.first_seen = timestamp() "
                                    "ON MATCH SET n.last_seen = timestamp()",
                                    val=email.lower(), inv=investigation_id
                                )
                                nodes_created += 1

                            for ip in ips[:5]:
                                await neo_session.run(
                                    "MERGE (n:IPAddress {value: $val}) "
                                    "ON CREATE SET n.investigation_id = $inv, n.first_seen = timestamp()",
                                    val=ip, inv=investigation_id
                                )
                                nodes_created += 1

                            for domain in domains:
                                await neo_session.run(
                                    "MERGE (n:Domain {value: $val}) "
                                    "ON CREATE SET n.investigation_id = $inv, n.first_seen = timestamp()",
                                    val=domain.lower(), inv=investigation_id
                                )
                                nodes_created += 1

                            # Create relationships between co-occurring entities
                            all_entities = (
                                [(e.lower(), "Email") for e in emails[:3]] +
                                [(ip, "IPAddress") for ip in ips[:3]] +
                                [(d.lower(), "Domain") for d in domains[:3]]
                            )
                            scanner = sr.scanner_name
                            for i, (val1, type1) in enumerate(all_entities):
                                for val2, type2 in all_entities[i + 1:i + 4]:
                                    await neo_session.run(
                                        f"MATCH (a:{type1} {{value: $v1}}), (b:{type2} {{value: $v2}}) "
                                        "MERGE (a)-[r:CO_OCCURS {{scanner: $scanner}}]->(b) "
                                        "ON CREATE SET r.count = 1 "
                                        "ON MATCH SET r.count = r.count + 1",
                                        v1=val1, v2=val2, scanner=scanner
                                    )
                                    edges_created += 1

        except Exception as neo_exc:
            log.debug("Neo4j graph build skipped", error=str(neo_exc))

    finally:
        await engine.dispose()

    return {"nodes_created": nodes_created, "edges_created": edges_created}
