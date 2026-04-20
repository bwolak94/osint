"""Sherlock username scanner — check username presence across 50+ platforms."""

import asyncio
import subprocess
import sys
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

SITES: dict[str, str] = {
    "GitHub": "https://github.com/{username}",
    "Twitter": "https://twitter.com/{username}",
    "Reddit": "https://www.reddit.com/user/{username}",
    "Instagram": "https://www.instagram.com/{username}/",
    "TikTok": "https://www.tiktok.com/@{username}",
    "YouTube": "https://www.youtube.com/@{username}",
    "LinkedIn": "https://www.linkedin.com/in/{username}",
    "Pinterest": "https://www.pinterest.com/{username}/",
    "Tumblr": "https://{username}.tumblr.com/",
    "Medium": "https://medium.com/@{username}",
    "Dev.to": "https://dev.to/{username}",
    "HackerNews": "https://news.ycombinator.com/user?id={username}",
    "GitLab": "https://gitlab.com/{username}",
    "Bitbucket": "https://bitbucket.org/{username}/",
    "Steam": "https://steamcommunity.com/id/{username}",
    "Twitch": "https://www.twitch.tv/{username}",
    "Pastebin": "https://pastebin.com/u/{username}",
    "Keybase": "https://keybase.io/{username}",
    "Gravatar": "https://en.gravatar.com/{username}",
    "Flickr": "https://www.flickr.com/people/{username}/",
    "Vimeo": "https://vimeo.com/{username}",
    "SoundCloud": "https://soundcloud.com/{username}",
    "Spotify": "https://open.spotify.com/user/{username}",
    "Codecademy": "https://www.codecademy.com/profiles/{username}",
    "HackerRank": "https://www.hackerrank.com/{username}",
    "LeetCode": "https://leetcode.com/{username}/",
    "Kaggle": "https://www.kaggle.com/{username}",
    "DockerHub": "https://hub.docker.com/u/{username}/",
    "npm": "https://www.npmjs.com/~{username}",
    "PyPI": "https://pypi.org/user/{username}/",
    "Replit": "https://replit.com/@{username}",
    "Codepen": "https://codepen.io/{username}",
    "Behance": "https://www.behance.net/{username}",
    "Dribbble": "https://dribbble.com/{username}",
    "ProductHunt": "https://www.producthunt.com/@{username}",
    "AngelList": "https://angel.co/{username}",
    "Mastodon": "https://mastodon.social/@{username}",
    "Telegram": "https://t.me/{username}",
    "WhatsApp": "https://wa.me/{username}",
    "Snapchat": "https://www.snapchat.com/add/{username}",
    "Discord": "https://discord.com/users/{username}",
    "StackOverflow": "https://stackoverflow.com/users/{username}",
    "Quora": "https://www.quora.com/profile/{username}",
    "Goodreads": "https://www.goodreads.com/{username}",
    "Last.fm": "https://www.last.fm/user/{username}",
    "Chess.com": "https://www.chess.com/member/{username}",
    "Duolingo": "https://www.duolingo.com/profile/{username}",
    "Strava": "https://www.strava.com/athletes/{username}",
    "About.me": "https://about.me/{username}",
}


class SherlockScanner(BaseOsintScanner):
    scanner_name = "sherlock"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = input_value.strip()

        # Attempt to run sherlock as a subprocess first
        try:
            result = await self._run_sherlock_subprocess(username)
            if result is not None:
                return result
        except Exception as exc:
            log.debug("Sherlock subprocess unavailable, falling back to direct checks", error=str(exc))

        # Fallback: direct concurrent HTTP checks
        return await self._direct_check(username)

    async def _run_sherlock_subprocess(self, username: str) -> dict[str, Any] | None:
        """Attempt to run the sherlock CLI tool as a subprocess."""
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "sherlock",
            username,
            "--timeout",
            "10",
            "--print-found",
            "--no-color",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            return None

        output = stdout.decode(errors="replace")
        found_on: list[str] = []
        profile_urls: list[str] = []

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("[+]"):
                parts = line.split(": ", 1)
                if len(parts) == 2:
                    site = parts[0].replace("[+]", "").strip()
                    url = parts[1].strip()
                    found_on.append(site)
                    profile_urls.append(url)

        identifiers = [f"url:{u}" for u in profile_urls]
        return {
            "username": username,
            "source": "sherlock_subprocess",
            "found_on": found_on,
            "profile_urls": profile_urls,
            "total_checked": len(SITES),
            "total_found": len(found_on),
            "extracted_identifiers": identifiers,
        }

    async def _direct_check(self, username: str) -> dict[str, Any]:
        """Check each site in SITES concurrently via HTTP status codes."""
        semaphore = asyncio.Semaphore(20)
        found_on: list[str] = []
        profile_urls: list[str] = []

        async def check_site(site_name: str, url_template: str) -> None:
            url = url_template.format(username=username)
            async with semaphore:
                try:
                    async with httpx.AsyncClient(
                        timeout=10,
                        follow_redirects=True,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"},
                    ) as client:
                        resp = await client.head(url)
                        if resp.status_code == 200:
                            found_on.append(site_name)
                            profile_urls.append(url)
                except Exception:
                    pass

        await asyncio.gather(*[check_site(name, tmpl) for name, tmpl in SITES.items()])

        identifiers = [f"url:{u}" for u in profile_urls]
        return {
            "username": username,
            "source": "direct_http",
            "found_on": found_on,
            "profile_urls": profile_urls,
            "total_checked": len(SITES),
            "total_found": len(found_on),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
