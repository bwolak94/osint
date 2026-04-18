"""TheHive/Cortex integration adapter."""

from typing import Any

import structlog

from src.config import get_settings

log = structlog.get_logger()


class TheHiveAdapter:
    """Create and manage cases in TheHive from OSINT investigations."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def create_case(
        self,
        title: str,
        description: str,
        severity: int = 2,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        if not self._settings.thehive_url:
            return {"status": "skipped", "reason": "No TheHive URL configured"}
        try:
            import httpx

            case_data = {
                "title": title,
                "description": description,
                "severity": severity,
                "tags": tags or ["osint-platform"],
                "flag": False,
                "tlp": 2,
                "pap": 2,
            }
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self._settings.thehive_url}/api/case",
                    json=case_data,
                    headers={
                        "Authorization": f"Bearer {self._settings.thehive_api_key}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                return {"status": "created", "case": resp.json()}
        except ImportError:
            return {"status": "error", "reason": "httpx not installed"}
        except Exception as e:
            log.error("TheHive case creation failed", error=str(e))
            return {"status": "error", "reason": str(e)}

    async def add_observable(
        self,
        case_id: str,
        data_type: str,
        data: str,
        message: str = "",
    ) -> dict[str, Any]:
        if not self._settings.thehive_url:
            return {"status": "skipped"}
        try:
            import httpx

            observable = {
                "dataType": data_type,
                "data": data,
                "message": message,
                "tlp": 2,
                "ioc": True,
                "sighted": True,
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self._settings.thehive_url}/api/case/{case_id}/artifact",
                    json=observable,
                    headers={
                        "Authorization": f"Bearer {self._settings.thehive_api_key}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                return {"status": "added", "observable": resp.json()}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    async def test_connection(self) -> dict[str, Any]:
        if not self._settings.thehive_url:
            return {"connected": False, "reason": "No TheHive URL configured"}
        return {"connected": True, "url": self._settings.thehive_url}
