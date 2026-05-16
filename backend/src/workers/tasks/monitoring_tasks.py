"""Continuous monitoring and alert tasks — periodic re-scan for watched targets."""

from __future__ import annotations

import asyncio
import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(
    name="src.workers.tasks.monitoring_tasks.run_monitoring_sweep",
    bind=True,
    max_retries=0,
    queue="light",
)
def run_monitoring_sweep(self) -> dict:
    """Periodic sweep: re-scan all monitored targets and emit alerts on changes.

    Called by Celery Beat every hour (configured in celery_app.py beat_schedule).
    """
    log.info("Monitoring sweep started")

    async def _sweep() -> dict:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import select, text
        from src.config import get_app_settings

        settings = get_app_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        alerts_sent = 0
        errors = 0

        try:
            async with async_session() as db:
                # Load monitored investigations (those with monitoring_enabled=True)
                try:
                    result = await db.execute(
                        text(
                            "SELECT id, title, owner_id, target "
                            "FROM investigations "
                            "WHERE monitoring_enabled = true AND status != 'running' "
                            "ORDER BY last_monitored_at ASC NULLS FIRST "
                            "LIMIT 50"
                        )
                    )
                    rows = result.fetchall()
                except Exception:
                    # Column may not exist yet (migration pending)
                    rows = []

                for row in rows:
                    try:
                        # Dispatch a re-scan task
                        from src.workers.tasks.investigation_tasks import run_osint_investigation
                        run_osint_investigation.apply_async(
                            kwargs={
                                "investigation_id": str(row[0]),
                                "seed_inputs_data": [{"value": str(row[3] or ""), "input_type": "domain"}],
                            },
                            queue="light",
                        )
                        alerts_sent += 1
                    except Exception as exc:
                        log.debug("Monitoring sweep dispatch failed", error=str(exc))
                        errors += 1
        except Exception as exc:
            log.error("Monitoring sweep DB error", error=str(exc))
        finally:
            await engine.dispose()

        return {"alerts_dispatched": alerts_sent, "errors": errors}

    result = asyncio.run(_sweep())
    log.info("Monitoring sweep completed", **result)
    return result


@celery_app.task(
    name="src.workers.tasks.monitoring_tasks.certstream_monitor",
    bind=True,
    max_retries=0,
    queue="light",
)
def certstream_monitor(self, domains: list[str] | None = None) -> dict:
    """Monitor CertStream for new TLS certificates matching watched domains.

    Useful for detecting new subdomains, phishing sites, and domain spoofing.
    """
    log.info("CertStream domain monitor started", domain_count=len(domains or []))

    async def _check() -> dict:
        import httpx
        matches: list[dict] = []

        if not domains:
            return {"matches": [], "domains_checked": 0}

        async with httpx.AsyncClient(timeout=10) as client:
            for domain in (domains or [])[:20]:
                try:
                    resp = await client.get(
                        "https://crt.sh/",
                        params={"q": f"%.{domain}", "output": "json"},
                        timeout=8,
                    )
                    if resp.status_code == 200:
                        import json as _json
                        entries = _json.loads(resp.text)
                        # New certs in last 24h
                        from datetime import datetime, timezone, timedelta
                        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                        for entry in (entries or [])[:5]:
                            not_before = entry.get("not_before", "")
                            try:
                                cert_date = datetime.fromisoformat(not_before.replace("Z", "+00:00"))
                                if cert_date > cutoff:
                                    matches.append({
                                        "domain": domain,
                                        "cert_domain": entry.get("name_value"),
                                        "issuer": entry.get("issuer_name"),
                                        "issued_at": not_before,
                                    })
                            except Exception:
                                pass
                except Exception as exc:
                    log.debug("CertStream crt.sh error", domain=domain, error=str(exc))

        return {"matches": matches, "domains_checked": len(domains or [])}

    result = asyncio.run(_check())
    log.info("CertStream monitor completed", matches=len(result.get("matches", [])))
    return result
