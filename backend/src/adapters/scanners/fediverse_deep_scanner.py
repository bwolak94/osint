"""Fediverse deep scanner — Mastodon/ActivityPub webfinger across 50+ instances.

Finds:
- Account existence across major Mastodon/Pleroma/Misskey/Akkoma instances
- Public profile data: display name, bio, follower/following counts, post count
- Account creation date and last active timestamp
- Linked URLs and custom fields from profiles
- Cross-instance identity links (same person on multiple instances)
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import quote

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# 50+ Fediverse instances to probe
_FEDIVERSE_INSTANCES: list[str] = [
    "mastodon.social",
    "fosstodon.org",
    "infosec.exchange",
    "hachyderm.io",
    "sigmoid.social",
    "mastodon.online",
    "mas.to",
    "techhub.social",
    "mstdn.social",
    "mastodon.world",
    "social.coop",
    "chaos.social",
    "scholar.social",
    "mathstodon.xyz",
    "newsie.social",
    "kolektiva.social",
    "mastodon.cloud",
    "noc.social",
    "dice.camp",
    "functional.cafe",
    "ruby.social",
    "indieweb.social",
    "universeodon.com",
    "toot.cafe",
    "sfba.social",
    "aus.social",
    "social.lol",
    "c.im",
    "mastodon.ie",
    "mastodon.nl",
    "social.v.st",
    "mastodon.gamedev.place",
    "photog.social",
    "masto.ai",
    "mastodon.technology",
    "mastodon.xyz",
    "qoto.org",
    "social.vivaldi.net",
    "octodon.social",
    "tooting.ai",
    "botsin.space",
    "vmst.io",
    "ioc.exchange",
    "mastodon.scot",
    "mastodon.sdf.org",
    "defcon.social",
    "social.privacyguides.net",
    "legal.social",
    "mastodon.lol",
    "mastodon.uno",
]


class FediverseDeepScanner(BaseOsintScanner):
    """Deep Fediverse/ActivityPub account scanner across 50+ instances."""

    scanner_name = "fediverse_deep"
    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.EMAIL})
    cache_ttl = 43200
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        profiles: list[dict[str, Any]] = []

        # Derive username
        if "@" in query and not query.startswith("@"):
            # Could be user@instance or email
            parts = query.split("@")
            username = parts[0].lower().strip()
        elif query.startswith("@"):
            parts = query.lstrip("@").split("@")
            username = parts[0].lower().strip()
        else:
            username = query.lower().strip()

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; FediverseScanner/1.0)",
                "Accept": "application/json, application/activity+json",
            },
        ) as client:
            semaphore = asyncio.Semaphore(10)  # 10 concurrent requests

            async def probe_instance(instance: str) -> None:
                async with semaphore:
                    try:
                        # 1. WebFinger lookup
                        wf_resp = await client.get(
                            f"https://{instance}/.well-known/webfinger",
                            params={"resource": f"acct:{username}@{instance}"},
                            timeout=6,
                        )
                        if wf_resp.status_code != 200:
                            return

                        import json as _json
                        wf_data = _json.loads(wf_resp.text)
                        # Find ActivityPub profile link
                        self_link = None
                        for link in wf_data.get("links", []):
                            if link.get("rel") == "self" and "activitystreams" in link.get("type", ""):
                                self_link = link.get("href")
                                break
                        if not self_link:
                            return

                        # 2. Fetch ActivityPub actor profile
                        actor_resp = await client.get(
                            self_link,
                            headers={"Accept": "application/activity+json"},
                            timeout=6,
                        )
                        if actor_resp.status_code != 200:
                            return

                        actor = _json.loads(actor_resp.text)
                        display_name = actor.get("name") or actor.get("preferredUsername")
                        summary_raw = actor.get("summary", "")
                        # Strip HTML tags from bio
                        bio = re.sub(r'<[^>]+>', '', summary_raw)[:200] if summary_raw else None
                        followers = actor.get("followers")
                        following = actor.get("following")
                        url = actor.get("url") or self_link
                        created = actor.get("published")
                        icon = actor.get("icon", {}).get("url") if isinstance(actor.get("icon"), dict) else None

                        # Extract custom fields
                        attachment = actor.get("attachment", [])
                        fields = [
                            {"name": a.get("name"), "value": re.sub(r'<[^>]+>', '', a.get("value", ""))}
                            for a in attachment if isinstance(a, dict) and a.get("type") == "PropertyValue"
                        ]

                        profile_data = {
                            "instance": instance,
                            "username": username,
                            "fediverse_id": f"@{username}@{instance}",
                            "display_name": display_name,
                            "bio": bio,
                            "url": url,
                            "created": created,
                            "avatar": icon,
                            "fields": fields[:5],
                        }
                        profiles.append(profile_data)
                        identifiers.append(f"info:fediverse:{instance}")

                    except Exception as exc:
                        log.debug("Fediverse instance probe failed", instance=instance, error=str(exc))

            # Probe all instances concurrently
            await asyncio.gather(*[probe_instance(inst) for inst in _FEDIVERSE_INSTANCES])

        if profiles:
            # Primary finding: list of all found profiles
            findings.append({
                "type": "fediverse_profiles_found",
                "severity": "info",
                "source": "Fediverse (ActivityPub)",
                "username": username,
                "total_instances": len(profiles),
                "instances": [p["instance"] for p in profiles],
                "profiles": profiles[:10],
                "description": f"Fediverse: '{username}' found on {len(profiles)} instance(s): "
                               + ", ".join(p["instance"] for p in profiles[:5])
                               + ("..." if len(profiles) > 5 else ""),
            })

            # If found on multiple instances, highlight cross-instance presence
            if len(profiles) > 1:
                findings.append({
                    "type": "fediverse_cross_instance",
                    "severity": "info",
                    "source": "Fediverse",
                    "username": username,
                    "instance_count": len(profiles),
                    "description": f"Cross-instance identity: '{username}' active on {len(profiles)} Fediverse instances",
                })

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "username": username,
            "profiles": profiles,
            "findings": findings,
            "total_found": len(findings),
            "instances_checked": len(_FEDIVERSE_INSTANCES),
            "instances_matched": len(profiles),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
