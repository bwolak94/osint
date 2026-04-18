"""IOC Enricher — multi-source Indicator of Compromise enrichment pipeline.

Queries multiple free/freemium threat intelligence APIs concurrently and
aggregates their results into a unified :class:`EnrichmentResult`.

Supported sources:

  ============  ==========================  ======================
  Source        IOC types                   API key setting
  ============  ==========================  ======================
  AbuseIPDB     ip                          ``abuseipdb_api_key``
  AlienVault    ip, domain, hash, url       ``otx_api_key``
  OTX
  GreyNoise     ip                          (free community API,
  Community                                 no key required)
  URLhaus       url, domain                 (free, no key needed)
  ============  ==========================  ======================

API keys are read from :func:`src.config.get_settings`.  If a key is not
configured, that source is silently skipped so the pipeline degrades
gracefully.

Risk score aggregation (0–100):

  - AbuseIPDB   → ``abuseConfidenceScore`` (0–100) maps directly.
  - OTX         → pulse count × 5, capped at 80.
  - GreyNoise   → ``malicious`` → 80, ``suspicious`` → 40, else 0.
  - URLhaus     → ``query_status == "is_malware"`` → 90, else 0.

The final risk score is the max of all source scores.

Usage::

    enricher = IOCEnricher()
    result = await enricher.enrich("8.8.8.8", "ip")
    print(result.risk_score, result.tags)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from src.config import get_settings

log = structlog.get_logger()

_DEFAULT_TIMEOUT = 15.0  # seconds per HTTP request


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class EnrichmentResult:
    """Aggregated enrichment data for one IOC.

    Attributes:
        ioc_value:   The queried indicator value (e.g. ``"8.8.8.8"``).
        ioc_type:    Normalised type string: ``ip``, ``domain``, ``hash``, ``url``.
        sources:     Raw result dict keyed by source name.  Values are the
                     parsed JSON response or an error dict.
        aggregated:  Merged key findings across all sources.
        risk_score:  Composite risk score 0–100 (higher = more malicious).
        tags:        Classification tags such as ``malicious``, ``suspicious``,
                     ``scanner``, ``clean``.
    """

    ioc_value: str
    ioc_type: str
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    aggregated: dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.0
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Enricher
# ---------------------------------------------------------------------------


class IOCEnricher:
    """Concurrent multi-source IOC enrichment pipeline.

    Each ``_query_*`` method is responsible for one data source.  All
    sources are queried concurrently via :func:`asyncio.gather`; a timeout
    or HTTP error in one source does not prevent others from completing.
    """

    _VALID_IOC_TYPES = {"ip", "domain", "hash", "url"}

    async def enrich(self, ioc_value: str, ioc_type: str) -> EnrichmentResult:
        """Enrich a single IOC by querying all configured sources.

        Args:
            ioc_value: The indicator to look up (e.g. ``"evil.com"``).
            ioc_type:  One of ``ip``, ``domain``, ``hash``, ``url``.

        Returns:
            An :class:`EnrichmentResult` populated with all available data.
            Returns a minimal result with empty sources on complete failure.
        """
        ioc_type = ioc_type.lower().strip()
        if ioc_type not in self._VALID_IOC_TYPES:
            log.warning("Unknown IOC type", ioc_type=ioc_type, ioc_value=ioc_value)
            ioc_type = "domain"

        settings = get_settings()
        log.info("IOC enrichment started", ioc=ioc_value, type=ioc_type)

        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                tasks: dict[str, asyncio.Task[dict[str, Any]]] = {}

                # AbuseIPDB — IPs only, requires API key.
                if ioc_type == "ip" and settings.abuseipdb_api_key:
                    tasks["abuseipdb"] = asyncio.create_task(
                        self._query_abuseipdb(client, ioc_value, settings.abuseipdb_api_key)
                    )

                # AlienVault OTX — all types, requires API key.
                if settings.otx_api_key:
                    tasks["otx"] = asyncio.create_task(
                        self._query_otx(client, ioc_value, ioc_type, settings.otx_api_key)
                    )

                # GreyNoise community — IPs only, no key required.
                if ioc_type == "ip":
                    tasks["greynoise"] = asyncio.create_task(
                        self._query_greynoise(client, ioc_value)
                    )

                # URLhaus — URLs and domains, no key required.
                if ioc_type in ("url", "domain"):
                    tasks["urlhaus"] = asyncio.create_task(
                        self._query_urlhaus(client, ioc_value)
                    )

                if not tasks:
                    log.warning(
                        "No enrichment sources available — check API key configuration",
                        ioc=ioc_value,
                    )
                    return EnrichmentResult(ioc_value=ioc_value, ioc_type=ioc_type)

                raw_results = await asyncio.gather(*tasks.values(), return_exceptions=True)
                sources: dict[str, dict[str, Any]] = {}
                for name, result in zip(tasks.keys(), raw_results):
                    if isinstance(result, Exception):
                        log.warning(
                            "Enrichment source error",
                            source=name,
                            error=str(result),
                        )
                        sources[name] = {"error": str(result)}
                    else:
                        sources[name] = result  # type: ignore[assignment]

            aggregated, risk_score, tags = self._aggregate(sources, ioc_type)

            enrichment = EnrichmentResult(
                ioc_value=ioc_value,
                ioc_type=ioc_type,
                sources=sources,
                aggregated=aggregated,
                risk_score=round(risk_score, 1),
                tags=tags,
            )
            log.info(
                "IOC enrichment complete",
                ioc=ioc_value,
                sources=len(sources),
                risk_score=enrichment.risk_score,
                tags=tags,
            )
            return enrichment

        except Exception as exc:
            log.error("IOC enrichment failed", ioc=ioc_value, error=str(exc), exc_info=True)
            return EnrichmentResult(ioc_value=ioc_value, ioc_type=ioc_type)

    # ------------------------------------------------------------------
    # Source query methods
    # ------------------------------------------------------------------

    async def _query_abuseipdb(
        self,
        client: httpx.AsyncClient,
        ip: str,
        api_key: str,
    ) -> dict[str, Any]:
        """Query the AbuseIPDB v2 check endpoint.

        Docs: https://docs.abuseipdb.com/#check-endpoint
        Requires: ``abuseipdb_api_key`` in settings.
        """
        try:
            resp = await client.get(
                "https://api.abuseipdb.com/api/v2/check",
                headers={"Accept": "application/json", "Key": api_key},
                params={"ipAddress": ip, "maxAgeInDays": "90", "verbose": ""},
            )
            resp.raise_for_status()
            return resp.json().get("data", {})
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code}", "source": "abuseipdb"}
        except Exception as exc:
            return {"error": str(exc), "source": "abuseipdb"}

    async def _query_otx(
        self,
        client: httpx.AsyncClient,
        ioc: str,
        ioc_type: str,
        api_key: str,
    ) -> dict[str, Any]:
        """Query AlienVault OTX for threat intelligence pulses.

        Docs: https://otx.alienvault.com/assets/static/external_api.html
        Requires: ``otx_api_key`` in settings.
        """
        # Map internal type to OTX indicator type path segment.
        _type_map = {
            "ip": "IPv4",
            "domain": "domain",
            "hash": "file",
            "url": "url",
        }
        otx_type = _type_map.get(ioc_type, "domain")
        url = f"https://otx.alienvault.com/api/v1/indicators/{otx_type}/{ioc}/general"

        try:
            resp = await client.get(url, headers={"X-OTX-API-KEY": api_key})
            resp.raise_for_status()
            data = resp.json()
            return {
                "pulse_count": data.get("pulse_info", {}).get("count", 0),
                "tags": data.get("tags", []),
                "malware_families": data.get("malware_families", []),
                "sections": data.get("sections", []),
            }
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code}", "source": "otx"}
        except Exception as exc:
            return {"error": str(exc), "source": "otx"}

    async def _query_greynoise(
        self,
        client: httpx.AsyncClient,
        ip: str,
    ) -> dict[str, Any]:
        """Query the GreyNoise community API (no key required).

        Docs: https://developer.greynoise.io/reference/community-api
        """
        try:
            resp = await client.get(
                f"https://api.greynoise.io/v3/community/{ip}",
                headers={"Accept": "application/json"},
            )
            if resp.status_code == 404:
                return {"noise": False, "riot": False, "classification": "unknown"}
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code}", "source": "greynoise"}
        except Exception as exc:
            return {"error": str(exc), "source": "greynoise"}

    async def _query_urlhaus(
        self,
        client: httpx.AsyncClient,
        url_or_domain: str,
    ) -> dict[str, Any]:
        """Query the URLhaus lookup API (no key required).

        Docs: https://urlhaus-api.abuse.ch/#lookupurl / #lookupdomain
        """
        try:
            # Determine whether to use the URL or host lookup endpoint.
            if url_or_domain.startswith("http"):
                resp = await client.post(
                    "https://urlhaus-api.abuse.ch/v1/url/",
                    data={"url": url_or_domain},
                )
            else:
                resp = await client.post(
                    "https://urlhaus-api.abuse.ch/v1/host/",
                    data={"host": url_or_domain},
                )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code}", "source": "urlhaus"}
        except Exception as exc:
            return {"error": str(exc), "source": "urlhaus"}

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _aggregate(
        self,
        sources: dict[str, dict[str, Any]],
        ioc_type: str,
    ) -> tuple[dict[str, Any], float, list[str]]:
        """Merge source results into a unified summary.

        Returns:
            (aggregated_dict, risk_score_0_to_100, tags_list)
        """
        aggregated: dict[str, Any] = {}
        risk_scores: list[float] = []
        tags: set[str] = set()

        # --- AbuseIPDB ---
        abuse_data = sources.get("abuseipdb", {})
        if "error" not in abuse_data and abuse_data:
            score = float(abuse_data.get("abuseConfidenceScore", 0))
            risk_scores.append(score)
            aggregated["abuse_confidence"] = score
            aggregated["total_reports"] = abuse_data.get("totalReports", 0)
            aggregated["country"] = abuse_data.get("countryCode", "")
            aggregated["isp"] = abuse_data.get("isp", "")
            if score >= 75:
                tags.add("malicious")
            elif score >= 25:
                tags.add("suspicious")

        # --- OTX ---
        otx_data = sources.get("otx", {})
        if "error" not in otx_data and otx_data:
            pulse_count = int(otx_data.get("pulse_count", 0))
            otx_score = min(80.0, pulse_count * 5.0)
            risk_scores.append(otx_score)
            aggregated["otx_pulse_count"] = pulse_count
            aggregated["otx_tags"] = otx_data.get("tags", [])
            aggregated["malware_families"] = otx_data.get("malware_families", [])
            if pulse_count > 0:
                tags.add("malicious" if pulse_count >= 5 else "suspicious")

        # --- GreyNoise ---
        gn_data = sources.get("greynoise", {})
        if "error" not in gn_data and gn_data:
            classification = gn_data.get("classification", "unknown")
            gn_score: float = 0.0
            if classification == "malicious":
                gn_score = 80.0
                tags.add("malicious")
            elif classification == "suspicious":
                gn_score = 40.0
                tags.add("suspicious")
            elif gn_data.get("riot", False):
                tags.add("scanner")
            risk_scores.append(gn_score)
            aggregated["greynoise_classification"] = classification
            aggregated["greynoise_name"] = gn_data.get("name", "")
            aggregated["greynoise_riot"] = gn_data.get("riot", False)

        # --- URLhaus ---
        uh_data = sources.get("urlhaus", {})
        if "error" not in uh_data and uh_data:
            query_status = uh_data.get("query_status", "")
            uh_score: float = 0.0
            if query_status == "is_malware":
                uh_score = 90.0
                tags.add("malicious")
            elif query_status == "is_offline":
                uh_score = 30.0
                tags.add("suspicious")
            risk_scores.append(uh_score)
            aggregated["urlhaus_status"] = query_status
            aggregated["urlhaus_urls_count"] = len(uh_data.get("urls", []))

        final_score = max(risk_scores) if risk_scores else 0.0

        if not tags:
            tags.add("clean")

        return aggregated, final_score, sorted(tags)
