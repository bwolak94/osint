"""VirusTotal scanner — threat intelligence for domains, IPs, and URLs."""

from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class VirusTotalScanner(BaseOsintScanner):
    """Queries VirusTotal for threat intelligence on domains, IPs, and URLs.

    Requires a VT API key (free tier: 4 requests/minute).
    """

    scanner_name = "virustotal"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS, ScanInputType.URL})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        from src.config import get_settings

        settings = get_settings()
        api_key = settings.virustotal_api_key if hasattr(settings, "virustotal_api_key") else ""

        if not api_key:
            return {"_stub": True, "note": "VirusTotal API key not configured", "extracted_identifiers": []}

        try:
            import httpx

            headers = {"x-apikey": api_key}

            if input_type == ScanInputType.DOMAIN:
                url = f"https://www.virustotal.com/api/v3/domains/{input_value}"
            elif input_type == ScanInputType.IP_ADDRESS:
                url = f"https://www.virustotal.com/api/v3/ip_addresses/{input_value}"
            else:
                import base64

                url_id = base64.urlsafe_b64encode(input_value.encode()).decode().rstrip("=")
                url = f"https://www.virustotal.com/api/v3/urls/{url_id}"

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 404:
                    return {"found": False, "input": input_value, "extracted_identifiers": []}
                resp.raise_for_status()
                data = resp.json()

            attrs = data.get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats", {})

            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            harmless = stats.get("harmless", 0)
            undetected = stats.get("undetected", 0)

            reputation = attrs.get("reputation", 0)
            categories = attrs.get("categories", {})

            identifiers: list[str] = []
            if malicious > 0:
                identifiers.append(f"threat:malicious_{malicious}")
            if suspicious > 0:
                identifiers.append(f"threat:suspicious_{suspicious}")

            return {
                "found": True,
                "input": input_value,
                "malicious_detections": malicious,
                "suspicious_detections": suspicious,
                "harmless_detections": harmless,
                "undetected": undetected,
                "total_engines": malicious + suspicious + harmless + undetected,
                "reputation_score": reputation,
                "categories": categories,
                "extracted_identifiers": identifiers,
            }
        except ImportError:
            return {"_stub": True, "extracted_identifiers": []}
        except Exception as e:
            log.error("VirusTotal scan error", error=str(e))
            raise
