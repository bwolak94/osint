"""OpenCTI bidirectional connector.

Pushes OSINT investigation bundles (STIX 2.1) to an OpenCTI instance and
pulls back enriched indicators for correlation.

Two transport surfaces are used:
    STIX import   — POST {url}/api/taxii2/root/collections/default/objects
    GraphQL API   — POST {url}/graphql

All network calls use ``httpx.AsyncClient`` with a sensible timeout.
If the platform is unconfigured (missing URL/token) every method returns a
safe empty value rather than raising.

Usage::

    adapter = OpenCTIAdapter()
    if adapter.is_configured():
        await adapter.push_investigation(bundle.to_json())
        indicators = await adapter.pull_indicators(["ipv4-addr", "domain-name"])
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.config import get_settings

log = structlog.get_logger()

# Default timeouts (seconds)
_CONNECT_TIMEOUT = 10.0
_READ_TIMEOUT = 30.0


class OpenCTIAdapter:
    """Push investigations to OpenCTI and pull indicators back.

    All public methods are coroutines so they can be awaited inside
    FastAPI route handlers or Celery async tasks without blocking the loop.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._url: str = getattr(settings, "opencti_url", "").rstrip("/")
        self._token: str = getattr(settings, "opencti_api_token", "")

    # ------------------------------------------------------------------
    # Configuration guard
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        """Return True only when both URL and token are set."""
        return bool(self._url and self._token)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        """Return a pre-configured AsyncClient instance."""
        return httpx.AsyncClient(
            headers=self._headers,
            timeout=httpx.Timeout(connect=_CONNECT_TIMEOUT, read=_READ_TIMEOUT, write=_READ_TIMEOUT, pool=_CONNECT_TIMEOUT),
        )

    # ------------------------------------------------------------------
    # Push
    # ------------------------------------------------------------------

    async def push_investigation(self, stix_bundle_json: str) -> dict[str, Any]:
        """Import a STIX 2.1 bundle into OpenCTI via the TAXII2 endpoint.

        OpenCTI's TAXII2 collection endpoint accepts a standard STIX bundle
        and returns a summary of the import operation.

        Args:
            stix_bundle_json: JSON string of a complete STIX 2.1 bundle.

        Returns:
            Dict with keys success, report_id, objects_created.
            Returns {success: False} on any error.
        """
        if not self.is_configured():
            log.warning("OpenCTI push skipped — adapter not configured")
            return {"success": False, "reason": "not_configured"}

        endpoint = f"{self._url}/api/taxii2/root/collections/default/objects"

        try:
            async with self._client() as client:
                response = await client.post(
                    endpoint,
                    content=stix_bundle_json,
                    headers={**self._headers, "Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

                report_id: str = data.get("id", "")
                objects_created: int = data.get("x_opencti_ingest_count", 0)

                log.info(
                    "OpenCTI push successful",
                    report_id=report_id,
                    objects_created=objects_created,
                )
                return {
                    "success": True,
                    "report_id": report_id,
                    "objects_created": objects_created,
                }

        except httpx.HTTPStatusError as exc:
            log.error(
                "OpenCTI push HTTP error",
                status=exc.response.status_code,
                detail=exc.response.text[:200],
            )
            return {"success": False, "reason": f"http_{exc.response.status_code}"}
        except httpx.RequestError as exc:
            log.error("OpenCTI push connection error", error=str(exc))
            return {"success": False, "reason": "connection_error"}

    # ------------------------------------------------------------------
    # Pull
    # ------------------------------------------------------------------

    async def pull_indicators(
        self,
        indicator_types: list[str] | None = None,
        limit: int = 100,
        tlp_level: str = "white",
    ) -> list[dict[str, Any]]:
        """Query OpenCTI's GraphQL API for threat indicators.

        Args:
            indicator_types: STIX SCO types to filter by, e.g.
                             ["ipv4-addr", "domain-name", "url"].
                             If None, returns all indicator types.
            limit:           Maximum number of indicators to retrieve.
            tlp_level:       TLP marking to filter by (white, green, amber, red).

        Returns:
            List of dicts with keys type, value, confidence, labels, tlp.
            Returns empty list on error.
        """
        if not self.is_configured():
            log.warning("OpenCTI pull skipped — adapter not configured")
            return []

        types_filter: list[str] = indicator_types or [
            "ipv4-addr",
            "domain-name",
            "url",
            "email-addr",
            "file",
        ]

        # Build a minimal GraphQL query for indicators
        gql_query = """
        query PullIndicators($first: Int, $filters: FilterGroup) {
          indicators(first: $first, filters: $filters) {
            edges {
              node {
                id
                name
                indicator_types
                confidence
                objectLabel { value }
                objectMarking { definition }
                pattern
                pattern_type
              }
            }
          }
        }
        """

        variables: dict[str, Any] = {
            "first": limit,
            "filters": {
                "mode": "and",
                "filters": [
                    {
                        "key": "pattern_type",
                        "values": ["stix"],
                        "operator": "eq",
                        "mode": "or",
                    }
                ],
                "filterGroups": [],
            },
        }

        try:
            async with self._client() as client:
                response = await client.post(
                    f"{self._url}/graphql",
                    json={"query": gql_query, "variables": variables},
                )
                response.raise_for_status()
                data = response.json()

            edges = (
                data.get("data", {})
                .get("indicators", {})
                .get("edges", [])
            )
            results: list[dict[str, Any]] = []
            for edge in edges:
                node = edge.get("node", {})
                labels = [lbl.get("value", "") for lbl in node.get("objectLabel", [])]
                markings = [m.get("definition", "") for m in node.get("objectMarking", [])]
                results.append(
                    {
                        "type": (node.get("indicator_types") or [None])[0],
                        "value": node.get("name", ""),
                        "confidence": node.get("confidence", 0),
                        "labels": labels,
                        "tlp": next((m for m in markings if "TLP" in m), "TLP:WHITE"),
                    }
                )

            log.info("OpenCTI pull complete", count=len(results), tlp=tlp_level)
            return results

        except httpx.HTTPStatusError as exc:
            log.error(
                "OpenCTI pull HTTP error",
                status=exc.response.status_code,
                detail=exc.response.text[:200],
            )
            return []
        except httpx.RequestError as exc:
            log.error("OpenCTI pull connection error", error=str(exc))
            return []

    # ------------------------------------------------------------------
    # Create report
    # ------------------------------------------------------------------

    async def create_report(
        self,
        name: str,
        description: str,
        objects: list[str],
    ) -> dict[str, Any]:
        """Create an OpenCTI Report entity via GraphQL mutation.

        Args:
            name:        Report display name.
            description: Analyst notes / executive summary.
            objects:     List of OpenCTI object IDs to attach to the report.

        Returns:
            Dict with keys id, name on success; {success: False} on error.
        """
        if not self.is_configured():
            log.warning("OpenCTI create_report skipped — adapter not configured")
            return {"success": False, "reason": "not_configured"}

        mutation = """
        mutation CreateReport($input: ReportAddInput!) {
          reportAdd(input: $input) {
            id
            name
            published
          }
        }
        """

        from datetime import datetime, timezone

        variables = {
            "input": {
                "name": name,
                "description": description,
                "published": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "report_types": ["threat-report"],
                "objects": objects,
            }
        }

        try:
            async with self._client() as client:
                response = await client.post(
                    f"{self._url}/graphql",
                    json={"query": mutation, "variables": variables},
                )
                response.raise_for_status()
                data = response.json()

            report_data = data.get("data", {}).get("reportAdd", {})
            log.info(
                "OpenCTI report created",
                report_id=report_data.get("id"),
                name=report_data.get("name"),
            )
            return report_data

        except httpx.HTTPStatusError as exc:
            log.error(
                "OpenCTI create_report HTTP error",
                status=exc.response.status_code,
                detail=exc.response.text[:200],
            )
            return {"success": False, "reason": f"http_{exc.response.status_code}"}
        except httpx.RequestError as exc:
            log.error("OpenCTI create_report connection error", error=str(exc))
            return {"success": False, "reason": "connection_error"}

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Verify connectivity to the OpenCTI instance.

        Sends a minimal GraphQL introspection query and checks the response.

        Returns:
            True if the platform responds with a 200 OK, False otherwise.
        """
        if not self.is_configured():
            log.debug("OpenCTI health_check skipped — not configured")
            return False

        probe = '{"query": "{ __typename }"}'
        try:
            async with self._client() as client:
                response = await client.post(
                    f"{self._url}/graphql",
                    content=probe,
                )
            is_up = response.status_code == 200
            log.info("OpenCTI health check", reachable=is_up, status=response.status_code)
            return is_up

        except httpx.RequestError as exc:
            log.warning("OpenCTI health check failed", error=str(exc))
            return False
