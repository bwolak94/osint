"""CISA Known Exploited Vulnerabilities (KEV) catalogue ingestor."""

from __future__ import annotations

import httpx
import structlog

from src.adapters.rag.ingestion.base_ingestor import BaseIngestor, RawDocument

log = structlog.get_logger(__name__)

_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


class CISAKEVIngestor(BaseIngestor):
    """Downloads the full CISA KEV JSON catalogue and emits one RawDocument per entry.

    The catalogue is small (< 2 MB) so a full refresh on every nightly run is
    acceptable. Existing rows are upserted by ``source_id`` (CVE ID).
    """

    def should_skip(self, doc: RawDocument) -> bool:
        # Always upsert — the catalogue is updated frequently.
        return False

    async def fetch(self) -> list[RawDocument]:
        docs: list[RawDocument] = []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(_KEV_URL)
                resp.raise_for_status()
                data: dict = resp.json()

            for vuln in data.get("vulnerabilities", []):
                doc = self._parse_entry(vuln)
                if doc is not None:
                    docs.append(doc)

            log.info("cisa_kev_ingestor.fetch.complete", count=len(docs))
        except httpx.HTTPStatusError as exc:
            log.error("cisa_kev_ingestor.fetch.http_error", status=exc.response.status_code, error=str(exc))
        except Exception as exc:
            log.error("cisa_kev_ingestor.fetch.error", error=str(exc))

        return docs

    @staticmethod
    def _parse_entry(vuln: dict) -> RawDocument | None:
        cve_id: str = vuln.get("cveID", "")
        if not cve_id:
            return None

        vuln_name: str = vuln.get("vulnerabilityName", "")
        short_desc: str = vuln.get("shortDescription", "")
        content = f"{cve_id}: {vuln_name} - {short_desc}"

        return RawDocument(
            source="cisa-kev",
            source_id=cve_id,
            content=content,
            metadata={
                "cve_id": cve_id,
                "vendor_project": vuln.get("vendorProject", ""),
                "product": vuln.get("product", ""),
                "kev": True,
                "date_added": vuln.get("dateAdded"),
                "due_date": vuln.get("dueDate"),
                "required_action": vuln.get("requiredAction", ""),
                "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
            },
        )
