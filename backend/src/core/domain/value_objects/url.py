"""URL value object with social media detection."""

import re
from dataclasses import dataclass
from urllib.parse import urlparse

# Pattern requiring http or https scheme followed by a valid domain
_URL_REGEX = re.compile(
    r"^https?://[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*"
    r"\.[a-zA-Z]{2,}(/.*)?$"
)

_SOCIAL_MEDIA_DOMAINS: dict[str, str] = {
    "twitter.com": "twitter",
    "x.com": "twitter",
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "linkedin.com": "linkedin",
    "github.com": "github",
    "reddit.com": "reddit",
    "tiktok.com": "tiktok",
    "youtube.com": "youtube",
    "vk.com": "vk",
}


@dataclass(frozen=True)
class URL:
    """Immutable, self-validating URL value object."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        object.__setattr__(self, "value", normalized)
        if not _URL_REGEX.match(self.value):
            raise ValueError(f"Invalid URL: {self.value!r}")

    def domain(self) -> str:
        """Extract the domain (hostname) from the URL."""
        parsed = urlparse(self.value)
        return parsed.hostname or ""

    def is_social_media(self) -> bool:
        """Check whether the URL belongs to a known social media platform."""
        host = self.domain().lower()
        # Strip leading 'www.' for matching
        if host.startswith("www."):
            host = host[4:]
        return host in _SOCIAL_MEDIA_DOMAINS

    def platform(self) -> str | None:
        """Return the platform name if this is a social media URL, None otherwise."""
        host = self.domain().lower()
        if host.startswith("www."):
            host = host[4:]
        return _SOCIAL_MEDIA_DOMAINS.get(host)

    def __str__(self) -> str:
        return self.value
