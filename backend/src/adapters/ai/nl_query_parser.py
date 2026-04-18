"""Natural language query parser for OSINT investigations.

Parses queries like 'find all accounts for john@example.com' into
structured scanner selections and seed inputs.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from src.core.domain.entities.types import ScanInputType


@dataclass
class ParsedQuery:
    """Result of parsing a natural language query."""

    seed_inputs: list[dict[str, str]] = field(default_factory=list)
    suggested_scanners: list[str] = field(default_factory=list)
    intent: str = "investigate"
    confidence: float = 0.0
    raw_query: str = ""


# Regex patterns for entity extraction
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"
)
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DOMAIN_PATTERN = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")
URL_PATTERN = re.compile(r"https?://[^\s]+")
NIP_PATTERN = re.compile(r"\b\d{10}\b")
USERNAME_PATTERN = re.compile(r"@([a-zA-Z0-9_]{3,30})")

# Intent keywords mapped to scanner types
INTENT_MAP: dict[str, list[str]] = {
    "breach": ["breach", "holehe"],
    "social": ["maigret", "twitter", "facebook", "instagram", "linkedin", "github"],
    "infrastructure": ["shodan", "dns", "whois", "cert", "subdomain", "geoip"],
    "company": ["playwright_krs", "playwright_ceidg", "vat"],
    "deep": [],  # all scanners
    "monitor": [],
    "investigate": [],
}

INTENT_KEYWORDS: dict[str, list[str]] = {
    "breach": ["breach", "leaked", "compromised", "pwned", "exposed", "hack"],
    "social": ["social", "account", "profile", "username", "media", "presence"],
    "infrastructure": [
        "infra",
        "server",
        "port",
        "dns",
        "domain",
        "hosting",
        "certificate",
        "subdomain",
    ],
    "company": ["company", "business", "nip", "krs", "vat", "registration", "firma"],
    "deep": ["deep", "thorough", "everything", "all", "full", "complete"],
    "monitor": ["monitor", "watch", "track", "alert", "notify"],
}


def parse_nl_query(query: str) -> ParsedQuery:
    """Parse a natural language query into structured investigation parameters."""
    result = ParsedQuery(raw_query=query)
    query_lower = query.lower()

    # Extract entities
    _extract_entities(query, result)

    # Determine intent
    best_intent = "investigate"
    best_score = 0
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > best_score:
            best_score = score
            best_intent = intent

    result.intent = best_intent
    result.suggested_scanners = INTENT_MAP.get(best_intent, [])

    # Calculate confidence based on extracted entities and intent match
    entity_confidence = min(len(result.seed_inputs) * 0.3, 0.6)
    intent_confidence = min(best_score * 0.15, 0.4)
    result.confidence = min(entity_confidence + intent_confidence, 1.0)

    return result


def _extract_entities(text: str, result: ParsedQuery) -> None:
    """Extract all recognizable entities from text."""
    # Order matters: URL before domain, email before domain
    for url in URL_PATTERN.findall(text):
        result.seed_inputs.append(
            {"value": url, "input_type": ScanInputType.URL.value}
        )

    for email in EMAIL_PATTERN.findall(text):
        result.seed_inputs.append(
            {"value": email, "input_type": ScanInputType.EMAIL.value}
        )

    for ip in IP_PATTERN.findall(text):
        parts = ip.split(".")
        if all(0 <= int(p) <= 255 for p in parts):
            result.seed_inputs.append(
                {"value": ip, "input_type": ScanInputType.IP_ADDRESS.value}
            )

    # NIP before generic domain (10-digit numbers)
    for nip in NIP_PATTERN.findall(text):
        # Skip if it's part of an IP
        if not any(nip in inp["value"] for inp in result.seed_inputs):
            result.seed_inputs.append(
                {"value": nip, "input_type": ScanInputType.NIP.value}
            )

    # Domains - exclude already-matched emails and URLs
    existing_values = {inp["value"] for inp in result.seed_inputs}
    for domain in DOMAIN_PATTERN.findall(text):
        if domain not in existing_values and not any(
            domain in v for v in existing_values
        ):
            # Skip common non-domain words
            if domain.count(".") >= 1 and len(domain) > 4:
                result.seed_inputs.append(
                    {"value": domain, "input_type": ScanInputType.DOMAIN.value}
                )

    # Usernames (with @ prefix)
    for username in USERNAME_PATTERN.findall(text):
        result.seed_inputs.append(
            {"value": username, "input_type": ScanInputType.USERNAME.value}
        )


def extract_entities_from_text(text: str) -> list[dict[str, str]]:
    """Standalone entity extraction from any text block."""
    result = ParsedQuery()
    _extract_entities(text, result)
    return result.seed_inputs
