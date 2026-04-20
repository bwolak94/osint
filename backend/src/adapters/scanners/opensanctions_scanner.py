"""OpenSanctions scanner — sanctions list and PEP matching."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_SEARCH_URL = "https://api.opensanctions.org/search/default"
_HEADERS = {"Accept": "application/json"}


def _query_from_input(input_value: str, input_type: ScanInputType) -> str:
    """Derive a search query string from the input."""
    if input_type == ScanInputType.DOMAIN:
        # Use the domain label as an org name hint
        name = input_value.lower().removeprefix("www.").split(".")[0]
        return name
    return input_value


class OpenSanctionsScanner(BaseOsintScanner):
    scanner_name = "opensanctions"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.USERNAME, ScanInputType.EMAIL})
    cache_ttl = 86400

    def __init__(self, api_key: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        query = _query_from_input(input_value, input_type)
        headers = dict(_HEADERS)
        if self._api_key:
            headers["Authorization"] = f"ApiKey {self._api_key}"

        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            return await self._search(client, query, input_value)

    async def _search(
        self, client: httpx.AsyncClient, query: str, original_input: str
    ) -> dict[str, Any]:
        params = {"q": query, "limit": "10"}
        try:
            resp = await client.get(_SEARCH_URL, params=params)
            if resp.status_code != 200:
                return {
                    "input": original_input,
                    "found": False,
                    "matches": [],
                    "is_sanctioned": False,
                    "is_pep": False,
                    "datasets_matched": [],
                    "extracted_identifiers": [],
                }
            data = resp.json()
            results = data.get("results", [])
        except Exception as exc:
            log.warning("OpenSanctions search failed", query=query, error=str(exc))
            return {
                "input": original_input,
                "found": False,
                "matches": [],
                "is_sanctioned": False,
                "is_pep": False,
                "datasets_matched": [],
                "extracted_identifiers": [],
            }

        matches: list[dict[str, Any]] = []
        is_sanctioned = False
        is_pep = False
        datasets_matched: list[str] = []

        for result in results:
            props = result.get("properties", {})
            datasets = result.get("datasets", [])
            datasets_matched.extend(d for d in datasets if d not in datasets_matched)

            schema = result.get("schema", "")
            if schema in ("Sanction", "SanctionedEntity") or any(
                "sanction" in d.lower() or "ofac" in d.lower() or "eu_fto" in d.lower()
                for d in datasets
            ):
                is_sanctioned = True
            if schema == "Person" and any("pep" in d.lower() for d in datasets):
                is_pep = True

            matches.append(
                {
                    "entity_name": result.get("caption", ""),
                    "schema": schema,
                    "datasets": datasets,
                    "aliases": props.get("alias", []),
                    "birth_date": props.get("birthDate", []),
                    "countries": props.get("country", []),
                    "sanctions_programs": props.get("program", []),
                    "score": result.get("score", 0.0),
                }
            )

        return {
            "input": original_input,
            "query": query,
            "found": bool(matches),
            "matches": matches,
            "is_sanctioned": is_sanctioned,
            "is_pep": is_pep,
            "datasets_matched": datasets_matched,
            "extracted_identifiers": [],
        }
