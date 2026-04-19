"""OpenCorporates scanner — corporate registry and officer search."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_BASE_URL = "https://api.opencorporates.com/v0.4"


def _extract_company_name_from_domain(domain: str) -> str:
    """Strip TLD and www prefix to derive a company name guess."""
    name = domain.lower().removeprefix("www.")
    name = name.split(".")[0]
    return name


class OpenCorporatesScanner(BaseOsintScanner):
    scanner_name = "opencorporates"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.USERNAME})
    cache_ttl = 86400

    def __init__(self, api_key: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        headers: dict[str, str] = {}
        params_extra: dict[str, str] = {}
        if self._api_key:
            params_extra["api_token"] = self._api_key

        async with httpx.AsyncClient(timeout=20) as client:
            if input_type == ScanInputType.DOMAIN:
                query = _extract_company_name_from_domain(input_value)
                return await self._search_companies(client, query, params_extra, input_value)
            # USERNAME — treat as person name
            query = input_value
            return await self._search_officers(client, query, params_extra, input_value)

    async def _search_companies(
        self,
        client: httpx.AsyncClient,
        query: str,
        params_extra: dict[str, str],
        original_input: str,
    ) -> dict[str, Any]:
        params = {"q": query, "per_page": "10", **params_extra}
        resp = await client.get(f"{_BASE_URL}/companies/search", params=params)
        if resp.status_code != 200:
            return {"input": original_input, "found": False, "companies": [], "officers": [], "extracted_identifiers": []}

        data = resp.json()
        raw_companies = data.get("results", {}).get("companies", [])

        identifiers: list[str] = []
        companies: list[dict[str, Any]] = []
        for item in raw_companies:
            co = item.get("company", {})
            entry: dict[str, Any] = {
                "name": co.get("name", ""),
                "company_number": co.get("company_number", ""),
                "jurisdiction": co.get("jurisdiction_code", ""),
                "status": co.get("current_status", ""),
                "incorporation_date": co.get("incorporation_date", ""),
                "registered_address": co.get("registered_address_in_full", ""),
                "directors_count": len(co.get("officers", [])),
            }
            companies.append(entry)
            for officer in co.get("officers", []):
                name = officer.get("officer", {}).get("name", "")
                if name:
                    identifiers.append(f"person:{name}")

        return {
            "input": original_input,
            "query": query,
            "found": bool(companies),
            "companies": companies,
            "officers": [],
            "extracted_identifiers": identifiers,
        }

    async def _search_officers(
        self,
        client: httpx.AsyncClient,
        query: str,
        params_extra: dict[str, str],
        original_input: str,
    ) -> dict[str, Any]:
        params = {"q": query, "per_page": "10", **params_extra}
        resp = await client.get(f"{_BASE_URL}/officers/search", params=params)
        if resp.status_code != 200:
            return {"input": original_input, "found": False, "companies": [], "officers": [], "extracted_identifiers": []}

        data = resp.json()
        raw_officers = data.get("results", {}).get("officers", [])

        identifiers: list[str] = []
        officers: list[dict[str, Any]] = []
        for item in raw_officers:
            off = item.get("officer", {})
            name = off.get("name", "")
            entry: dict[str, Any] = {
                "name": name,
                "position": off.get("position", ""),
                "start_date": off.get("start_date", ""),
                "end_date": off.get("end_date", ""),
                "company_name": off.get("company", {}).get("name", ""),
                "jurisdiction": off.get("company", {}).get("jurisdiction_code", ""),
            }
            officers.append(entry)
            if name:
                identifiers.append(f"person:{name}")

        return {
            "input": original_input,
            "query": query,
            "found": bool(officers),
            "companies": [],
            "officers": officers,
            "extracted_identifiers": identifiers,
        }
