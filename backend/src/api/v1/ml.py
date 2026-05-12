"""ML/AI analysis endpoints."""
import hashlib
import math
from collections import Counter
from typing import Any, Annotated

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.ai.anomaly_detector import AnomalyDetector
from src.adapters.ai.link_predictor import LinkPredictor
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger()
router = APIRouter()

_anomaly_detector: AnomalyDetector | None = None
_link_predictor: LinkPredictor | None = None


def get_anomaly_detector() -> AnomalyDetector:
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
    return _anomaly_detector


def get_link_predictor() -> LinkPredictor:
    global _link_predictor
    if _link_predictor is None:
        _link_predictor = LinkPredictor()
    return _link_predictor


class AnomalyRequest(BaseModel):
    scan_results: list[dict[str, Any]]


class AnomalyResponse(BaseModel):
    anomalies: list[dict[str, Any]]
    total: int


class RiskScoreRequest(BaseModel):
    scan_results: list[dict[str, Any]]


class RiskScoreResponse(BaseModel):
    score: float
    level: str
    factors: list[dict[str, Any]]


class LinkPredictionRequest(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class LinkPredictionResponse(BaseModel):
    predictions: list[dict[str, Any]]
    total: int


@router.post("/ml/anomalies", response_model=AnomalyResponse)
async def detect_anomalies(
    body: AnomalyRequest,
    current_user: Any = Depends(get_current_user),
    detector: AnomalyDetector = Depends(get_anomaly_detector),
) -> AnomalyResponse:
    anomalies = detector.detect_anomalies(body.scan_results)
    return AnomalyResponse(anomalies=anomalies, total=len(anomalies))


@router.post("/ml/risk-score", response_model=RiskScoreResponse)
async def compute_risk_score(
    body: RiskScoreRequest,
    current_user: Any = Depends(get_current_user),
    detector: AnomalyDetector = Depends(get_anomaly_detector),
) -> RiskScoreResponse:
    result = detector.compute_risk_score(body.scan_results)
    return RiskScoreResponse(**result)


@router.post("/ml/link-prediction", response_model=LinkPredictionResponse)
async def predict_links(
    body: LinkPredictionRequest,
    current_user: Any = Depends(get_current_user),
    predictor: LinkPredictor = Depends(get_link_predictor),
) -> LinkPredictionResponse:
    predictions = predictor.predict_links(body.nodes, body.edges)
    return LinkPredictionResponse(predictions=predictions, total=len(predictions))


# ---------------------------------------------------------------------------
# Investigation Similarity Clustering (Feature 5)
# ---------------------------------------------------------------------------


class SimilarityCluster(BaseModel):
    cluster_id: int
    investigation_ids: list[str]
    investigation_titles: list[str]
    centroid_terms: list[str]  # top TF-IDF terms
    avg_similarity: float
    size: int


class SimilarityClusterResponse(BaseModel):
    clusters: list[SimilarityCluster]
    total_investigations: int
    total_clusters: int
    method: str


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    import re
    return [t.lower() for t in re.split(r"[^a-z0-9_@.-]+", text.lower()) if len(t) > 2]


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = Counter(tokens)
    total = max(len(tokens), 1)
    return {t: (c / total) * idf.get(t, 1.0) for t, c in tf.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[k] * b[k] for k in common)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


@router.get("/ml/similarity-clusters", response_model=SimilarityClusterResponse)
async def similarity_clusters(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    threshold: float = Query(0.35, ge=0.0, le=1.0),
    max_investigations: int = Query(50, ge=5, le=200),
) -> SimilarityClusterResponse:
    """
    Cluster investigations by TF-IDF cosine similarity on title + seed values.
    Uses single-linkage agglomerative clustering with a configurable threshold.
    """
    from src.adapters.db.models import InvestigationModel

    result = await db.execute(
        select(InvestigationModel)
        .where(InvestigationModel.owner_id == current_user.id)
        .limit(max_investigations)
    )
    investigations = result.scalars().all()

    if len(investigations) < 2:
        return SimilarityClusterResponse(clusters=[], total_investigations=len(investigations), total_clusters=0, method="tfidf-cosine")

    # Build per-investigation document: title + seed values
    docs: list[tuple[str, str, str]] = []
    for inv in investigations:
        seeds = inv.seed_inputs or []
        seed_text = " ".join(s.get("value", "") for s in seeds if isinstance(s, dict))
        text = f"{inv.title} {inv.description or ''} {seed_text}"
        docs.append((str(inv.id), inv.title, text))

    # IDF
    all_tokens = [_tokenize(d[2]) for d in docs]
    df: Counter = Counter()
    for tokens in all_tokens:
        df.update(set(tokens))
    N = len(docs)
    idf = {t: math.log(N / (1 + c)) for t, c in df.items()}

    vectors = [_tfidf_vector(tokens, idf) for tokens in all_tokens]

    # Single-linkage agglomerative clustering
    cluster_assignments = list(range(N))

    def find(i: int) -> int:
        while cluster_assignments[i] != i:
            cluster_assignments[i] = cluster_assignments[cluster_assignments[i]]
            i = cluster_assignments[i]
        return i

    for i in range(N):
        for j in range(i + 1, N):
            sim = _cosine(vectors[i], vectors[j])
            if sim >= threshold:
                ri, rj = find(i), find(j)
                if ri != rj:
                    cluster_assignments[ri] = rj

    # Group
    groups: dict[int, list[int]] = {}
    for idx in range(N):
        root = find(idx)
        groups.setdefault(root, []).append(idx)

    clusters: list[SimilarityCluster] = []
    for cluster_id, (root, members) in enumerate(groups.items()):
        if len(members) == 1:
            continue  # skip singletons
        inv_ids = [docs[m][0] for m in members]
        inv_titles = [docs[m][1] for m in members]
        # centroid = average vector; top terms by weight
        centroid: dict[str, float] = {}
        for m in members:
            for term, weight in vectors[m].items():
                centroid[term] = centroid.get(term, 0) + weight / len(members)
        top_terms = sorted(centroid.items(), key=lambda x: -x[1])[:8]
        # avg pairwise similarity
        sims = [
            _cosine(vectors[members[a]], vectors[members[b]])
            for a in range(len(members))
            for b in range(a + 1, len(members))
        ]
        avg_sim = sum(sims) / len(sims) if sims else 0.0

        clusters.append(SimilarityCluster(
            cluster_id=cluster_id,
            investigation_ids=inv_ids,
            investigation_titles=inv_titles,
            centroid_terms=[t for t, _ in top_terms],
            avg_similarity=round(avg_sim, 3),
            size=len(members),
        ))

    clusters.sort(key=lambda c: (-c.size, -c.avg_similarity))
    log.info("Similarity clustering done", investigations=N, clusters=len(clusters), threshold=threshold)

    return SimilarityClusterResponse(
        clusters=clusters,
        total_investigations=N,
        total_clusters=len(clusters),
        method="tfidf-cosine",
    )
