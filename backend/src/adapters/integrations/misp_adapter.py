"""MISP bi-directional sync adapter."""

from typing import Any
from uuid import UUID
import structlog
from src.config import get_settings

log = structlog.get_logger()


class MISPAdapter:
    """Bi-directional sync with MISP threat intelligence platform."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def push_event(self, investigation_id: str, title: str, iocs: list[dict[str, Any]]) -> dict[str, Any]:
        """Push an OSINT investigation as a MISP event."""
        if not self._settings.misp_url:
            return {"status": "skipped", "reason": "No MISP URL configured"}

        try:
            import httpx
            event_data = {
                "Event": {
                    "info": title,
                    "distribution": "0",
                    "threat_level_id": "2",
                    "analysis": "2",
                    "Tag": [{"name": "osint-platform"}, {"name": f"investigation:{investigation_id}"}],
                    "Attribute": [self._ioc_to_attribute(ioc) for ioc in iocs],
                }
            }
            async with httpx.AsyncClient(timeout=15, verify=self._settings.misp_verify_ssl) as client:
                resp = await client.post(
                    f"{self._settings.misp_url}/events",
                    json=event_data,
                    headers={"Authorization": self._settings.misp_api_key, "Content-Type": "application/json"},
                )
                resp.raise_for_status()
                result = resp.json()
            log.info("Event pushed to MISP", investigation_id=investigation_id)
            return {"status": "pushed", "misp_event_id": result.get("Event", {}).get("id")}
        except ImportError:
            return {"status": "error", "reason": "httpx not installed"}
        except Exception as e:
            log.error("MISP push failed", error=str(e))
            return {"status": "error", "reason": str(e)}

    async def pull_events(self, tags: list[str] | None = None, limit: int = 50) -> dict[str, Any]:
        """Pull events from MISP."""
        if not self._settings.misp_url:
            return {"status": "skipped", "events": [], "reason": "No MISP URL configured"}

        try:
            import httpx
            body: dict[str, Any] = {"returnFormat": "json", "limit": limit}
            if tags:
                body["tags"] = tags
            async with httpx.AsyncClient(timeout=15, verify=self._settings.misp_verify_ssl) as client:
                resp = await client.post(
                    f"{self._settings.misp_url}/events/restSearch",
                    json=body,
                    headers={"Authorization": self._settings.misp_api_key, "Content-Type": "application/json"},
                )
                resp.raise_for_status()
                events = resp.json().get("response", [])
            return {"status": "ok", "events": events, "count": len(events)}
        except ImportError:
            return {"status": "error", "events": [], "reason": "httpx not installed"}
        except Exception as e:
            log.error("MISP pull failed", error=str(e))
            return {"status": "error", "events": [], "reason": str(e)}

    def _ioc_to_attribute(self, ioc: dict[str, Any]) -> dict[str, Any]:
        type_map = {"ip": "ip-dst", "domain": "domain", "url": "url", "email": "email-src", "hash": "md5"}
        return {
            "type": type_map.get(ioc.get("type", ""), "text"),
            "value": ioc.get("value", ""),
            "comment": f"Source: {ioc.get('source_scanner', 'unknown')}",
            "to_ids": True,
        }

    async def test_connection(self) -> dict[str, Any]:
        if not self._settings.misp_url:
            return {"connected": False, "reason": "No MISP URL configured"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5, verify=self._settings.misp_verify_ssl) as client:
                resp = await client.get(
                    f"{self._settings.misp_url}/servers/getVersion",
                    headers={"Authorization": self._settings.misp_api_key},
                )
                resp.raise_for_status()
                return {"connected": True, "version": resp.json().get("version")}
        except Exception as e:
            return {"connected": False, "reason": str(e)}
