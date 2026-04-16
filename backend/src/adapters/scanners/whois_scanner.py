"""WHOIS scanner — domain ownership and registration data."""

from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class WhoisScanner(BaseOsintScanner):
    """Queries WHOIS data for a domain name.

    Returns registrant info, registrar, creation/expiry dates,
    nameservers, and status.
    """

    scanner_name = "whois"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            import httpx

            # Use a public WHOIS API
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"https://rdap.org/domain/{input_value}",
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    return {
                        "domain": input_value,
                        "found": False,
                        "extracted_identifiers": [],
                    }

                data = resp.json()

                # Extract useful fields
                name = data.get("name", input_value)
                registrar = None
                for entity in data.get("entities", []):
                    if "registrar" in entity.get("roles", []):
                        vcard = entity.get("vcardArray", [None, []])[1] if entity.get("vcardArray") else []
                        for field in vcard:
                            if field[0] == "fn":
                                registrar = field[3]

                nameservers = [ns.get("ldhName", "") for ns in data.get("nameservers", [])]
                status = data.get("status", [])

                events = {}
                for event in data.get("events", []):
                    events[event.get("eventAction", "")] = event.get("eventDate", "")

                identifiers = [f"domain:{input_value}"]
                if registrar:
                    identifiers.append(f"registrar:{registrar}")
                for ns in nameservers:
                    if ns:
                        identifiers.append(f"nameserver:{ns}")

                return {
                    "domain": input_value,
                    "found": True,
                    "name": name,
                    "registrar": registrar,
                    "nameservers": nameservers,
                    "status": status,
                    "registration_date": events.get("registration", ""),
                    "expiration_date": events.get("expiration", ""),
                    "last_update": events.get("last changed", ""),
                    "extracted_identifiers": identifiers,
                }
        except ImportError:
            return {"domain": input_value, "found": False, "extracted_identifiers": [], "_stub": True}
        except Exception as e:
            log.error("WHOIS scan error", error=str(e))
            raise
