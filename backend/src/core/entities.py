"""Typed OSINT entity model following the Entity-Attribute-Relationship (EAR) pattern.

Every entity in an OSINT graph has:
  - entity_type: Fully qualified type string (e.g. "osint.IPv4Address")
  - value:       Canonical string representation (e.g. "8.8.8.8")
  - properties:  Key/value attributes attached to the entity
  - relations:   Directed edges to other entities with a labelled relation type

This module is framework-agnostic and has no external dependencies beyond stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Entity types
# ---------------------------------------------------------------------------


class EntityType(StrEnum):
    # Network / Infrastructure
    IPv4_ADDRESS = "osint.IPv4Address"
    IPv6_ADDRESS = "osint.IPv6Address"
    DOMAIN = "osint.DNSDomain"
    URL = "osint.URL"
    WEBSITE = "osint.Website"
    NETBLOCK = "osint.Netblock"
    AS = "osint.AS"
    PORT = "osint.Port"
    BANNER = "osint.Banner"
    # Identity
    EMAIL_ADDRESS = "osint.EmailAddress"
    PHONE_NUMBER = "osint.PhoneNumber"
    PERSON = "osint.Person"
    ALIAS = "osint.Alias"
    USERNAME = "osint.Username"
    # Organisation
    ORGANIZATION = "osint.Organization"
    # Social / SOCMINT
    TWITTER_PROFILE = "osint.TwitterProfile"
    FACEBOOK_PROFILE = "osint.FacebookProfile"
    INSTAGRAM_PROFILE = "osint.InstagramProfile"
    LINKEDIN_PROFILE = "osint.LinkedInProfile"
    GITHUB_PROFILE = "osint.GitHubProfile"
    TELEGRAM_PROFILE = "osint.TelegramProfile"
    REDDIT_PROFILE = "osint.RedditProfile"
    # Threat Intelligence
    MALWARE = "osint.Malware"
    HASH = "osint.Hash"
    CVE = "osint.CVE"
    THREAT_ACTOR = "osint.ThreatActor"
    # Documents / Files
    DOCUMENT = "osint.Document"
    IMAGE = "osint.Image"
    PDF = "osint.PDF"
    # Location
    LOCATION = "osint.Location"
    GPS_COORDINATE = "osint.GPSCoordinate"
    # Custom OSINT types
    BREACH = "osint.Breach"
    TRACKING_CODE = "osint.TrackingCode"
    CERTIFICATE = "osint.Certificate"
    PASTE = "osint.Paste"
    ASN = "osint.ASN"
    INTERNAL_PATH = "osint.InternalPath"


class RelationType(StrEnum):
    """Directed relationship labels between entities."""
    RESOLVES_TO = "resolves_to"
    HOSTED_ON = "hosted_on"
    OWNS = "owns"
    USES = "uses"
    REGISTERED_TO = "registered_to"
    MEMBER_OF = "member_of"
    CONNECTED_TO = "connected_to"
    ALIAS_OF = "alias_of"
    EMPLOYED_BY = "employed_by"
    HAS_VULNERABILITY = "has_vulnerability"
    COMMUNICATES_WITH = "communicates_with"
    SHARES_TRACKING_CODE = "shares_tracking_code"
    FOUND_IN = "found_in"
    ISSUED_BY = "issued_by"
    RELATED_TO = "related_to"
    CREATED_BY = "created_by"
    LOCATED_AT = "located_at"
    PART_OF = "part_of"


# ---------------------------------------------------------------------------
# Property + Entity dataclasses
# ---------------------------------------------------------------------------


@dataclass
class EntityProperty:
    """A named, typed attribute attached to an entity."""

    name: str
    value: Any
    display_name: str = ""

    def __post_init__(self) -> None:
        if not self.display_name:
            self.display_name = self.name.replace("_", " ").title()

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "display_name": self.display_name}


@dataclass
class OsintEntity:
    """A typed OSINT entity following the Entity-Attribute-Relationship (EAR) pattern.

    Usage::

        ip_entity = OsintEntity(entity_type=EntityType.IPv4_ADDRESS, value="8.8.8.8")
        ip_entity.set_property("isp", "Google LLC")
        ip_entity.set_property("country", "US")
    """

    entity_type: EntityType
    value: str
    id: UUID = field(default_factory=uuid4)
    properties: dict[str, EntityProperty] = field(default_factory=dict)
    source_scanner: str = ""
    confidence: float = 1.0  # 0.0 – 1.0
    investigation_id: UUID | None = None

    # ------------------------------------------------------------------
    # Property accessors
    # ------------------------------------------------------------------

    def set_property(self, name: str, value: Any, display_name: str = "") -> None:
        self.properties[name] = EntityProperty(name=name, value=value, display_name=display_name)

    def get_property(self, name: str, default: Any = None) -> Any:
        prop = self.properties.get(name)
        return prop.value if prop else default

    def has_property(self, name: str) -> bool:
        return name in self.properties

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "entity_type": self.entity_type,
            "value": self.value,
            "properties": {k: v.to_dict() for k, v in self.properties.items()},
            "source_scanner": self.source_scanner,
            "confidence": self.confidence,
            "investigation_id": str(self.investigation_id) if self.investigation_id else None,
        }

    def __hash__(self) -> int:
        return hash((self.entity_type, self.value))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OsintEntity):
            return NotImplemented
        return self.entity_type == other.entity_type and self.value == other.value


@dataclass
class EntityRelation:
    """A directed relationship between two OsintEntity instances.

    Represents the 'R' in EAR — e.g. IP "resolves_to" Domain.
    """

    from_entity: OsintEntity
    to_entity: OsintEntity
    relation_type: RelationType
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    id: UUID = field(default_factory=uuid4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "from": self.from_entity.to_dict(),
            "to": self.to_entity.to_dict(),
            "relation_type": self.relation_type,
            "properties": self.properties,
            "confidence": self.confidence,
        }


# ---------------------------------------------------------------------------
# Typed factory functions
# ---------------------------------------------------------------------------


def make_ipv4(ip: str, source: str = "", **props: Any) -> OsintEntity:
    """Create an IPv4 address entity."""
    e = OsintEntity(entity_type=EntityType.IPv4_ADDRESS, value=ip, source_scanner=source)
    for k, v in props.items():
        e.set_property(k, v)
    return e


def make_domain(domain: str, source: str = "", **props: Any) -> OsintEntity:
    """Create a DNS domain entity."""
    e = OsintEntity(entity_type=EntityType.DOMAIN, value=domain.lower(), source_scanner=source)
    for k, v in props.items():
        e.set_property(k, v)
    return e


def make_email(email: str, source: str = "", **props: Any) -> OsintEntity:
    """Create an email address entity."""
    e = OsintEntity(entity_type=EntityType.EMAIL_ADDRESS, value=email.lower(), source_scanner=source)
    for k, v in props.items():
        e.set_property(k, v)
    return e


def make_person(name: str, source: str = "", **props: Any) -> OsintEntity:
    """Create a person entity."""
    e = OsintEntity(entity_type=EntityType.PERSON, value=name, source_scanner=source)
    for k, v in props.items():
        e.set_property(k, v)
    return e


def make_username(username: str, source: str = "", platform: str = "") -> OsintEntity:
    """Create a username / alias entity."""
    e = OsintEntity(entity_type=EntityType.USERNAME, value=username, source_scanner=source)
    if platform:
        e.set_property("platform", platform)
    return e


def make_phone(phone: str, source: str = "", **props: Any) -> OsintEntity:
    """Create a phone number entity (E.164 format preferred)."""
    e = OsintEntity(entity_type=EntityType.PHONE_NUMBER, value=phone, source_scanner=source)
    for k, v in props.items():
        e.set_property(k, v)
    return e


def make_hash(hash_value: str, algorithm: str = "SHA-256", source: str = "") -> OsintEntity:
    """Create a file/artifact hash entity."""
    e = OsintEntity(entity_type=EntityType.HASH, value=hash_value, source_scanner=source)
    e.set_property("algorithm", algorithm)
    return e


def make_cve(cve_id: str, source: str = "", cvss: float | None = None, **props: Any) -> OsintEntity:
    """Create a CVE vulnerability entity."""
    e = OsintEntity(entity_type=EntityType.CVE, value=cve_id.upper(), source_scanner=source)
    if cvss is not None:
        e.set_property("cvss_score", cvss)
    for k, v in props.items():
        e.set_property(k, v)
    return e


def make_tracking_code(code: str, code_type: str, source: str = "") -> OsintEntity:
    """Create a web tracking code entity (GA/AdSense/GTM etc.)."""
    e = OsintEntity(entity_type=EntityType.TRACKING_CODE, value=code, source_scanner=source)
    e.set_property("code_type", code_type, display_name="Code Type")
    return e


def make_location(
    label: str,
    lat: float | None = None,
    lon: float | None = None,
    source: str = "",
    **props: Any,
) -> OsintEntity:
    """Create a geo-location entity."""
    e = OsintEntity(entity_type=EntityType.LOCATION, value=label, source_scanner=source)
    if lat is not None:
        e.set_property("latitude", lat)
    if lon is not None:
        e.set_property("longitude", lon)
    for k, v in props.items():
        e.set_property(k, v)
    return e


def make_url(url: str, source: str = "", **props: Any) -> OsintEntity:
    """Create a URL entity."""
    e = OsintEntity(entity_type=EntityType.URL, value=url, source_scanner=source)
    for k, v in props.items():
        e.set_property(k, v)
    return e


def make_breach(name: str, source: str = "", **props: Any) -> OsintEntity:
    """Create a data breach entity."""
    e = OsintEntity(entity_type=EntityType.BREACH, value=name, source_scanner=source)
    for k, v in props.items():
        e.set_property(k, v)
    return e


def relate(
    from_entity: OsintEntity,
    to_entity: OsintEntity,
    relation: RelationType,
    confidence: float = 1.0,
    **props: Any,
) -> EntityRelation:
    """Convenience function to create a typed relation between two entities."""
    return EntityRelation(
        from_entity=from_entity,
        to_entity=to_entity,
        relation_type=relation,
        properties=props,
        confidence=confidence,
    )
