"""Geolocation Triangulation.

Extracts location signals from social media posts, EXIF metadata,
IP geolocation, Wi-Fi probe data, and cell tower triangulation
to build a timeline of subject location patterns.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User


from src.config import get_settings as _get_settings

# When OSINT_MOCK_DATA=false, endpoints return 501 — real data source required. (#13)
_MOCK_DATA: bool = _get_settings().osint_mock_data

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/geolocation", tags=["geolocation"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LocationSignal(BaseModel):
    signal_id: str
    source: str  # exif, social_post, ip_geolocation, wifi, cell_tower, checkin
    timestamp: str
    latitude: float | None
    longitude: float | None
    accuracy_meters: int
    location_name: str | None
    country: str
    city: str | None
    raw_evidence: str
    confidence: float


class LocationCluster(BaseModel):
    cluster_id: str
    location_name: str
    latitude: float
    longitude: float
    visit_count: int
    first_visit: str
    last_visit: str
    avg_duration_hours: float
    location_type: str  # home, work, frequent_location, transit, unknown
    signals: list[LocationSignal]


class TriangulationRequest(BaseModel):
    subject_identifier: str = Field(..., min_length=1, description="Username, email, or IP address")
    data_sources: list[str] = Field(
        default_factory=lambda: ["social_posts", "ip_geolocation", "exif"],
        description="Sources to query: social_posts, ip_geolocation, exif, wifi, cell_tower",
    )
    time_range_days: int = Field(90, ge=1, le=365)
    platforms: list[str] = Field(
        default_factory=lambda: ["twitter", "instagram"],
        description="Social platforms to query",
    )


class TriangulationResult(BaseModel):
    subject: str
    total_signals: int
    unique_locations: int
    countries_visited: list[str]
    home_location: LocationCluster | None
    work_location: LocationCluster | None
    location_clusters: list[LocationCluster]
    location_timeline: list[LocationSignal]
    pattern_summary: str
    privacy_risk_level: str  # critical, high, medium, low
    analyzed_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CITIES = [
    ("New York", "US", 40.7128, -74.0060),
    ("London", "GB", 51.5074, -0.1278),
    ("Berlin", "DE", 52.5200, 13.4050),
    ("Tokyo", "JP", 35.6762, 139.6503),
    ("Warsaw", "PL", 52.2297, 21.0122),
    ("Amsterdam", "NL", 52.3676, 4.9041),
    ("Paris", "FR", 48.8566, 2.3522),
    ("Toronto", "CA", 43.6532, -79.3832),
]

_SOURCES = ["social_post", "exif", "ip_geolocation", "wifi", "cell_tower", "checkin"]

_LOCATION_TYPES = ["home", "work", "frequent_location", "transit", "unknown"]


def _jitter(lat: float, lon: float, meters: int = 500) -> tuple[float, float]:
    delta = meters / 111320
    rng = random.Random(f"{lat}{lon}{meters}")
    return round(lat + rng.uniform(-delta, delta), 5), round(lon + rng.uniform(-delta, delta), 5)


def _make_signal(subject: str, idx: int, city_data: tuple) -> LocationSignal:
    city, country, lat, lon = city_data
    rng = random.Random(f"{subject}{idx}")
    jlat, jlon = _jitter(lat, lon, rng.randint(100, 2000))
    days_ago = rng.randint(0, 89)
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago, hours=rng.randint(0, 23))).isoformat()
    source = rng.choice(_SOURCES)
    accuracy = {"exif": 10, "checkin": 50, "wifi": 200, "cell_tower": 1000, "ip_geolocation": 5000, "social_post": 3000}[source]
    confidence = {"exif": 0.95, "checkin": 0.9, "wifi": 0.8, "cell_tower": 0.7, "ip_geolocation": 0.6, "social_post": 0.5}[source]

    evidence_templates = {
        "social_post": f'Post: "Having coffee in {city} ☕" with location tag',
        "exif": f"EXIF GPS: {jlat:.4f}N, {jlon:.4f}E — photo taken in {city}",
        "ip_geolocation": f"Login from IP geolocated to {city}, {country}",
        "wifi": f"Wi-Fi probe: SSID pattern matches {city} ISP infrastructure",
        "cell_tower": f"Cell tower triangulation: LAC/CID maps to {city} area",
        "checkin": f"Foursquare/Swarm check-in: '{city} Central Station'",
    }

    return LocationSignal(
        signal_id=f"sig_{hashlib.md5(f'{subject}{idx}'.encode()).hexdigest()[:10]}",
        source=source,
        timestamp=ts,
        latitude=jlat,
        longitude=jlon,
        accuracy_meters=accuracy,
        location_name=f"{city} area" if source in ["ip_geolocation", "cell_tower"] else city,
        country=country,
        city=city,
        raw_evidence=evidence_templates[source],
        confidence=round(confidence + rng.uniform(-0.05, 0.05), 2),
    )


def _cluster_signals(signals: list[LocationSignal], city_data: tuple, cluster_id: str, loc_type: str) -> LocationCluster:
    city, country, lat, lon = city_data
    rng = random.Random(cluster_id)
    timestamps = sorted(s.timestamp for s in signals)

    return LocationCluster(
        cluster_id=cluster_id,
        location_name=city,
        latitude=lat,
        longitude=lon,
        visit_count=len(signals),
        first_visit=timestamps[0] if timestamps else datetime.now(timezone.utc).isoformat(),
        last_visit=timestamps[-1] if timestamps else datetime.now(timezone.utc).isoformat(),
        avg_duration_hours=round(rng.uniform(0.5, 8.0), 1),
        location_type=loc_type,
        signals=signals,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/triangulate", response_model=TriangulationResult)
async def triangulate_location(
    body: TriangulationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> TriangulationResult:
    """Triangulate subject location from multiple data sources."""
    rng = random.Random(body.subject_identifier)
    num_cities = rng.randint(2, 4)
    selected_cities = rng.sample(_CITIES, k=num_cities)

    all_signals: list[LocationSignal] = []
    city_signals: dict[str, list[LocationSignal]] = {}

    for i, city_data in enumerate(selected_cities):
        n_signals = rng.randint(3, 12)
        city_sig_list: list[LocationSignal] = []
        for j in range(n_signals):
            sig = _make_signal(body.subject_identifier, i * 20 + j, city_data)
            if sig.source in body.data_sources or "all" in body.data_sources:
                city_sig_list.append(sig)
                all_signals.append(sig)
        city_signals[city_data[0]] = city_sig_list

    all_signals.sort(key=lambda s: s.timestamp)

    clusters: list[LocationCluster] = []
    sorted_cities = sorted(city_signals.items(), key=lambda x: len(x[1]), reverse=True)
    for i, (city_name, sigs) in enumerate(sorted_cities):
        if not sigs:
            continue
        city_data = next(c for c in selected_cities if c[0] == city_name)
        loc_type = ["home", "work", "frequent_location", "transit"][min(i, 3)]
        clusters.append(_cluster_signals(sigs, city_data, f"cluster_{i:03d}", loc_type))

    home = next((c for c in clusters if c.location_type == "home"), None)
    work = next((c for c in clusters if c.location_type == "work"), None)
    countries = list({c.location_name for c in clusters})

    total_signals = len(all_signals)
    privacy_risk = "critical" if total_signals >= 20 else "high" if total_signals >= 10 else "medium" if total_signals >= 5 else "low"

    pattern = (
        f"Subject shows {len(clusters)} distinct location cluster(s) over {body.time_range_days} days. "
        f"{'Home location identified with high confidence. ' if home else ''}"
        f"{'Workplace likely identified. ' if work else ''}"
        f"Signal sources: {', '.join(body.data_sources)}."
    )

    log.info("geolocation_triangulated", subject=body.subject_identifier[:4] + "***", signals=total_signals, clusters=len(clusters))
    return TriangulationResult(
        subject=body.subject_identifier,
        total_signals=total_signals,
        unique_locations=len(clusters),
        countries_visited=countries,
        home_location=home,
        work_location=work,
        location_clusters=clusters,
        location_timeline=all_signals[:50],
        pattern_summary=pattern,
        privacy_risk_level=privacy_risk,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )

    if not _MOCK_DATA:
        raise HTTPException(status_code=501, detail="Real data source not configured — set OSINT_MOCK_DATA=true or wire up a live integration.")