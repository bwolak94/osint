"""Trigger-based alert tasks — evaluate user-defined alert rules and send notifications.

These tasks are dispatched by the scanner pipeline after each new entity is
discovered.  They evaluate trigger rules stored in the database against the
incoming event and fan out to the appropriate notification channel
(Slack, Discord, webhook, email) for matching rules.

Tasks are intentionally stateless: all rule state lives in the DB and all
notification credentials are loaded from settings at runtime.
"""

import asyncio
import structlog
from celery import shared_task

log = structlog.get_logger()


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(
    bind=True,
    name="src.workers.tasks.alert_tasks.evaluate_trigger_rules",
    queue="light",
    rate_limit="120/m",
)
def evaluate_trigger_rules(
    self,
    investigation_id: str,
    event_type: str,
    entity_value: str,
    entity_type: str,
    source_scanner: str,
) -> dict:
    """Evaluate all user-defined trigger rules for a newly discovered entity.

    Loads every active trigger rule scoped to the investigation's owner and
    evaluates each rule condition in order:

    1. ``entity_type`` must match the rule's target type (or rule targets "any").
    2. ``source_scanner`` must match the rule's scanner filter (if set).
    3. ``entity_value`` must match the rule's regex / exact-value filter (if set).

    For every rule that matches, a notification is sent via the rule's configured
    channel (``slack``, ``discord``, ``webhook``, or ``email``).  Each delivery
    attempt is logged for audit purposes.

    Args:
        investigation_id: Investigation where the entity was discovered.
        event_type: Semantic event label, e.g. ``"entity_discovered"``,
                    ``"scan_completed"``, ``"risk_threshold_exceeded"``.
        entity_value: The raw entity value, e.g. ``"evil.com"``.
        entity_type: Canonical entity type, e.g. ``"domain"``, ``"ip"``.
        source_scanner: Name of the scanner that produced the entity.

    Returns:
        dict with keys: investigation_id, entity, rules_evaluated,
        notifications_sent.
    """

    async def _run() -> dict:
        entity_label = f"{entity_type}:{entity_value}"

        log.info(
            "Evaluating trigger rules",
            investigation_id=investigation_id,
            event_type=event_type,
            entity=entity_label,
            source_scanner=source_scanner,
        )

        rules_evaluated = 0
        notifications_sent = 0

        try:
            # Load trigger rules from DB for this investigation's owner.
            # rules = await TriggerRuleRepository.get_active_for_investigation(
            #     investigation_id
            # )
            rules: list[dict] = []

            for rule in rules:
                rules_evaluated += 1
                if not _rule_matches(rule, entity_type, entity_value, source_scanner):
                    continue

                channel = rule.get("channel", "email")
                try:
                    await _dispatch_notification(
                        channel=channel,
                        rule=rule,
                        event_type=event_type,
                        entity_label=entity_label,
                        investigation_id=investigation_id,
                    )
                    notifications_sent += 1
                    log.info(
                        "Notification sent",
                        channel=channel,
                        rule_id=rule.get("id"),
                        entity=entity_label,
                    )
                except Exception as notify_exc:
                    log.error(
                        "Notification delivery failed",
                        channel=channel,
                        rule_id=rule.get("id"),
                        error=str(notify_exc),
                    )

        except Exception as exc:
            log.error(
                "evaluate_trigger_rules failed",
                investigation_id=investigation_id,
                error=str(exc),
            )
            # Do not retry rule evaluation — the event has already passed.

        return {
            "investigation_id": investigation_id,
            "entity": entity_label,
            "rules_evaluated": rules_evaluated,
            "notifications_sent": notifications_sent,
        }

    return _run_async(_run())


@shared_task(
    bind=True,
    name="src.workers.tasks.alert_tasks.send_daily_digest",
    queue="light",
)
def send_daily_digest(self, user_id: str) -> dict:
    """Send a daily digest notification summarising investigation activity.

    Aggregates activity from the past 24 hours for all investigations owned by
    ``user_id``:

    - New entities discovered.
    - Scans completed and their status breakdown.
    - Risk score changes (delta from previous digest).
    - Watchlist hits.

    The digest is delivered via the channel configured in the user's notification
    preferences (email and/or Slack).  If no preference is set the task returns
    with ``sent=False`` and ``reason="not_configured"``.

    Args:
        user_id: ID of the user to send the digest to.

    Returns:
        dict with keys: user_id, sent, reason.
    """

    async def _run() -> dict:
        log.info("Preparing daily digest", user_id=user_id)

        try:
            # Load notification preferences (stubbed).
            # prefs = await UserPreferencesRepository.get(user_id)
            prefs: dict | None = None

            if not prefs or not prefs.get("digest_enabled"):
                log.info("Daily digest not configured", user_id=user_id)
                return {"user_id": user_id, "sent": False, "reason": "not_configured"}

            # Aggregate last-24h activity (stubbed).
            # summary = await ActivityRepository.daily_summary(user_id)

            # Dispatch to notification channel.
            # await NotificationService.send_digest(prefs["channel"], summary)

            log.info("Daily digest sent", user_id=user_id)
            return {"user_id": user_id, "sent": True, "reason": "ok"}

        except Exception as exc:
            log.error("send_daily_digest failed", user_id=user_id, error=str(exc))
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))

    return _run_async(_run())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rule_matches(
    rule: dict,
    entity_type: str,
    entity_value: str,
    source_scanner: str,
) -> bool:
    """Return True if the rule's conditions are satisfied by this event.

    Conditions are evaluated in short-circuit order:
    1. entity_type filter (required)
    2. source_scanner filter (optional)
    3. value pattern filter (optional, regex)
    """
    import re

    rule_entity_type: str = rule.get("entity_type", "any")
    if rule_entity_type != "any" and rule_entity_type != entity_type:
        return False

    rule_scanner: str | None = rule.get("source_scanner")
    if rule_scanner and rule_scanner != source_scanner:
        return False

    rule_pattern: str | None = rule.get("value_pattern")
    if rule_pattern:
        try:
            if not re.search(rule_pattern, entity_value, re.IGNORECASE):
                return False
        except re.error:
            # Malformed regex stored in DB — skip this condition silently.
            pass

    return True


async def _dispatch_notification(
    channel: str,
    rule: dict,
    event_type: str,
    entity_label: str,
    investigation_id: str,
) -> None:
    """Send a single notification to the specified channel.

    Stubbed: replace each branch with a real adapter call
    (e.g. SlackNotifier, DiscordNotifier, WebhookNotifier, EmailNotifier).
    """
    payload = {
        "rule_name": rule.get("name", "Unnamed rule"),
        "event_type": event_type,
        "entity": entity_label,
        "investigation_id": investigation_id,
    }

    if channel == "slack":
        # await SlackNotifier(rule["webhook_url"]).send(payload)
        pass
    elif channel == "discord":
        # await DiscordNotifier(rule["webhook_url"]).send(payload)
        pass
    elif channel == "webhook":
        # await WebhookNotifier(rule["webhook_url"]).send(payload)
        pass
    elif channel == "email":
        # await EmailNotifier().send(rule["email_address"], payload)
        pass
    else:
        log.warning("Unknown notification channel", channel=channel, rule_id=rule.get("id"))
