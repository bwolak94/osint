"""Slack webhook notification adapter."""

import structlog
from typing import Any

log = structlog.get_logger()


class SlackNotifier:
    """Sends notifications to a Slack channel via webhook URL."""

    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    async def send(self, title: str, message: str, fields: dict[str, Any] | None = None) -> bool:
        if not self._url:
            return False
        try:
            import httpx
            blocks = [
                {"type": "header", "text": {"type": "plain_text", "text": title}},
                {"type": "section", "text": {"type": "mrkdwn", "text": message}},
            ]
            if fields:
                field_blocks = [{"type": "mrkdwn", "text": f"*{k}:* {v}"} for k, v in fields.items()]
                blocks.append({"type": "section", "fields": field_blocks})

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._url, json={"blocks": blocks})
                return resp.status_code == 200
        except Exception as e:
            log.warning("Slack notification failed", error=str(e))
            return False
