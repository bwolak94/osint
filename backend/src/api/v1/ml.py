"""ML/AI analysis endpoints."""
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.adapters.ai.anomaly_detector import AnomalyDetector
from src.adapters.ai.link_predictor import LinkPredictor
from src.api.v1.auth.dependencies import get_current_user

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
