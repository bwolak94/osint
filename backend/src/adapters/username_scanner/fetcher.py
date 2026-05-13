"""Cross-platform username scanner — checks existence across 30+ platforms."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
import httpx

# Platform definitions: (name, url_template, expected_status_on_found)
# url_template: use {username} placeholder
_PLATFORMS: list[tuple[str, str, int]] = [
    ("GitHub", "https://github.com/{username}", 200),
    ("GitLab", "https://gitlab.com/{username}", 200),
    ("Twitter/X", "https://twitter.com/{username}", 200),
    ("Instagram", "https://www.instagram.com/{username}/", 200),
    ("Reddit", "https://www.reddit.com/user/{username}", 200),
    ("Pinterest", "https://www.pinterest.com/{username}/", 200),
    ("Twitch", "https://www.twitch.tv/{username}", 200),
    ("YouTube", "https://www.youtube.com/@{username}", 200),
    ("TikTok", "https://www.tiktok.com/@{username}", 200),
    ("LinkedIn", "https://www.linkedin.com/in/{username}", 200),
    ("Keybase", "https://keybase.io/{username}", 200),
    ("HackerNews", "https://news.ycombinator.com/user?id={username}", 200),
    ("Dev.to", "https://dev.to/{username}", 200),
    ("Medium", "https://medium.com/@{username}", 200),
    ("Substack", "https://{username}.substack.com", 200),
    ("Mastodon", "https://mastodon.social/@{username}", 200),
    ("Bluesky", "https://bsky.app/profile/{username}.bsky.social", 200),
    ("Steam", "https://steamcommunity.com/id/{username}", 200),
    ("Behance", "https://www.behance.net/{username}", 200),
    ("Dribbble", "https://dribbble.com/{username}", 200),
    ("Fiverr", "https://www.fiverr.com/{username}", 200),
    ("Freelancer", "https://www.freelancer.com/u/{username}", 200),
    ("Vimeo", "https://vimeo.com/{username}", 200),
    ("Flickr", "https://www.flickr.com/people/{username}", 200),
    ("Soundcloud", "https://soundcloud.com/{username}", 200),
    ("Spotify", "https://open.spotify.com/user/{username}", 200),
    ("Patreon", "https://www.patreon.com/{username}", 200),
    ("Ko-fi", "https://ko-fi.com/{username}", 200),
    ("Docker Hub", "https://hub.docker.com/u/{username}", 200),
    ("npm", "https://www.npmjs.com/~{username}", 200),
    ("PyPI", "https://pypi.org/user/{username}/", 200),
    ("HuggingFace", "https://huggingface.co/{username}", 200),
]


@dataclass
class PlatformResult:
    platform: str
    url: str
    found: bool
    status_code: int | None = None
    error: str | None = None


@dataclass
class UsernameScanResult:
    username: str
    found: list[PlatformResult] = field(default_factory=list)
    not_found: list[PlatformResult] = field(default_factory=list)
    errors: list[PlatformResult] = field(default_factory=list)
    total_checked: int = 0
    source: str = "username_scanner"


async def scan_username(username: str) -> UsernameScanResult:
    username = username.strip().lstrip("@")
    result = UsernameScanResult(username=username)

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(
        timeout=10.0,
        follow_redirects=True,
        headers=headers,
        verify=False,
    ) as client:
        tasks = [_check_platform(client, name, url_t, expected, username) for name, url_t, expected in _PLATFORMS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, PlatformResult):
            result.total_checked += 1
            if r.error:
                result.errors.append(r)
            elif r.found:
                result.found.append(r)
            else:
                result.not_found.append(r)

    return result


async def _check_platform(
    client: httpx.AsyncClient,
    name: str,
    url_template: str,
    expected_status: int,
    username: str,
) -> PlatformResult:
    url = url_template.replace("{username}", username)
    try:
        r = await client.head(url)
        found = r.status_code == expected_status
        # Some sites return 405 for HEAD but have content on GET
        if r.status_code == 405:
            r2 = await client.get(url)
            found = r2.status_code == expected_status
            return PlatformResult(platform=name, url=url, found=found, status_code=r2.status_code)
        return PlatformResult(platform=name, url=url, found=found, status_code=r.status_code)
    except httpx.TimeoutException:
        return PlatformResult(platform=name, url=url, found=False, error="timeout")
    except Exception as e:
        return PlatformResult(platform=name, url=url, found=False, error=str(e)[:80])
