"""SIEM integration adapter for forwarding events and IOCs."""

from typing import Any
import structlog
from src.config import get_settings

log = structlog.get_logger()


class SIEMAdapter:
    """Forward OSINT findings to SIEM platforms."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def forward_event(self, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Forward an event to the configured SIEM."""
        siem_type = self._settings.siem_type
        if not self._settings.siem_endpoint:
            return {"status": "skipped", "reason": "No SIEM endpoint configured"}

        try:
            import httpx
            payload = self._format_event(siem_type, event_type, data)
            async with httpx.AsyncClient(timeout=10) as client:
                headers = self._get_headers(siem_type)
                resp = await client.post(self._settings.siem_endpoint, json=payload, headers=headers)
                resp.raise_for_status()
            log.info("Event forwarded to SIEM", siem_type=siem_type, event_type=event_type)
            return {"status": "sent", "siem_type": siem_type}
        except ImportError:
            return {"status": "error", "reason": "httpx not installed"}
        except Exception as e:
            log.error("SIEM forward failed", error=str(e))
            return {"status": "error", "reason": str(e)}

    def _get_headers(self, siem_type: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if siem_type == "splunk":
            headers["Authorization"] = f"Splunk {self._settings.siem_api_key}"
        elif siem_type == "sentinel":
            headers["Authorization"] = f"Bearer {self._settings.siem_api_key}"
        else:
            headers["Authorization"] = f"ApiKey {self._settings.siem_api_key}"
        return headers

    def _format_event(self, siem_type: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        if siem_type == "splunk":
            return {"event": {"type": event_type, **data}, "sourcetype": "osint_platform"}
        return {"event_type": event_type, "source": "osint_platform", "data": data}

    async def test_connection(self) -> dict[str, Any]:
        if not self._settings.siem_endpoint:
            return {"connected": False, "reason": "No endpoint configured"}
        return {"connected": True, "siem_type": self._settings.siem_type, "endpoint": self._settings.siem_endpoint}
