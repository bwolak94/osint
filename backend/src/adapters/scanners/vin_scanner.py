"""Vehicle VIN decoder scanner — NHTSA, VPIC, recall history.

Finds:
- Make, model, year, trim, engine from VIN
- Safety recall history (open + completed)
- Manufacturer defect complaints
- Crash test ratings
- Registration state hints from VIN structure
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_VIN_RE = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$', re.IGNORECASE)
_NHTSA_VPIC = "https://vpic.nhtsa.dot.gov/api/vehicles"
_NHTSA_COMPLAINTS = "https://api.nhtsa.gov/complaints/complaintsByVehicle"
_NHTSA_RECALLS = "https://api.nhtsa.gov/recalls/recallsByVehicle"


class VINScanner(BaseOsintScanner):
    """Vehicle Identification Number (VIN) decoder and history scanner."""

    scanner_name = "vin"
    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.DOMAIN})
    cache_ttl = 86400
    scan_timeout = 20

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []

        # Extract VIN from input (could be embedded in text)
        vin_match = _VIN_RE.search(query.upper().replace(" ", ""))
        if not vin_match:
            # Try to find VIN pattern in longer text
            embedded = re.search(r'\b([A-HJ-NPR-Z0-9]{17})\b', query.upper())
            if not embedded:
                return {
                    "input": query,
                    "scan_mode": "manual_fallback",
                    "findings": [],
                    "total_found": 0,
                    "note": "No valid 17-character VIN found in input",
                    "extracted_identifiers": [],
                }
            vin = embedded.group(1)
        else:
            vin = vin_match.group(0)

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; VINScanner/1.0)"},
        ) as client:
            # 1. Decode VIN via NHTSA VPIC
            try:
                resp = await client.get(
                    f"{_NHTSA_VPIC}/DecodeVinValuesExtended/{vin}?format=json",
                    timeout=8,
                )
                if resp.status_code == 200:
                    import json as _json
                    data = _json.loads(resp.text)
                    results = data.get("Results", [{}])
                    r = results[0] if results else {}

                    make = r.get("Make", "")
                    model = r.get("Model", "")
                    year = r.get("ModelYear", "")
                    trim = r.get("Trim", "")
                    engine = r.get("DisplacementL", "")
                    fuel = r.get("FuelTypePrimary", "")
                    body = r.get("BodyClass", "")
                    drive = r.get("DriveType", "")
                    country = r.get("PlantCountry", "")
                    error_code = r.get("ErrorCode", "")

                    if make or model:
                        identifiers.append("info:vin:decoded")
                        findings.append({
                            "type": "vin_decoded",
                            "severity": "info",
                            "source": "NHTSA VPIC",
                            "vin": vin,
                            "make": make,
                            "model": model,
                            "year": year,
                            "trim": trim,
                            "engine_displacement_l": engine,
                            "fuel_type": fuel,
                            "body_class": body,
                            "drive_type": drive,
                            "plant_country": country,
                            "description": f"VIN {vin}: {year} {make} {model} {trim}".strip(),
                        })

                        # 2. Recalls for this vehicle
                        if make and model and year:
                            try:
                                recall_resp = await client.get(
                                    _NHTSA_RECALLS,
                                    params={"make": make, "model": model, "modelYear": year},
                                    timeout=8,
                                )
                                if recall_resp.status_code == 200:
                                    recall_data = _json.loads(recall_resp.text)
                                    recalls = recall_data.get("results", [])
                                    open_recalls = [r for r in recalls if not r.get("completed")]
                                    if recalls:
                                        identifiers.append("info:vin:recalls_found")
                                        findings.append({
                                            "type": "vehicle_recalls",
                                            "severity": "high" if open_recalls else "medium",
                                            "source": "NHTSA Recalls",
                                            "vin": vin,
                                            "total_recalls": len(recalls),
                                            "open_recalls": len(open_recalls),
                                            "sample_recalls": [
                                                {
                                                    "campaign": r.get("NHTSACampaignNumber"),
                                                    "component": r.get("Component"),
                                                    "summary": r.get("Summary", "")[:100],
                                                }
                                                for r in recalls[:3]
                                            ],
                                            "description": f"Vehicle has {len(recalls)} recall(s) — {len(open_recalls)} open",
                                        })
                            except Exception as exc:
                                log.debug("NHTSA recalls error", error=str(exc))

                        # 3. Complaints
                        if make and model and year:
                            try:
                                comp_resp = await client.get(
                                    _NHTSA_COMPLAINTS,
                                    params={"make": make, "model": model, "modelYear": year},
                                    timeout=8,
                                )
                                if comp_resp.status_code == 200:
                                    comp_data = _json.loads(comp_resp.text)
                                    complaints = comp_data.get("results", [])
                                    if complaints:
                                        identifiers.append("info:vin:complaints_found")
                                        findings.append({
                                            "type": "vehicle_complaints",
                                            "severity": "low",
                                            "source": "NHTSA Complaints",
                                            "vin": vin,
                                            "total_complaints": len(complaints),
                                            "description": f"Vehicle has {len(complaints)} consumer complaints filed",
                                        })
                            except Exception as exc:
                                log.debug("NHTSA complaints error", error=str(exc))

            except Exception as exc:
                log.debug("NHTSA VPIC error", error=str(exc))

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "vin": vin,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
