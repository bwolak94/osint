"""Attribution Scorer — scores investigation entities against a built-in TTP library.

Compares extracted entities and scan results against known threat-actor
Tactics, Techniques and Procedures (TTPs) to surface probable attributions.

The built-in TTP library is a conservative, illustrative set of 10 known
threat actor patterns.  Each actor entry contains:

  - ``indicators``  — list of matching rules (see ``_score_actor`` for details)
  - ``description`` — one-line summary suitable for analyst reports

Indicator rule format:
  ``{"field": <entity field>, "match": <substring|regex prefix>, "weight": <float>}``

Fields that can be matched:
  - ``value``       — entity value string
  - ``type``        — entity type string
  - ``tld``         — TLD extracted from domain/URL values
  - ``asn``         — ASN string from properties
  - ``tag``         — any tag in properties.tags list
  - ``port``        — any port in properties.ports list (stringified)
  - ``scanner``     — scanner_name from scan_results entries

Usage::

    scorer = AttributionScorer()
    results = scorer.score(entities, scan_results)
    for r in results:
        print(r.threat_actor, f"{r.confidence:.2%}", r.matched_indicators)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class AttributionResult:
    """Score of one threat actor against the investigation's evidence.

    Attributes:
        threat_actor:        Common name of the threat actor group.
        confidence:          Normalised score in [0.0, 1.0].
        matched_indicators:  Human-readable descriptions of matched rules.
        description:         One-line actor profile for analyst reports.
    """

    threat_actor: str
    confidence: float
    matched_indicators: list[str] = field(default_factory=list)
    description: str = ""


# ---------------------------------------------------------------------------
# Built-in TTP library
# ---------------------------------------------------------------------------

# Each entry:
#   "max_weight": sum of all indicator weights (used for normalisation).
#   "description": analyst-facing description.
#   "indicators": list of rule dicts.
#
# Rule dict keys:
#   field   — which aspect of an entity or scan to inspect.
#   match   — substring (str) or compiled regex (re.Pattern) to look for.
#   weight  — contribution to the raw score when the rule fires.
#   label   — human-readable description added to matched_indicators.

_TTP_LIBRARY: dict[str, dict[str, Any]] = {
    "APT28 (Fancy Bear)": {
        "description": (
            "Russian GRU-affiliated group targeting political, military and "
            "critical-infrastructure organisations since ~2004."
        ),
        "indicators": [
            {
                "field": "tld", "match": ".ru", "weight": 2.0,
                "label": "Domain uses .ru TLD (Russian hosting)",
            },
            {
                "field": "tld", "match": ".su", "weight": 1.5,
                "label": "Domain uses legacy Soviet .su TLD",
            },
            {
                "field": "port", "match": "1080", "weight": 1.0,
                "label": "Port 1080 — SOCKS proxy commonly used by APT28",
            },
            {
                "field": "port", "match": "8080", "weight": 0.5,
                "label": "Port 8080 — alternative HTTP proxy",
            },
            {
                "field": "tag", "match": "vpn", "weight": 1.0,
                "label": "VPN service tag observed — matches APT28 OPSEC pattern",
            },
            {
                "field": "value", "match": re.compile(r"(vps|dedicat)", re.I), "weight": 0.8,
                "label": "Hostname suggests dedicated/VPS server — APT28 infrastructure pattern",
            },
        ],
    },
    "Lazarus Group": {
        "description": (
            "North Korean state-sponsored group (DPRK) known for financial theft, "
            "cryptocurrency heists and destructive malware since ~2009."
        ),
        "indicators": [
            {
                "field": "tag", "match": "cryptocurrency", "weight": 2.5,
                "label": "Cryptocurrency-related tag — core Lazarus targeting indicator",
            },
            {
                "field": "value", "match": re.compile(r"(btc|eth|wallet|defi|swap)", re.I), "weight": 2.0,
                "label": "Crypto-related entity value (btc/eth/wallet/defi/swap)",
            },
            {
                "field": "asn", "match": "AS131279", "weight": 3.0,
                "label": "ASN AS131279 — known DPRK-attributed netblock",
            },
            {
                "field": "asn", "match": "AS136061", "weight": 2.5,
                "label": "ASN AS136061 — linked to Lazarus infrastructure",
            },
            {
                "field": "tld", "match": ".kp", "weight": 3.0,
                "label": "Domain uses .kp TLD (North Korean ccTLD)",
            },
        ],
    },
    "FIN7": {
        "description": (
            "Financially motivated cybercrime group targeting hospitality, "
            "retail and restaurant sectors with POS malware since ~2015."
        ),
        "indicators": [
            {
                "field": "tag", "match": "hospitality", "weight": 2.0,
                "label": "Hospitality sector tag — primary FIN7 target vertical",
            },
            {
                "field": "tag", "match": "retail", "weight": 1.5,
                "label": "Retail sector tag — secondary FIN7 target",
            },
            {
                "field": "tag", "match": "pos", "weight": 2.5,
                "label": "Point-of-sale related tag — FIN7 malware target",
            },
            {
                "field": "value", "match": re.compile(r"(carbanak|fin7|loadout)", re.I), "weight": 3.0,
                "label": "Known FIN7 / Carbanak malware family name detected",
            },
            {
                "field": "port", "match": "53", "weight": 0.5,
                "label": "DNS port — FIN7 often uses DNS tunnelling for C2",
            },
        ],
    },
    "Cozy Bear (APT29)": {
        "description": (
            "Russian SVR-affiliated group conducting long-term espionage against "
            "governments, think tanks and diplomatic missions since ~2008."
        ),
        "indicators": [
            {
                "field": "tld", "match": ".ru", "weight": 1.5,
                "label": "Domain uses .ru TLD",
            },
            {
                "field": "tag", "match": "government", "weight": 2.0,
                "label": "Government sector tag — APT29 primary target",
            },
            {
                "field": "tag", "match": "diplomatic", "weight": 2.5,
                "label": "Diplomatic sector tag — strong APT29 indicator",
            },
            {
                "field": "value", "match": re.compile(r"(office365|sharepoint|teams)", re.I), "weight": 1.5,
                "label": "Microsoft 365 / cloud service — APT29 commonly targets cloud identity",
            },
            {
                "field": "scanner", "match": "breach", "weight": 0.5,
                "label": "Breach data found — APT29 leverages credential theft",
            },
        ],
    },
    "Sandworm": {
        "description": (
            "Russian GRU Unit 74455 responsible for destructive cyber-attacks "
            "on Ukrainian critical infrastructure and the NotPetya wiper (2017)."
        ),
        "indicators": [
            {
                "field": "tld", "match": ".ua", "weight": 2.0,
                "label": "Domain uses .ua TLD — Sandworm primary target country",
            },
            {
                "field": "tag", "match": "industrial", "weight": 2.0,
                "label": "Industrial/ICS sector tag — Sandworm OT targeting",
            },
            {
                "field": "tag", "match": "energy", "weight": 2.0,
                "label": "Energy sector tag — Sandworm targeted Ukrainian power grid",
            },
            {
                "field": "value", "match": re.compile(r"(notpetya|industroyer|crashoverride)", re.I), "weight": 3.5,
                "label": "Known Sandworm malware family identifier",
            },
            {
                "field": "port", "match": "502", "weight": 1.5,
                "label": "Modbus port 502 — ICS protocol exploited by Sandworm",
            },
        ],
    },
    "Charming Kitten (APT35)": {
        "description": (
            "Iranian IRGC-affiliated group conducting phishing and credential "
            "harvesting against journalists, activists and dissidents."
        ),
        "indicators": [
            {
                "field": "tld", "match": ".ir", "weight": 2.5,
                "label": "Domain uses .ir TLD (Iranian ccTLD)",
            },
            {
                "field": "tag", "match": "phishing", "weight": 2.0,
                "label": "Phishing tag — primary Charming Kitten technique",
            },
            {
                "field": "value", "match": re.compile(r"(gmail|yahoo|outlook|login|signin)", re.I), "weight": 1.5,
                "label": "Credential-harvesting domain pattern (login/signin spoofing)",
            },
            {
                "field": "tag", "match": "journalist", "weight": 2.0,
                "label": "Journalist sector tag — key Charming Kitten target",
            },
            {
                "field": "scanner", "match": "holehe", "weight": 1.0,
                "label": "Social platform registrations found — matches Charming Kitten victim profiling",
            },
        ],
    },
    "Equation Group": {
        "description": (
            "NSA-affiliated threat actor deploying highly sophisticated implants "
            "and firmware-level malware; linked to STUXNET co-development."
        ),
        "indicators": [
            {
                "field": "tag", "match": "firmware", "weight": 3.0,
                "label": "Firmware-level tag — hallmark Equation Group capability",
            },
            {
                "field": "value", "match": re.compile(r"(stuxnet|fanny|doublefantasy|equationlaser)", re.I), "weight": 3.5,
                "label": "Known Equation Group implant family name",
            },
            {
                "field": "tag", "match": "nuclear", "weight": 2.0,
                "label": "Nuclear sector tag — Equation Group STUXNET targeting",
            },
            {
                "field": "port", "match": "445", "weight": 0.8,
                "label": "SMB port 445 — EternalBlue exploit vector",
            },
        ],
    },
    "Carbanak": {
        "description": (
            "FIN7-linked financial-sector threat actor that compromised over "
            "100 banks globally, stealing more than $1 billion via SWIFT fraud."
        ),
        "indicators": [
            {
                "field": "tag", "match": "banking", "weight": 2.5,
                "label": "Banking sector tag — Carbanak primary target",
            },
            {
                "field": "tag", "match": "swift", "weight": 3.0,
                "label": "SWIFT-related tag — Carbanak SWIFT transfer fraud indicator",
            },
            {
                "field": "value", "match": re.compile(r"(swift|iban|bic|atm)", re.I), "weight": 2.0,
                "label": "Banking/SWIFT related entity value",
            },
            {
                "field": "port", "match": "3389", "weight": 1.0,
                "label": "RDP port 3389 — Carbanak used RDP for lateral movement",
            },
        ],
    },
    "DarkSide": {
        "description": (
            "Ransomware-as-a-Service group (active 2020–2021) responsible for "
            "the Colonial Pipeline attack; believed to operate from Russia."
        ),
        "indicators": [
            {
                "field": "tag", "match": "ransomware", "weight": 3.0,
                "label": "Ransomware tag — DarkSide primary capability",
            },
            {
                "field": "tag", "match": "pipeline", "weight": 2.5,
                "label": "Pipeline/energy infrastructure tag — Colonial Pipeline targeting pattern",
            },
            {
                "field": "value", "match": re.compile(r"darkside", re.I), "weight": 3.5,
                "label": "DarkSide name directly referenced in entity value",
            },
            {
                "field": "tag", "match": "cryptocurrency", "weight": 1.5,
                "label": "Cryptocurrency ransom payment indicator",
            },
            {
                "field": "port", "match": "3389", "weight": 0.8,
                "label": "RDP port — common DarkSide initial access vector",
            },
        ],
    },
    "Hafnium": {
        "description": (
            "Chinese state-sponsored group (active 2021) that exploited "
            "zero-day vulnerabilities in Microsoft Exchange Server."
        ),
        "indicators": [
            {
                "field": "tld", "match": ".cn", "weight": 2.0,
                "label": "Domain uses .cn TLD (Chinese ccTLD)",
            },
            {
                "field": "value", "match": re.compile(r"(exchange|owa|autodiscover|proxylogon|proxyshell)", re.I), "weight": 3.0,
                "label": "Microsoft Exchange / ProxyLogon exploit pattern",
            },
            {
                "field": "port", "match": "443", "weight": 0.3,
                "label": "HTTPS port — Hafnium used HTTPS for webshell C2",
            },
            {
                "field": "tag", "match": "webshell", "weight": 3.0,
                "label": "Webshell tag — primary Hafnium post-exploitation technique",
            },
            {
                "field": "tag", "match": "defense", "weight": 1.5,
                "label": "Defence sector tag — Hafnium targeting pattern",
            },
        ],
    },
}


# Pre-compute max_weight for each actor (sum of all indicator weights).
for _actor, _data in _TTP_LIBRARY.items():
    _data["max_weight"] = sum(ind["weight"] for ind in _data["indicators"])


# ---------------------------------------------------------------------------
# Attribution scorer
# ---------------------------------------------------------------------------


class AttributionScorer:
    """Scores investigation evidence against the built-in TTP library.

    The scorer is stateless and thread-safe; ``score()`` can be called
    concurrently from multiple coroutines.
    """

    def __init__(self) -> None:
        self._ttp_library: dict[str, dict[str, Any]] = _TTP_LIBRARY

    def score(
        self,
        entities: list[dict[str, Any]],
        scan_results: list[dict[str, Any]],
    ) -> list[AttributionResult]:
        """Score entities and scan results against all known threat actors.

        Args:
            entities:     List of entity dicts with keys ``type``, ``value``,
                          and optional ``properties`` (dict with ``tags``,
                          ``ports``, ``asn``, etc.).
            scan_results: List of scan result dicts with ``scanner_name``.

        Returns:
            List of :class:`AttributionResult` sorted by ``confidence``
            descending.  Only actors with confidence > 0 are included.
            Returns empty list on failure.
        """
        if not entities and not scan_results:
            return []

        results: list[AttributionResult] = []
        try:
            for actor_name, ttp in self._ttp_library.items():
                result = self._score_actor(actor_name, ttp, entities, scan_results)
                if result.confidence > 0.0:
                    results.append(result)

            results.sort(key=lambda r: r.confidence, reverse=True)
            log.info(
                "Attribution scoring complete",
                entities=len(entities),
                actors_with_matches=len(results),
            )
        except Exception as exc:
            log.error("Attribution scoring failed", error=str(exc), exc_info=True)

        return results

    def _score_actor(
        self,
        actor_name: str,
        ttp: dict[str, Any],
        entities: list[dict[str, Any]],
        scan_results: list[dict[str, Any]],
    ) -> AttributionResult:
        """Compute raw score for one threat actor and normalise to [0, 1].

        For each indicator rule, every entity (or scan result) is tested.
        When the rule fires the indicator's weight is added to the raw score
        (capped at one fire per indicator to avoid double-counting).
        """
        raw_score = 0.0
        matched: list[str] = []
        max_weight: float = ttp.get("max_weight", 1.0) or 1.0

        for indicator in ttp.get("indicators", []):
            field = indicator["field"]
            match_target = indicator["match"]
            weight = indicator["weight"]
            label = indicator.get("label", f"{field}:{match_target}")
            fired = False

            # Test against every entity.
            for entity in entities:
                if fired:
                    break
                test_values = self._extract_field_values(entity, field)
                for val in test_values:
                    if self._matches(val, match_target):
                        fired = True
                        break

            # If not yet fired, test against scan result scanner names.
            if not fired and field == "scanner":
                for scan in scan_results:
                    scanner_name = scan.get("scanner_name", "")
                    if self._matches(scanner_name, match_target):
                        fired = True
                        break

            if fired:
                raw_score += weight
                matched.append(label)

        confidence = min(1.0, raw_score / max_weight) if max_weight > 0 else 0.0

        return AttributionResult(
            threat_actor=actor_name,
            confidence=round(confidence, 4),
            matched_indicators=matched,
            description=ttp.get("description", ""),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_field_values(entity: dict[str, Any], field: str) -> list[str]:
        """Extract the values for a given rule field from one entity dict."""
        props: dict[str, Any] = entity.get("properties", {}) or {}

        if field == "value":
            return [str(entity.get("value", ""))]

        if field == "type":
            return [str(entity.get("type", ""))]

        if field == "tld":
            value = str(entity.get("value", ""))
            # Extract the last two dot-separated segments as a pseudo-TLD.
            parts = value.rstrip("/").rsplit(".", 1)
            if len(parts) == 2:
                return [f".{parts[-1]}"]
            return []

        if field == "asn":
            asn = props.get("asn", "")
            return [str(asn)] if asn else []

        if field == "tag":
            tags = props.get("tags", [])
            return [str(t).lower() for t in tags] if isinstance(tags, list) else []

        if field == "port":
            ports = props.get("ports", [])
            return [str(p) for p in ports] if isinstance(ports, list) else []

        return []

    @staticmethod
    def _matches(value: str, target: str | re.Pattern[str]) -> bool:  # type: ignore[type-arg]
        """Return True if *value* satisfies *target* (substring or regex)."""
        if not value:
            return False
        if isinstance(target, re.Pattern):
            return bool(target.search(value))
        return target.lower() in value.lower()
