"""Geo-clustering endpoint — cluster geo-tagged findings by location proximity.

GET /api/v1/geo/clusters/{investigation_id} — return geo clusters for an investigation
"""

from __future__ import annotations

import math
import re
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.adapters.db.models import ScanResultModel, UserModel

log = structlog.get_logger(__name__)

router = APIRouter()

_COORD_RE = re.compile(r'(?i)(?:lat|latitude)["\s:]+(-?\d{1,3}\.\d+)[,\s]+(?:lon|long|longitude)["\s:]+(-?\d{1,3}\.\d+)')


class GeoPoint(BaseModel):
    lat: float
    lon: float
    label: str
    source: str
    finding_type: str


class GeoCluster(BaseModel):
    cluster_id: int
    center_lat: float
    center_lon: float
    radius_km: float
    point_count: int
    points: list[GeoPoint]
    dominant_source: str
    label: str


class GeoClusterResponse(BaseModel):
    investigation_id: str
    total_geo_points: int
    clusters: list[GeoCluster]
    bounding_box: dict[str, float] | None


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _extract_geo_points(findings: list[dict[str, Any]], source: str) -> list[GeoPoint]:
    points: list[GeoPoint] = []
    for f in findings:
        lat = f.get("latitude") or f.get("lat")
        lon = f.get("longitude") or f.get("lon") or f.get("lng")
        if lat is not None and lon is not None:
            try:
                points.append(GeoPoint(
                    lat=float(lat),
                    lon=float(lon),
                    label=f.get("city") or f.get("country") or f.get("label") or source,
                    source=source,
                    finding_type=f.get("type", "unknown"),
                ))
            except (ValueError, TypeError):
                pass
        # Also try to parse from raw text
        raw_str = str(f)
        for m in _COORD_RE.finditer(raw_str):
            try:
                points.append(GeoPoint(
                    lat=float(m.group(1)),
                    lon=float(m.group(2)),
                    label=source,
                    source=source,
                    finding_type=f.get("type", "unknown"),
                ))
            except (ValueError, TypeError):
                pass
    return points


def _simple_cluster(points: list[GeoPoint], radius_km: float = 100.0) -> list[GeoCluster]:
    """Simple greedy clustering: assign point to nearest existing cluster center."""
    clusters: list[list[GeoPoint]] = []

    for pt in points:
        assigned = False
        for cluster in clusters:
            center_lat = sum(p.lat for p in cluster) / len(cluster)
            center_lon = sum(p.lon for p in cluster) / len(cluster)
            if _haversine(pt.lat, pt.lon, center_lat, center_lon) <= radius_km:
                cluster.append(pt)
                assigned = True
                break
        if not assigned:
            clusters.append([pt])

    result: list[GeoCluster] = []
    for idx, cluster in enumerate(clusters):
        center_lat = sum(p.lat for p in cluster) / len(cluster)
        center_lon = sum(p.lon for p in cluster) / len(cluster)
        max_dist = max(
            _haversine(p.lat, p.lon, center_lat, center_lon) for p in cluster
        ) if len(cluster) > 1 else 0.0
        source_counts: dict[str, int] = {}
        for p in cluster:
            source_counts[p.source] = source_counts.get(p.source, 0) + 1
        dominant = max(source_counts, key=source_counts.__getitem__)
        labels = [p.label for p in cluster if p.label]
        label = labels[0] if labels else f"Cluster {idx + 1}"
        result.append(GeoCluster(
            cluster_id=idx,
            center_lat=round(center_lat, 5),
            center_lon=round(center_lon, 5),
            radius_km=round(max_dist, 2),
            point_count=len(cluster),
            points=cluster[:20],
            dominant_source=dominant,
            label=label,
        ))

    return sorted(result, key=lambda c: c.point_count, reverse=True)


@router.get("/geo/clusters/{investigation_id}",
            response_model=GeoClusterResponse, tags=["geo"])
async def get_geo_clusters(
    investigation_id: str,
    radius_km: float = 100.0,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> GeoClusterResponse:
    """Cluster geo-tagged findings for an investigation by proximity."""

    result = await db.execute(
        select(ScanResultModel).where(
            ScanResultModel.investigation_id == investigation_id
        ).limit(200)
    )
    scan_results = result.scalars().all()
    if not scan_results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No scan results for this investigation")

    all_points: list[GeoPoint] = []
    for sr in scan_results:
        findings = (sr.raw_data or {}).get("findings", [])
        all_points.extend(_extract_geo_points(findings, sr.scanner_name or "unknown"))

    if not all_points:
        return GeoClusterResponse(
            investigation_id=investigation_id,
            total_geo_points=0,
            clusters=[],
            bounding_box=None,
        )

    clusters = _simple_cluster(all_points, radius_km=radius_km)

    bbox = {
        "min_lat": min(p.lat for p in all_points),
        "max_lat": max(p.lat for p in all_points),
        "min_lon": min(p.lon for p in all_points),
        "max_lon": max(p.lon for p in all_points),
    }

    return GeoClusterResponse(
        investigation_id=investigation_id,
        total_geo_points=len(all_points),
        clusters=clusters,
        bounding_box=bbox,
    )
