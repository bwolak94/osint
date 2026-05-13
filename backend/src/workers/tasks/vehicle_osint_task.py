"""Celery task: Vehicle OSINT NHTSA API fetch (light queue)."""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="vehicle_osint.fetch",
    queue="light",
    max_retries=2,
    default_retry_delay=15,
    soft_time_limit=45,
    time_limit=60,
)
def vehicle_osint_fetch_task(self: Any, query: str, query_type: str) -> dict[str, Any]:
    """Fetch vehicle data from NHTSA free public APIs."""
    try:
        from src.adapters.vehicle_osint.fetcher import fetch_vehicle

        result = asyncio.run(fetch_vehicle(query, query_type))

        vehicles_json = []
        for v in result.vehicles:
            recalls = [
                {
                    "recall_id": r.recall_id,
                    "component": r.component,
                    "summary": r.summary,
                    "consequence": r.consequence,
                    "remedy": r.remedy,
                    "report_date": r.report_date,
                }
                for r in v.recalls
            ]
            complaints = [
                {
                    "odt_number": c.odt_number,
                    "component": c.component,
                    "summary": c.summary,
                    "crash": c.crash,
                    "fire": c.fire,
                    "date_complaint_filed": c.date_complaint_filed,
                }
                for c in v.recent_complaints
            ]
            vehicles_json.append(
                {
                    "vin": v.vin,
                    "make": v.make,
                    "model": v.model,
                    "model_year": v.model_year,
                    "vehicle_type": v.vehicle_type,
                    "body_class": v.body_class,
                    "drive_type": v.drive_type,
                    "fuel_type": v.fuel_type,
                    "engine_cylinders": v.engine_cylinders,
                    "engine_displacement": v.engine_displacement,
                    "transmission": v.transmission,
                    "plant_country": v.plant_country,
                    "manufacturer": v.manufacturer,
                    "series": v.series,
                    "trim": v.trim,
                    "doors": v.doors,
                    "error_code": v.error_code,
                    "recalls": recalls,
                    "complaints_count": v.complaints_count,
                    "recent_complaints": complaints,
                    "source": v.source,
                }
            )

        log.info("vehicle_osint_task_done", query=query, count=len(vehicles_json))
        return {"vehicles": vehicles_json, "query": query, "query_type": query_type}

    except Exception as exc:
        log.error("vehicle_osint_task_error", query=query, error=str(exc))
        raise self.retry(exc=exc)
