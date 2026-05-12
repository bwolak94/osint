"""Probe template data model — the core type system for VulnProbeScanner.

Templates describe what to check, how to match a finding, and what to extract.
All types are frozen dataclasses for hashability and immutability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class MatcherType(str, Enum):
    STATUS = "status"    # HTTP status code in a set
    WORD = "word"        # substring in body / header value
    REGEX = "regex"      # regex match in body / header value
    HEADER = "header"   # header present / header value word
    SIZE = "size"        # response body size comparison


class ExtractorType(str, Enum):
    REGEX = "regex"      # named-group regex over body
    HEADER = "header"    # value of a named response header
    WORD = "word"        # return the matched word (for inventory)


class MatcherPart(str, Enum):
    BODY = "body"
    HEADER = "header"    # match against all header values joined
    STATUS = "status"
    URL = "url"          # final (post-redirect) URL


class MatcherCondition(str, Enum):
    OR = "or"    # any value matches → positive
    AND = "and"  # all values must match → positive


# ── Matchers ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StatusMatcher:
    """Passes when the HTTP status code is in `codes`."""
    codes: tuple[int, ...]
    negative: bool = False

    def match(self, *, status: int, body: str, headers: dict[str, str], url: str) -> bool:
        result = status in self.codes
        return (not result) if self.negative else result


@dataclass(frozen=True)
class WordMatcher:
    """Passes when any/all words appear in `part`."""
    words: tuple[str, ...]
    part: MatcherPart = MatcherPart.BODY
    condition: MatcherCondition = MatcherCondition.OR
    case_insensitive: bool = True
    negative: bool = False

    def match(self, *, status: int, body: str, headers: dict[str, str], url: str) -> bool:
        text = self._get_part(body, headers, url)
        if self.case_insensitive:
            text = text.lower()
            words = [w.lower() for w in self.words]
        else:
            words = list(self.words)

        if self.condition == MatcherCondition.OR:
            result = any(w in text for w in words)
        else:
            result = all(w in text for w in words)

        return (not result) if self.negative else result

    def _get_part(self, body: str, headers: dict[str, str], url: str) -> str:
        if self.part == MatcherPart.HEADER:
            return " ".join(headers.values())
        if self.part == MatcherPart.URL:
            return url
        return body


@dataclass(frozen=True)
class RegexMatcher:
    """Passes when the regex matches in `part`."""
    pattern: str
    part: MatcherPart = MatcherPart.BODY
    negative: bool = False

    def match(self, *, status: int, body: str, headers: dict[str, str], url: str) -> bool:
        import re
        text = self._get_part(body, headers, url)
        result = bool(re.search(self.pattern, text, re.IGNORECASE | re.DOTALL))
        return (not result) if self.negative else result

    def _get_part(self, body: str, headers: dict[str, str], url: str) -> str:
        if self.part == MatcherPart.HEADER:
            return " ".join(headers.values())
        if self.part == MatcherPart.URL:
            return url
        return body


@dataclass(frozen=True)
class HeaderMatcher:
    """Passes when the named header is present (and optionally contains a word)."""
    header_name: str
    contains: str | None = None
    present: bool = True  # False → assert header is ABSENT
    negative: bool = False

    def match(self, *, status: int, body: str, headers: dict[str, str], url: str) -> bool:
        norm = {k.lower(): v for k, v in headers.items()}
        key = self.header_name.lower()
        header_present = key in norm
        if not self.present:
            # We expect the header to be absent
            result = not header_present
        elif self.contains:
            result = header_present and self.contains.lower() in norm.get(key, "").lower()
        else:
            result = header_present
        return (not result) if self.negative else result


# Union type for all matchers
Matcher = StatusMatcher | WordMatcher | RegexMatcher | HeaderMatcher


# ── Extractors ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RegexExtractor:
    """Extract a named group from the response body using a regex."""
    name: str
    pattern: str
    part: MatcherPart = MatcherPart.BODY

    def extract(self, *, body: str, headers: dict[str, str], url: str) -> str | None:
        import re
        text = body if self.part == MatcherPart.BODY else " ".join(headers.values())
        m = re.search(self.pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                return m.group("value") or m.group(1)
            except IndexError:
                return m.group(0)
        return None


@dataclass(frozen=True)
class HeaderExtractor:
    """Return the value of the named response header."""
    name: str
    header_name: str

    def extract(self, *, body: str, headers: dict[str, str], url: str) -> str | None:
        norm = {k.lower(): v for k, v in headers.items()}
        return norm.get(self.header_name.lower())


Extractor = RegexExtractor | HeaderExtractor


# ── Probe request ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProbeRequest:
    """A single HTTP request definition within a template."""
    method: str = "GET"
    path: str = "/"                       # appended to the target base URL
    headers: tuple[tuple[str, str], ...] = ()  # extra request headers
    body: str | None = None
    follow_redirects: bool = True
    # Matchers applied to this request's response (AND across matchers)
    matchers: tuple[Matcher, ...] = ()
    # Condition between matchers within this request
    matcher_condition: MatcherCondition = MatcherCondition.AND
    # Extractors: run only when matched
    extractors: tuple[Extractor, ...] = ()


# ── Template ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProbeTemplate:
    """A self-contained probe definition, analogous to a Nuclei template
    but expressed in typed Python instead of YAML.

    Each template is uniquely identified by `id` and describes:
    - What to probe  (requests)
    - What constitutes a finding (matchers inside each request)
    - How to extract evidence (extractors)
    - Metadata for reporting (severity, tags, remediation, references)
    """

    id: str
    name: str
    description: str
    severity: Severity
    category: str         # e.g. "security-headers", "exposed-files", "misconfiguration"
    tags: tuple[str, ...]
    requests: tuple[ProbeRequest, ...]

    remediation: str = ""
    references: tuple[str, ...] = ()
    cvss_score: float | None = None  # optional CVSS base score

    def __hash__(self) -> int:
        return hash(self.id)
