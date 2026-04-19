"""AIS vessel tracking scanner — multi-source vessel position and fleet intelligence."""

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_MMSI_RE = re.compile(r"\b[2-7]\d{8}\b")


class AISVesselScanner(BaseOsintScanner):
    scanner_name = "ais_vessel"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS})
    cache_ttl = 300

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        settings = get_settings()
        vessels: list[dict[str, Any]] = []

        mmsi = self._extract_mmsi(input_value)

        if mmsi:
            vessels = await self._lookup_by_mmsi(mmsi, settings)
        else:
            company_query = input_value.strip().lower()
            vessels = await self._search_by_company(company_query, settings)

        fleet_size = len(vessels)

        return {
            "input": input_value,
            "mmsi_detected": mmsi,
            "vessels": vessels,
            "company_fleet_size": fleet_size,
            "extracted_identifiers": [],
        }

    def _extract_mmsi(self, value: str) -> str:
        # Treat pure numeric 9-digit string or IP-format that maps to MMSI
        clean = value.strip().replace(".", "")
        if re.fullmatch(r"[2-7]\d{8}", clean):
            return clean
        m = _MMSI_RE.search(value)
        return m.group() if m else ""

    async def _lookup_by_mmsi(self, mmsi: str, settings: Any) -> list[dict[str, Any]]:
        vessels: list[dict[str, Any]] = []

        aishub_user = getattr(settings, "aishub_username", "")
        if aishub_user:
            v = await self._aishub_lookup(mmsi, aishub_user)
            if v:
                vessels.append(v)
                return vessels

        v = await self._vesselfinder_scrape(mmsi)
        if v:
            vessels.append(v)
            return vessels

        v = await self._shipfinder_scrape(mmsi)
        if v:
            vessels.append(v)

        return vessels

    async def _aishub_lookup(self, mmsi: str, username: str) -> dict[str, Any] | None:
        url = (
            f"https://www.aishub.net/api/api.php"
            f"?username={username}&format=json&output=json&compress=0&mmsi={mmsi}"
        )
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers={"User-Agent": "OSINT-Platform/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 1:
                        vessel_list = data[1] if isinstance(data[1], list) else [data[1]]
                        if vessel_list:
                            raw = vessel_list[0]
                            return self._normalise_vessel(raw)
        except Exception as exc:
            log.debug("AISHub lookup failed", mmsi=mmsi, error=str(exc))
        return None

    async def _vesselfinder_scrape(self, mmsi: str) -> dict[str, Any] | None:
        url = f"https://www.vesselfinder.com/vessels/{mmsi}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"}
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    text = resp.text
                    name_m = re.search(r'<h1[^>]*>([^<]+)</h1>', text)
                    flag_m = re.search(r'Flag[^:]*:\s*([A-Za-z ]+)', text)
                    type_m = re.search(r'Type[^:]*:\s*([A-Za-z ]+)', text)
                    return {
                        "name": name_m.group(1).strip() if name_m else "",
                        "mmsi": mmsi,
                        "imo": "",
                        "flag": flag_m.group(1).strip() if flag_m else "",
                        "vessel_type": type_m.group(1).strip() if type_m else "",
                        "position": {},
                        "speed": None,
                        "course": None,
                        "destination": "",
                        "last_seen": "",
                        "source": "vesselfinder_scrape",
                    }
        except Exception as exc:
            log.debug("VesselFinder scrape failed", mmsi=mmsi, error=str(exc))
        return None

    async def _shipfinder_scrape(self, mmsi: str) -> dict[str, Any] | None:
        url = f"https://www.shipfinder.com/tracking/{mmsi}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"}
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    text = resp.text
                    name_m = re.search(r'"vesselName"\s*:\s*"([^"]+)"', text)
                    flag_m = re.search(r'"flag"\s*:\s*"([^"]+)"', text)
                    lat_m = re.search(r'"lat"\s*:\s*([\d.\-]+)', text)
                    lon_m = re.search(r'"lon"\s*:\s*([\d.\-]+)', text)
                    position: dict[str, float] = {}
                    if lat_m and lon_m:
                        position = {
                            "latitude": float(lat_m.group(1)),
                            "longitude": float(lon_m.group(1)),
                        }
                    return {
                        "name": name_m.group(1) if name_m else "",
                        "mmsi": mmsi,
                        "imo": "",
                        "flag": flag_m.group(1) if flag_m else "",
                        "vessel_type": "",
                        "position": position,
                        "speed": None,
                        "course": None,
                        "destination": "",
                        "last_seen": "",
                        "source": "shipfinder_scrape",
                    }
        except Exception as exc:
            log.debug("ShipFinder scrape failed", mmsi=mmsi, error=str(exc))
        return None

    async def _search_by_company(self, company: str, settings: Any) -> list[dict[str, Any]]:
        """Search vessel registries by company/operator name."""
        vessels: list[dict[str, Any]] = []
        url = f"https://www.marinetraffic.com/en/ais/index/ships/all/shipname:{company}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"}
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    names = re.findall(r'"shipname":"([^"]+)"', resp.text)
                    mmsis = re.findall(r'"mmsi":"(\d{9})"', resp.text)
                    for name, mmsi in zip(names[:10], mmsis[:10]):
                        vessels.append({
                            "name": name,
                            "mmsi": mmsi,
                            "imo": "",
                            "flag": "",
                            "vessel_type": "",
                            "position": {},
                            "speed": None,
                            "course": None,
                            "destination": "",
                            "last_seen": "",
                            "source": "marinetraffic_scrape",
                        })
        except Exception as exc:
            log.debug("MarineTraffic company search failed", company=company, error=str(exc))
        return vessels

    def _normalise_vessel(self, raw: dict[str, Any]) -> dict[str, Any]:
        lat = raw.get("LATITUDE") or raw.get("lat")
        lon = raw.get("LONGITUDE") or raw.get("lon")
        position: dict[str, float] = {}
        if lat is not None and lon is not None:
            try:
                position = {"latitude": float(lat), "longitude": float(lon)}
            except (TypeError, ValueError):
                pass
        return {
            "name": str(raw.get("NAME") or raw.get("name") or ""),
            "mmsi": str(raw.get("MMSI") or raw.get("mmsi") or ""),
            "imo": str(raw.get("IMO") or raw.get("imo") or ""),
            "flag": str(raw.get("FLAG") or raw.get("flag") or ""),
            "vessel_type": str(raw.get("TYPE_NAME") or raw.get("type") or ""),
            "position": position,
            "speed": raw.get("SPEED") or raw.get("speed"),
            "course": raw.get("COURSE") or raw.get("course"),
            "destination": str(raw.get("DESTINATION") or raw.get("destination") or ""),
            "last_seen": str(raw.get("LAST_POS_UTC") or raw.get("last_seen") or ""),
            "source": "aishub",
        }
