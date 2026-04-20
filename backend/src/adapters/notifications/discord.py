"""Discord webhook notification adapter."""

import structlog
from typing import Any

log = structlog.get_logger()


class DiscordNotifier:
    """Sends notifications to a Discord channel via webhook URL."""

    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    async def send(self, title: str, message: str, fields: dict[str, Any] | None = None) -> bool:
        if not self._url:
            return False
        try:
            import httpx
            embed = {
                "title": title,
                "description": message,
                "color": 1046829,  # Brand teal
            }
            if fields:
                embed["fields"] = [{"name": k, "value": str(v), "inline": True} for k, v in fields.items()]

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._url, json={"embeds": [embed]})
                return resp.status_code in (200, 204)
        except Exception as e:
            log.warning("Discord notification failed", error=str(e))
            return False
