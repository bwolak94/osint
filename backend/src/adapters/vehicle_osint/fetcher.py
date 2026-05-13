"""Vehicle OSINT fetcher using free public APIs.

- NHTSA vPIC API: VIN decode, recalls, complaints (free, no key)
- NHTSA SaferCar: safety ratings by VIN (free, no key)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

_VPIC_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles"
_COMPLAINTS_BASE = "https://api.nhtsa.gov/complaints/complaintsByVehicle"
_RECALLS_BASE = "https://api.nhtsa.gov/recalls/recallsByVehicle"


@dataclass
class VehicleRecall:
    recall_id: str | None = None
    component: str | None = None
    summary: str | None = None
    consequence: str | None = None
    remedy: str | None = None
    report_date: str | None = None


@dataclass
class VehicleComplaint:
    odt_number: str | None = None
    component: str | None = None
    summary: str | None = None
    crash: bool = False
    fire: bool = False
    date_complaint_filed: str | None = None


@dataclass
class VehicleInfo:
    vin: str | None = None
    make: str | None = None
    model: str | None = None
    model_year: str | None = None
    vehicle_type: str | None = None
    body_class: str | None = None
    drive_type: str | None = None
    fuel_type: str | None = None
    engine_cylinders: str | None = None
    engine_displacement: str | None = None
    transmission: str | None = None
    plant_country: str | None = None
    manufacturer: str | None = None
    series: str | None = None
    trim: str | None = None
    doors: str | None = None
    error_code: str | None = None
    recalls: list[VehicleRecall] = field(default_factory=list)
    complaints_count: int = 0
    recent_complaints: list[VehicleComplaint] = field(default_factory=list)
    source: str = "nhtsa"


@dataclass
class VehicleScrapeResult:
    query: str
    query_type: str
    vehicles: list[VehicleInfo] = field(default_factory=list)


async def fetch_vehicle(query: str, query_type: str) -> VehicleScrapeResult:
    result = VehicleScrapeResult(query=query, query_type=query_type)

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        if query_type == "vin":
            vehicle = await _decode_vin(client, query.upper().strip())
            if vehicle:
                result.vehicles = [vehicle]
        elif query_type == "make_model":
            # Search by make/model/year format "Toyota Camry 2020"
            parts = query.strip().split()
            if len(parts) >= 2:
                make = parts[0]
                model = " ".join(parts[1:-1]) if len(parts) > 2 else parts[1]
                year = parts[-1] if len(parts) > 2 and parts[-1].isdigit() else None
                result.vehicles = await _search_by_make_model(client, make, model, year)

    return result


async def _decode_vin(client: httpx.AsyncClient, vin: str) -> VehicleInfo | None:
    try:
        r = await client.get(
            f"{_VPIC_BASE}/decodevin/{vin}",
            params={"format": "json"},
        )
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception:
        return None

    results = data.get("Results", [])
    fields: dict[str, str] = {
        item["Variable"]: item["Value"]
        for item in results
        if item.get("Value") and item["Value"] not in ("", "Not Applicable", "null", None)
    }

    vehicle = VehicleInfo(
        vin=vin,
        make=fields.get("Make"),
        model=fields.get("Model"),
        model_year=fields.get("Model Year"),
        vehicle_type=fields.get("Vehicle Type"),
        body_class=fields.get("Body Class"),
        drive_type=fields.get("Drive Type"),
        fuel_type=fields.get("Fuel Type - Primary"),
        engine_cylinders=fields.get("Engine Number of Cylinders"),
        engine_displacement=fields.get("Displacement (L)"),
        transmission=fields.get("Transmission Style"),
        plant_country=fields.get("Plant Country"),
        manufacturer=fields.get("Manufacturer Name"),
        series=fields.get("Series"),
        trim=fields.get("Trim"),
        doors=fields.get("Doors"),
        error_code=fields.get("Error Code") if fields.get("Error Code") != "0" else None,
    )

    if not vehicle.make:
        return None

    # Fetch recalls
    if vehicle.make and vehicle.model and vehicle.model_year:
        vehicle.recalls = await _fetch_recalls(
            client, vehicle.make, vehicle.model, vehicle.model_year
        )
        vehicle.recent_complaints, vehicle.complaints_count = await _fetch_complaints(
            client, vehicle.make, vehicle.model, vehicle.model_year
        )

    return vehicle


async def _search_by_make_model(
    client: httpx.AsyncClient, make: str, model: str, year: str | None
) -> list[VehicleInfo]:
    recalls = await _fetch_recalls(client, make, model, year)
    complaints, count = await _fetch_complaints(client, make, model, year)
    vehicle = VehicleInfo(
        make=make.title(),
        model=model.title(),
        model_year=year,
        recalls=recalls,
        recent_complaints=complaints,
        complaints_count=count,
    )
    return [vehicle] if (recalls or complaints) else []


async def _fetch_recalls(
    client: httpx.AsyncClient, make: str, model: str, year: str | None
) -> list[VehicleRecall]:
    try:
        params: dict[str, str] = {"make": make, "model": model}
        if year:
            params["modelYear"] = year
        r = await client.get(_RECALLS_BASE, params=params)
        if r.status_code != 200:
            return []
        items = r.json().get("results", [])
        return [
            VehicleRecall(
                recall_id=item.get("NHTSACampaignNumber"),
                component=item.get("Component"),
                summary=item.get("Summary"),
                consequence=item.get("Consequence"),
                remedy=item.get("Remedy"),
                report_date=item.get("ReportReceivedDate"),
            )
            for item in items[:10]
        ]
    except Exception:
        return []


async def _fetch_complaints(
    client: httpx.AsyncClient, make: str, model: str, year: str | None
) -> tuple[list[VehicleComplaint], int]:
    try:
        params: dict[str, str] = {"make": make, "model": model}
        if year:
            params["modelYear"] = year
        r = await client.get(_COMPLAINTS_BASE, params=params)
        if r.status_code != 200:
            return [], 0
        data = r.json()
        items = data.get("results", [])
        complaints = [
            VehicleComplaint(
                odt_number=str(item.get("odiNumber", "")),
                component=item.get("components"),
                summary=item.get("summary"),
                crash=bool(item.get("crash")),
                fire=bool(item.get("fire")),
                date_complaint_filed=item.get("dateComplaintFiled"),
            )
            for item in items[:5]
        ]
        return complaints, len(items)
    except Exception:
        return [], 0
