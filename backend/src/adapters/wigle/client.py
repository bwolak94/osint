"""WiGLE API v2 client for WiFi network geolocation."""

from __future__ import annotations

import os
import httpx
from dataclasses import dataclass, field


@dataclass
class WigleNetwork:
    netid: str  # BSSID
    ssid: str | None
    encryption: str | None
    channel: int | None
    trilat: float | None  # latitude
    trilong: float | None  # longitude
    first_seen: str | None
    last_seen: str | None
    country: str | None
    region: str | None
    city: str | None
    maps_url: str | None


@dataclass
class WigleResult:
    query: str
    query_type: str
    networks: list[WigleNetwork] = field(default_factory=list)


class WigleClient:
    BASE_URL = "https://api.wigle.net/api/v2"

    def __init__(self) -> None:
        self._api_key = os.getenv("WIGLE_API_KEY", "")

    async def search(self, query: str, query_type: str) -> WigleResult:
        result = WigleResult(query=query, query_type=query_type)
        if not self._api_key:
            return result

        params: dict = {"resultsPerPage": 25, "first": "true"}
        if query_type == "bssid":
            params["netid"] = query.upper()
        else:
            params["ssid"] = query

        headers = {"Authorization": f"Basic {self._api_key}"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/network/search",
                    params=params,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return result

        for net in data.get("results", []):
            trilat = net.get("trilat")
            trilong = net.get("trilong")
            maps_url = None
            if trilat is not None and trilong is not None:
                maps_url = f"https://www.google.com/maps?q={trilat},{trilong}"
            result.networks.append(
                WigleNetwork(
                    netid=net.get("netid", ""),
                    ssid=net.get("ssid"),
                    encryption=net.get("encryption"),
                    channel=net.get("channel"),
                    trilat=trilat,
                    trilong=trilong,
                    first_seen=net.get("firsttime"),
                    last_seen=net.get("lasttime"),
                    country=net.get("country"),
                    region=net.get("region"),
                    city=net.get("city"),
                    maps_url=maps_url,
                )
            )
        return result
