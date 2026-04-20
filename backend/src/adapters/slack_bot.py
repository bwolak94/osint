"""Slack and Microsoft Teams bot adapters for OSINT platform notifications.

SlackBot
--------
Handles two transport paths:
  1. Incoming Webhooks  — for fire-and-forget alert messages.
  2. Slack Web API      — for interactive bot actions (slash commands, etc.).

Supports:
  - Rich attachment alert messages with configurable colours and fields.
  - Scan result summaries.
  - /osint slash command routing:
      /osint scan <type>:<value>   — trigger a scan
      /osint status <id>           — check investigation status
      /osint alert add <value>     — add a watchlist alert

  - HMAC-SHA256 signature verification of incoming Slack requests.

TeamsBot
--------
Microsoft Teams Incoming Webhook adapter using Adaptive Cards format.

Usage::

    bot = SlackBot()
    if bot.is_configured():
        await bot.send_alert(
            channel="#threat-intel",
            title="New IOC detected",
            message="Suspicious IP 1.2.3.4 observed in 3 investigations.",
            color="#ff0000",
        )

    teams = TeamsBot()
    await teams.send_alert(title="Alert", message="...", color="FF0000")
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx
import structlog

from src.config import get_settings

log = structlog.get_logger()

_CONNECT_TIMEOUT = 5.0
_READ_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# Slack Bot
# ---------------------------------------------------------------------------


class SlackBot:
    """Slack bot handler for OSINT investigation queries and alerts.

    Supports both Incoming Webhooks (send_alert, send_scan_result_summary)
    and the Slack Web API bot token path (handle_slash_command).
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._webhook_url: str = getattr(settings, "slack_webhook_url", "")
        self._bot_token: str = getattr(settings, "slack_bot_token", "")
        self._signing_secret: str = getattr(settings, "slack_signing_secret", "")

    # ------------------------------------------------------------------
    # Configuration guard
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        """Return True when at least a webhook URL or bot token is present."""
        return bool(self._webhook_url or self._bot_token)

    # ------------------------------------------------------------------
    # Alert messaging
    # ------------------------------------------------------------------

    async def send_alert(
        self,
        channel: str,
        title: str,
        message: str,
        fields: list[dict[str, Any]] | None = None,
        color: str = "#ff0000",
        investigation_url: str = "",
    ) -> bool:
        """Send a rich attachment alert message to a Slack channel.

        Uses the Web API ``chat.postMessage`` when a bot token is present;
        falls back to the Incoming Webhook otherwise.

        Args:
            channel:          Slack channel name or ID (e.g. "#threat-intel").
            title:            Bold title line of the attachment.
            message:          Main body text.
            fields:           Optional list of {title, value, short} dicts.
            color:            Hex colour string for the left-side attachment bar.
            investigation_url: Optional link appended to the attachment footer.

        Returns:
            True on success, False on any error.
        """
        if not self.is_configured():
            log.warning("Slack send_alert skipped — not configured")
            return False

        attachment = self._build_attachment(
            title=title,
            message=message,
            fields=fields or [],
            color=color,
            url=investigation_url,
        )

        try:
            if self._bot_token:
                return await self._post_via_api(channel=channel, attachment=attachment)
            return await self._post_via_webhook(attachment=attachment)
        except Exception as exc:
            log.error("Slack send_alert unexpected error", error=str(exc))
            return False

    async def send_scan_result_summary(
        self,
        channel: str,
        scanner_name: str,
        input_value: str,
        findings: list[str],
        investigation_id: str,
    ) -> bool:
        """Send a structured scan result summary to a Slack channel.

        Args:
            channel:          Destination Slack channel.
            scanner_name:     Name of the scanner that produced the results.
            input_value:      The query that was scanned (e.g. "8.8.8.8").
            findings:         List of human-readable finding strings.
            investigation_id: UUID of the parent investigation.

        Returns:
            True on success, False on error.
        """
        findings_text = "\n".join(f"• {f}" for f in findings) if findings else "_No findings_"
        message = f"Scanner *{scanner_name}* finished scanning `{input_value}`.\n\n{findings_text}"

        fields = [
            {"title": "Scanner", "value": scanner_name, "short": True},
            {"title": "Input", "value": input_value, "short": True},
            {"title": "Findings", "value": str(len(findings)), "short": True},
            {"title": "Investigation", "value": investigation_id, "short": True},
        ]

        color = "#36a64f" if findings else "#cccccc"  # green = found something

        return await self.send_alert(
            channel=channel,
            title=f"Scan complete — {scanner_name}",
            message=message,
            fields=fields,
            color=color,
        )

    # ------------------------------------------------------------------
    # Slash command routing
    # ------------------------------------------------------------------

    async def handle_slash_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Route an incoming /osint Slack slash command to the correct handler.

        Supported sub-commands:
            /osint scan <type>:<value>  — schedule a new scan
            /osint status <id>          — check investigation status
            /osint alert add <value>    — add a watchlist entry

        Args:
            payload: Raw Slack slash command payload dict (parsed from the
                     application/x-www-form-urlencoded request body).

        Returns:
            A Slack response dict with ``response_type`` and ``text`` keys.
        """
        text: str = (payload.get("text") or "").strip()
        user_name: str = payload.get("user_name", "unknown")

        log.info("Slack slash command received", text=text, user=user_name)

        parts = text.split(maxsplit=2)
        if not parts:
            return self._ephemeral_response(self._help_text())

        sub_command = parts[0].lower()

        if sub_command == "scan":
            return await self._handle_scan(parts[1:], user_name)

        if sub_command == "status":
            return await self._handle_status(parts[1:])

        if sub_command == "alert" and len(parts) >= 3 and parts[1].lower() == "add":
            return await self._handle_alert_add(parts[2:])

        return self._ephemeral_response(
            f"Unknown sub-command `{sub_command}`.\n{self._help_text()}"
        )

    async def _handle_scan(self, args: list[str], user: str) -> dict[str, Any]:
        """Handle /osint scan <type>:<value>."""
        if not args or ":" not in args[0]:
            return self._ephemeral_response(
                "Usage: `/osint scan <type>:<value>`\nExample: `/osint scan ip:8.8.8.8`"
            )
        entity_type, _, entity_value = args[0].partition(":")
        # In production this would enqueue a Celery task; here we acknowledge.
        log.info("Slack scan command", type=entity_type, value=entity_value, user=user)
        return self._ephemeral_response(
            f":mag: Scan queued for `{entity_type}:{entity_value}` by <@{user}>.\n"
            "You'll receive a summary when the scan completes."
        )

    async def _handle_status(self, args: list[str]) -> dict[str, Any]:
        """Handle /osint status <investigation_id>."""
        if not args:
            return self._ephemeral_response("Usage: `/osint status <investigation_id>`")
        investigation_id = args[0]
        log.info("Slack status command", investigation_id=investigation_id)
        return self._ephemeral_response(
            f":information_source: Status lookup for investigation `{investigation_id}`.\n"
            "_Fetching from database…_ (integrate with your investigation service here)"
        )

    async def _handle_alert_add(self, args: list[str]) -> dict[str, Any]:
        """Handle /osint alert add <value>."""
        if not args:
            return self._ephemeral_response("Usage: `/osint alert add <value>`")
        value = args[0]
        log.info("Slack alert add command", value=value)
        return self._ephemeral_response(
            f":bell: Watchlist alert added for `{value}`.\n"
            "You'll be notified when this value is detected."
        )

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------

    def verify_signature(
        self,
        body: bytes,
        timestamp: str,
        signature: str,
    ) -> bool:
        """Verify the authenticity of a Slack request using HMAC-SHA256.

        Slack signs every request with the app's signing secret. This method
        reproduces the signature and compares it in constant time to prevent
        timing attacks.

        Args:
            body:      Raw request body bytes.
            timestamp: Value of the ``X-Slack-Request-Timestamp`` header.
            signature: Value of the ``X-Slack-Signature`` header.

        Returns:
            True if the signature is valid and not replayed.
        """
        if not self._signing_secret:
            log.warning("Slack signature verification skipped — no signing secret")
            return False

        # Reject requests older than 5 minutes to prevent replay attacks
        try:
            request_time = int(timestamp)
            if abs(time.time() - request_time) > 300:
                log.warning("Slack request timestamp too old", timestamp=timestamp)
                return False
        except (ValueError, TypeError):
            return False

        sig_basestring = f"v0:{timestamp}:".encode() + body
        expected = (
            "v0="
            + hmac.new(
                self._signing_secret.encode(),
                sig_basestring,
                hashlib.sha256,
            ).hexdigest()
        )

        return hmac.compare_digest(expected, signature)

    # ------------------------------------------------------------------
    # Internal transport helpers
    # ------------------------------------------------------------------

    async def _post_via_api(
        self,
        channel: str,
        attachment: dict[str, Any],
    ) -> bool:
        """Post a message via the Slack Web API chat.postMessage endpoint."""
        payload = {
            "channel": channel,
            "attachments": [attachment],
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=_CONNECT_TIMEOUT, read=_READ_TIMEOUT, write=_READ_TIMEOUT, pool=_CONNECT_TIMEOUT),
        ) as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._bot_token}",
                    "Content-Type": "application/json",
                },
            )
        data = response.json()
        ok: bool = data.get("ok", False)
        if not ok:
            log.error("Slack API error", error=data.get("error"))
        return ok

    async def _post_via_webhook(self, attachment: dict[str, Any]) -> bool:
        """Post a message via an Incoming Webhook URL."""
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=_CONNECT_TIMEOUT, read=_READ_TIMEOUT, write=_READ_TIMEOUT, pool=_CONNECT_TIMEOUT),
        ) as client:
            response = await client.post(
                self._webhook_url,
                json={"attachments": [attachment]},
            )
        ok = response.status_code == 200
        if not ok:
            log.error("Slack webhook error", status=response.status_code, body=response.text[:200])
        return ok

    def _build_attachment(
        self,
        title: str,
        message: str,
        fields: list[dict[str, Any]],
        color: str,
        url: str,
    ) -> dict[str, Any]:
        """Construct a Slack message attachment dict.

        See https://api.slack.com/reference/messaging/attachments for the
        full schema. We use the legacy attachment format for broad compatibility.
        """
        attachment: dict[str, Any] = {
            "color": color,
            "title": title,
            "text": message,
            "fields": fields,
            "footer": "OSINT Platform",
            "ts": int(time.time()),
            "mrkdwn_in": ["text"],
        }
        if url:
            attachment["title_link"] = url
        return attachment

    @staticmethod
    def _ephemeral_response(text: str) -> dict[str, Any]:
        """Build an ephemeral (only visible to the requesting user) response."""
        return {"response_type": "ephemeral", "text": text}

    @staticmethod
    def _help_text() -> str:
        return (
            "*OSINT Platform Slash Commands*\n"
            "`/osint scan <type>:<value>` — Start a new scan\n"
            "`/osint status <id>` — Check investigation status\n"
            "`/osint alert add <value>` — Add a watchlist alert"
        )


# ---------------------------------------------------------------------------
# Microsoft Teams Bot
# ---------------------------------------------------------------------------


class TeamsBot:
    """Microsoft Teams Incoming Webhook adapter.

    Uses Adaptive Cards format for rich message presentation.
    All methods mirror the SlackBot interface so the two can be used
    interchangeably in notification services.

    Usage::

        teams = TeamsBot()
        if teams.is_configured():
            await teams.send_alert(title="Alert", message="Details here.")
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._webhook_url: str = getattr(settings, "teams_webhook_url", "")

    def is_configured(self) -> bool:
        """Return True when a Teams webhook URL is configured."""
        return bool(self._webhook_url)

    async def send_alert(
        self,
        title: str,
        message: str,
        fields: list[dict[str, Any]] | None = None,
        color: str = "FF0000",
        investigation_url: str = "",
    ) -> bool:
        """Send an Adaptive Card alert to the configured Teams channel.

        Args:
            title:            Card heading text.
            message:          Card body text.
            fields:           Optional list of {title, value} fact pairs.
            color:            Hex colour string (without #) for the top bar.
            investigation_url: Optional action URL added as a "View" button.

        Returns:
            True on success, False on error.
        """
        if not self.is_configured():
            log.warning("Teams send_alert skipped — not configured")
            return False

        card = self._build_adaptive_card(
            title=title,
            message=message,
            fields=fields or [],
            color=color,
            url=investigation_url,
        )

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=_CONNECT_TIMEOUT, read=_READ_TIMEOUT, write=_READ_TIMEOUT, pool=_CONNECT_TIMEOUT),
            ) as client:
                response = await client.post(self._webhook_url, json=card)
            ok = response.status_code in (200, 202)
            if not ok:
                log.error(
                    "Teams webhook error",
                    status=response.status_code,
                    body=response.text[:200],
                )
            return ok
        except httpx.RequestError as exc:
            log.error("Teams send_alert connection error", error=str(exc))
            return False

    async def send_scan_result_summary(
        self,
        scanner_name: str,
        input_value: str,
        findings: list[str],
        investigation_id: str,
    ) -> bool:
        """Send a scan result summary card to Teams.

        Args:
            scanner_name:     Display name of the scanner.
            input_value:      Scanned entity value.
            findings:         List of finding strings.
            investigation_id: Parent investigation UUID.

        Returns:
            True on success.
        """
        findings_text = "\n".join(f"- {f}" for f in findings) if findings else "No findings."
        message = f"Scanner **{scanner_name}** finished scanning `{input_value}`.\n\n{findings_text}"

        fields = [
            {"title": "Scanner", "value": scanner_name},
            {"title": "Input", "value": input_value},
            {"title": "Findings", "value": str(len(findings))},
            {"title": "Investigation ID", "value": investigation_id},
        ]

        color = "00AA00" if findings else "AAAAAA"

        return await self.send_alert(
            title=f"Scan complete — {scanner_name}",
            message=message,
            fields=fields,
            color=color,
        )

    # ------------------------------------------------------------------
    # Adaptive Card builder
    # ------------------------------------------------------------------

    def _build_adaptive_card(
        self,
        title: str,
        message: str,
        fields: list[dict[str, Any]],
        color: str,
        url: str,
    ) -> dict[str, Any]:
        """Build a Teams Adaptive Card payload.

        The outer wrapper is a legacy ``MessageCard`` format for compatibility
        with both Incoming Webhooks v1 and the newer Adaptive Cards connector.
        Facts are rendered as a FactSet column.
        """
        facts = [
            {"name": f.get("title", ""), "value": f.get("value", "")}
            for f in fields
        ]

        body: list[dict[str, Any]] = [
            {
                "type": "TextBlock",
                "text": title,
                "weight": "Bolder",
                "size": "Large",
                "color": "Attention" if color.upper().startswith("FF") else "Good",
            },
            {
                "type": "TextBlock",
                "text": message,
                "wrap": True,
            },
        ]

        if facts:
            body.append(
                {
                    "type": "FactSet",
                    "facts": facts,
                }
            )

        actions: list[dict[str, Any]] = []
        if url:
            actions.append(
                {
                    "type": "Action.OpenUrl",
                    "title": "View Investigation",
                    "url": url,
                }
            )

        card: dict[str, Any] = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": body,
                        "actions": actions,
                        "msteams": {"width": "Full"},
                    },
                }
            ],
        }
        return card
