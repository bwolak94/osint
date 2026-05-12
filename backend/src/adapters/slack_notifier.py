"""Slack webhook notification adapter. (#32)

Usage:
    notifier = SlackNotifier()
    await notifier.send_finding(finding_dict)
    await notifier.send_message("#channel", "text", blocks=[...])

Config via env:
    SLACK_WEBHOOK_URL    — incoming webhook URL
    SLACK_DEFAULT_CHANNEL — fallback channel (default: #pentest-alerts)
    SLACK_ENABLED        — "true" to enable (default: false)
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SLACK_ENABLED = os.getenv("SLACK_ENABLED", "false").lower() == "true"
SLACK_DEFAULT_CHANNEL = os.getenv("SLACK_DEFAULT_CHANNEL", "#pentest-alerts")

_SEVERITY_EMOJI = {
    "critical": ":red_circle:",
    "high": ":large_orange_circle:",
    "medium": ":large_yellow_circle:",
    "low": ":large_blue_circle:",
    "info": ":white_circle:",
}


class SlackNotifier:
    """Send structured messages to Slack via incoming webhook."""

    def __init__(self, webhook_url: str = SLACK_WEBHOOK_URL) -> None:
        self.webhook_url = webhook_url
        self.enabled = SLACK_ENABLED and bool(webhook_url)

    async def send_message(
        self,
        text: str,
        channel: str = SLACK_DEFAULT_CHANNEL,
        blocks: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Send a plain or block-kit message. Returns True on success."""
        if not self.enabled:
            await log.adebug("slack_disabled", text=text[:80])
            return False

        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks

        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.post(self.webhook_url, json=payload)
                resp.raise_for_status()
            await log.ainfo("slack_sent", channel=channel, text=text[:80])
            return True
        except Exception as exc:
            await log.awarning("slack_send_failed", error=str(exc))
            return False

    async def send_finding(self, finding: dict[str, Any], channel: str = SLACK_DEFAULT_CHANNEL) -> bool:
        """Send a rich finding alert with severity colour and detail."""
        severity = str(finding.get("severity", "info")).lower()
        emoji = _SEVERITY_EMOJI.get(severity, ":white_circle:")
        title = finding.get("title", "Untitled Finding")
        target = finding.get("target", "unknown")
        cve = finding.get("cve_id", "")

        blocks: list[dict[str, Any]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{severity.upper()} Finding:* {title}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Target:*\n{target}"},
                    {"type": "mrkdwn", "text": f"*CVE:*\n{cve or 'N/A'}"},
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity}"},
                    {"type": "mrkdwn", "text": f"*ID:*\n{finding.get('id', '—')}"},
                ],
            },
        ]

        if finding.get("description"):
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Description:*\n{str(finding['description'])[:300]}"},
            })

        blocks.append({"type": "divider"})

        fallback = f"{emoji} [{severity.upper()}] {title} on {target}"
        return await self.send_message(text=fallback, channel=channel, blocks=blocks)

    async def send_scenario_completion(
        self,
        objective: str,
        steps_total: int,
        steps_done: int,
        steps_errored: int,
        execution_id: str,
        channel: str = SLACK_DEFAULT_CHANNEL,
    ) -> bool:
        """Notify channel when a scenario run completes."""
        status = "✅ Completed" if steps_errored == 0 else "⚠️ Completed with errors"
        text = f"{status}: *{objective}* — {steps_done}/{steps_total} steps done, {steps_errored} errors. (exec: {execution_id})"
        return await self.send_message(text=text, channel=channel)


# Module-level singleton
_notifier: SlackNotifier | None = None


def get_slack_notifier() -> SlackNotifier:
    global _notifier
    if _notifier is None:
        _notifier = SlackNotifier()
    return _notifier
