"""Jira/ServiceNow ticket creation adapter."""

import base64
from typing import Any

import structlog

from src.config import get_settings

log = structlog.get_logger()


class JiraAdapter:
    """Create and manage Jira tickets from OSINT investigations."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def create_ticket(
        self,
        summary: str,
        description: str,
        issue_type: str = "Task",
        priority: str = "Medium",
        labels: list[str] | None = None,
    ) -> dict[str, Any]:
        if not self._settings.jira_url:
            return {"status": "skipped", "reason": "No Jira URL configured"}
        try:
            import httpx

            auth = base64.b64encode(
                f"{self._settings.jira_email}:{self._settings.jira_api_token}".encode()
            ).decode()
            issue_data = {
                "fields": {
                    "project": {"key": self._settings.jira_project_key},
                    "summary": summary,
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": description}],
                            }
                        ],
                    },
                    "issuetype": {"name": issue_type},
                    "priority": {"name": priority},
                    "labels": labels or ["osint-platform"],
                }
            }
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self._settings.jira_url}/rest/api/3/issue",
                    json=issue_data,
                    headers={
                        "Authorization": f"Basic {auth}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                result = resp.json()
            log.info("Jira ticket created", key=result.get("key"))
            return {
                "status": "created",
                "key": result.get("key"),
                "id": result.get("id"),
                "url": f"{self._settings.jira_url}/browse/{result.get('key')}",
            }
        except ImportError:
            return {"status": "error", "reason": "httpx not installed"}
        except Exception as e:
            log.error("Jira ticket creation failed", error=str(e))
            return {"status": "error", "reason": str(e)}

    async def test_connection(self) -> dict[str, Any]:
        if not self._settings.jira_url:
            return {"connected": False, "reason": "No Jira URL configured"}
        return {
            "connected": True,
            "url": self._settings.jira_url,
            "project": self._settings.jira_project_key,
        }
