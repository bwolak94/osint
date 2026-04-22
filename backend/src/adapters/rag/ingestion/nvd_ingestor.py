"""NVD CVE 2.0 API ingestor — delta sync for the last 48 hours."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import structlog

from src.adapters.rag.ingestion.base_ingestor import BaseIngestor, RawDocument
from src.config import get_settings

log = structlog.get_logger(__name__)

_NVD_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_API_KEY_HEADER = "apiKey"
_DELTA_HOURS = 48


class NVDIngestor(BaseIngestor):
    """Fetches CVEs modified in the last 48 hours from the NVD CVE 2.0 API.

    Uses delta sync to avoid re-ingesting the entire catalogue on every run.
    An optional NVD API key (``nvd_api_key`` setting) lifts the rate limit
    from 5 req/30 s to 50 req/30 s.
    """

    def should_skip(self, doc: RawDocument) -> bool:
        # Upsert semantics: always replace stale CVE records.
        return False

    async def fetch(self) -> list[RawDocument]:
        settings = get_settings()
        now = datetime.now(tz=timezone.utc)
        since = now - timedelta(hours=_DELTA_HOURS)

        params: dict[str, str | int] = {
            "lastModStartDate": since.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "lastModEndDate": now.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "resultsPerPage": 2000,
        }

        headers: dict[str, str] = {}
        nvd_api_key: str = getattr(settings, "nvd_api_key", "")
        if nvd_api_key:
            headers[_API_KEY_HEADER] = nvd_api_key

        docs: list[RawDocument] = []

        try:
            async with httpx.AsyncClient(timeout=60, headers=headers) as client:
                resp = await client.get(_NVD_BASE_URL, params=params)
                resp.raise_for_status()
                data: dict = resp.json()

            for vuln in data.get("vulnerabilities", []):
                cve = vuln.get("cve", {})
                doc = self._parse_cve(cve)
                if doc is not None:
                    docs.append(doc)

            log.info("nvd_ingestor.fetch.complete", count=len(docs), delta_hours=_DELTA_HOURS)
        except httpx.HTTPStatusError as exc:
            log.error("nvd_ingestor.fetch.http_error", status=exc.response.status_code, error=str(exc))
        except Exception as exc:
            log.error("nvd_ingestor.fetch.error", error=str(exc))

        return docs

    def _parse_cve(self, cve: dict) -> Optional[RawDocument]:
        cve_id: str = cve.get("id", "")
        if not cve_id:
            return None

        description = next(
            (d["value"] for d in cve.get("descriptions", []) if d.get("lang") == "en"),
            "",
        )

        cvss = self._extract_cvss(cve)
        cwe = self._extract_cwe(cve)

        content = f"{cve_id}: {description}"

        return RawDocument(
            source="nvd",
            source_id=cve_id,
            content=content,
            metadata={
                "cve_id": cve_id,
                "cvss_v3": cvss,
                "cwe": cwe,
                "published": cve.get("published"),
                "last_modified": cve.get("lastModified"),
                "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
            },
        )

    @staticmethod
    def _extract_cvss(cve: dict) -> Optional[float]:
        metrics = cve.get("metrics", {})
        for version_key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            entries = metrics.get(version_key)
            if entries:
                try:
                    return float(entries[0]["cvssData"]["baseScore"])
                except (KeyError, IndexError, TypeError, ValueError):
                    continue
        return None

    @staticmethod
    def _extract_cwe(cve: dict) -> Optional[int]:
        for weakness in cve.get("weaknesses", []):
            for desc in weakness.get("description", []):
                value: str = desc.get("value", "")
                if value.startswith("CWE-"):
                    try:
                        return int(value.replace("CWE-", ""))
                    except ValueError:
                        continue
        return None
