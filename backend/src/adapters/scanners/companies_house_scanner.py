"""UK Companies House scanner — corporate registry, officers, and beneficial ownership."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_BASE_URL = "https://api.company-information.service.gov.uk"


def _extract_company_name_from_domain(domain: str) -> str:
    name = domain.lower().removeprefix("www.").split(".")[0]
    return name


class CompaniesHouseScanner(BaseOsintScanner):
    scanner_name = "companies_house"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.USERNAME})
    cache_ttl = 86400

    def __init__(self, api_key: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        if not self._api_key:
            log.warning("Companies House API key not configured")
            return {
                "input": input_value,
                "found": False,
                "error": "Companies House API key required",
                "companies": [],
                "officers": [],
                "psc_list": [],
                "extracted_identifiers": [],
            }

        auth = (self._api_key, "")
        if input_type == ScanInputType.DOMAIN:
            query = _extract_company_name_from_domain(input_value)
        else:
            query = input_value

        async with httpx.AsyncClient(timeout=20, auth=auth) as client:
            return await self._search(client, query, input_value)

    async def _search(
        self, client: httpx.AsyncClient, query: str, original_input: str
    ) -> dict[str, Any]:
        resp = await client.get(
            f"{_BASE_URL}/search/companies", params={"q": query, "items_per_page": "10"}
        )
        if resp.status_code != 200:
            return {
                "input": original_input,
                "found": False,
                "companies": [],
                "officers": [],
                "psc_list": [],
                "extracted_identifiers": [],
            }

        data = resp.json()
        raw_items = data.get("items", [])

        companies: list[dict[str, Any]] = []
        all_officers: list[dict[str, Any]] = []
        all_psc: list[dict[str, Any]] = []
        identifiers: list[str] = []

        for item in raw_items:
            co_number = item.get("company_number", "")
            companies.append(
                {
                    "name": item.get("title", ""),
                    "number": co_number,
                    "status": item.get("company_status", ""),
                    "type": item.get("company_type", ""),
                    "date_of_creation": item.get("date_of_creation", ""),
                    "registered_office": item.get("address_snippet", ""),
                }
            )

            if co_number:
                officers = await self._get_officers(client, co_number)
                psc_list = await self._get_psc(client, co_number)
                all_officers.extend(officers)
                all_psc.extend(psc_list)
                for off in officers:
                    name = off.get("name", "")
                    if name:
                        identifiers.append(f"person:{name}")
                for psc in psc_list:
                    name = psc.get("name", "")
                    if name:
                        identifiers.append(f"person:{name}")

        return {
            "input": original_input,
            "query": query,
            "found": bool(companies),
            "companies": companies,
            "officers": all_officers,
            "psc_list": all_psc,
            "extracted_identifiers": identifiers,
        }

    async def _get_officers(
        self, client: httpx.AsyncClient, company_number: str
    ) -> list[dict[str, Any]]:
        try:
            resp = await client.get(f"{_BASE_URL}/company/{company_number}/officers")
            if resp.status_code != 200:
                return []
            data = resp.json()
            officers: list[dict[str, Any]] = []
            for item in data.get("items", []):
                officers.append(
                    {
                        "name": item.get("name", ""),
                        "role": item.get("officer_role", ""),
                        "appointed_on": item.get("appointed_on", ""),
                        "resigned_on": item.get("resigned_on", ""),
                        "nationality": item.get("nationality", ""),
                    }
                )
            return officers
        except Exception as exc:
            log.warning("Companies House officers fetch failed", company=company_number, error=str(exc))
            return []

    async def _get_psc(
        self, client: httpx.AsyncClient, company_number: str
    ) -> list[dict[str, Any]]:
        try:
            resp = await client.get(
                f"{_BASE_URL}/company/{company_number}/persons-with-significant-control"
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            psc_list: list[dict[str, Any]] = []
            for item in data.get("items", []):
                psc_list.append(
                    {
                        "name": item.get("name", ""),
                        "nat_of_control": item.get("natures_of_control", []),
                        "country_of_residence": item.get("country_of_residence", ""),
                        "nationality": item.get("nationality", ""),
                    }
                )
            return psc_list
        except Exception as exc:
            log.warning("Companies House PSC fetch failed", company=company_number, error=str(exc))
            return []
