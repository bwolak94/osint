"""SEC EDGAR scanner — company filings and executive search via free EDGAR API."""

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
_COMPANY_SEARCH_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_HEADERS = {"User-Agent": "OSINT-Platform contact@example.com", "Accept-Encoding": "gzip, deflate"}


def _extract_company_name_from_domain(domain: str) -> str:
    name = domain.lower().removeprefix("www.")
    return name.split(".")[0]


class SECEdgarScanner(BaseOsintScanner):
    scanner_name = "sec_edgar"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.USERNAME})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20, headers=_HEADERS) as client:
            if input_type == ScanInputType.DOMAIN:
                query = _extract_company_name_from_domain(input_value)
            else:
                query = input_value
            return await self._search_edgar(client, query, input_value)

    async def _search_edgar(
        self, client: httpx.AsyncClient, query: str, original_input: str
    ) -> dict[str, Any]:
        # Step 1: find CIK for company
        cik, company_name, sic_industry, state_of_incorporation = await self._find_cik(client, query)

        filings: list[dict[str, Any]] = []
        executives: list[str] = []
        identifiers: list[str] = []

        if cik:
            filings, executives = await self._get_filings(client, cik)
            for exec_name in executives:
                identifiers.append(f"person:{exec_name}")
            for filing in filings[:5]:
                if filing.get("url"):
                    identifiers.append(f"url:{filing['url']}")

        return {
            "input": original_input,
            "query": query,
            "found": bool(cik),
            "company_name": company_name,
            "cik": cik,
            "sic_industry": sic_industry,
            "state_of_incorporation": state_of_incorporation,
            "filings": filings,
            "executives": executives,
            "extracted_identifiers": identifiers,
        }

    async def _find_cik(
        self, client: httpx.AsyncClient, query: str
    ) -> tuple[str, str, str, str]:
        params = {
            "company": query,
            "CIK": "",
            "type": "10-K",
            "dateb": "",
            "owner": "include",
            "count": "10",
            "output": "atom",
            "action": "getcompany",
        }
        try:
            resp = await client.get(_COMPANY_SEARCH_URL, params=params)
            if resp.status_code != 200:
                return "", "", "", ""
            text = resp.text
            # Parse CIK from Atom XML: <content type="text">CIK 0000012345</content> or similar patterns
            cik_match = re.search(r"CIK=(\d+)", text)
            name_match = re.search(r"<company-name>(.*?)</company-name>", text)
            sic_match = re.search(r"<assigned-sic-desc>(.*?)</assigned-sic-desc>", text)
            state_match = re.search(r"<state-of-incorporation>(.*?)</state-of-incorporation>", text)
            cik = cik_match.group(1) if cik_match else ""
            company_name = name_match.group(1) if name_match else ""
            sic = sic_match.group(1) if sic_match else ""
            state = state_match.group(1) if state_match else ""
            return cik, company_name, sic, state
        except Exception as exc:
            log.warning("SEC EDGAR CIK lookup failed", query=query, error=str(exc))
            return "", "", "", ""

    async def _get_filings(
        self, client: httpx.AsyncClient, cik: str
    ) -> tuple[list[dict[str, Any]], list[str]]:
        cik_padded = cik.zfill(10)
        url = _SUBMISSIONS_URL.format(cik=cik_padded)
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return [], []
            data = resp.json()
            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            descriptions = recent.get("primaryDocument", [])
            accession_numbers = recent.get("accessionNumber", [])

            filings: list[dict[str, Any]] = []
            for i in range(min(10, len(forms))):
                acc = accession_numbers[i].replace("-", "") if i < len(accession_numbers) else ""
                doc = descriptions[i] if i < len(descriptions) else ""
                filing_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}" if acc and doc else ""
                )
                filings.append(
                    {
                        "type": forms[i],
                        "date": dates[i] if i < len(dates) else "",
                        "description": doc,
                        "url": filing_url,
                    }
                )

            # Extract executives from companyFacts or officers array if present
            executives: list[str] = []
            for officer in data.get("officers", []):
                name = officer.get("name", "")
                if name:
                    executives.append(name)

            return filings, executives
        except Exception as exc:
            log.warning("SEC EDGAR filings fetch failed", cik=cik, error=str(exc))
            return [], []
