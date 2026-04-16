"""Domain enums and shared types for the OSINT platform."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class UserRole(str, Enum):
    """Roles that govern what a user can do on the platform."""

    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class SubscriptionTier(str, Enum):
    """Billing tiers that determine feature access."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Feature(str, Enum):
    """Individual platform capabilities gated by subscription tier."""

    BASIC_SEARCH = "basic_search"
    DEEP_SCAN = "deep_scan"
    GRAPH_ANALYSIS = "graph_analysis"
    EXPORT_REPORT = "export_report"
    API_ACCESS = "api_access"
    BULK_SCAN = "bulk_scan"


# Feature access matrix — maps each tier to the features it unlocks.
TIER_FEATURES: dict[SubscriptionTier, frozenset[Feature]] = {
    SubscriptionTier.FREE: frozenset({Feature.BASIC_SEARCH}),
    SubscriptionTier.PRO: frozenset(
        {
            Feature.BASIC_SEARCH,
            Feature.DEEP_SCAN,
            Feature.GRAPH_ANALYSIS,
            Feature.EXPORT_REPORT,
        }
    ),
    SubscriptionTier.ENTERPRISE: frozenset(Feature),
}


class InvestigationStatus(str, Enum):
    """Lifecycle states of an investigation."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ScanInputType(str, Enum):
    """Supported input types for OSINT scans."""

    EMAIL = "email"
    PHONE = "phone"
    USERNAME = "username"
    NIP = "nip"
    URL = "url"
    IP_ADDRESS = "ip_address"
    DOMAIN = "domain"


class NodeType(str, Enum):
    """Types of nodes in the investigation knowledge graph."""

    PERSON = "person"
    COMPANY = "company"
    EMAIL = "email"
    PHONE = "phone"
    USERNAME = "username"
    IP = "ip"
    DOMAIN = "domain"
    SERVICE = "service"
    LOCATION = "location"
    VULNERABILITY = "vulnerability"
    BREACH = "breach"


class RelationshipType(str, Enum):
    """Types of edges connecting graph nodes."""

    OWNS = "owns"
    USES = "uses"
    MEMBER_OF = "member_of"
    CONNECTED_TO = "connected_to"
    REGISTERED_TO = "registered_to"
    EMPLOYED_BY = "employed_by"
    ALIAS_OF = "alias_of"


class ScanStatus(str, Enum):
    """Outcome states of an individual scanner run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class SeedInput:
    """A single seed value provided by the analyst to kick off scanning."""

    value: str
    input_type: ScanInputType
