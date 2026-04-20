"""Tests for ML endpoints."""
import pytest
from unittest.mock import MagicMock


class TestMLEndpoints:
    @pytest.mark.asyncio
    async def test_detect_anomalies(self) -> None:
        from src.api.v1.ml import detect_anomalies, AnomalyRequest, get_anomaly_detector

        body = AnomalyRequest(scan_results=[{
            "scanner_name": "test",
            "raw_data": {"ports": list(range(60))},
            "extracted_identifiers": [],
        }])
        result = await detect_anomalies(
            body=body, current_user=MagicMock(), detector=get_anomaly_detector()
        )
        assert result.total >= 1

    @pytest.mark.asyncio
    async def test_risk_score(self) -> None:
        from src.api.v1.ml import compute_risk_score, RiskScoreRequest, get_anomaly_detector

        body = RiskScoreRequest(scan_results=[{"raw_data": {"vulns": ["CVE-1"]}}])
        result = await compute_risk_score(
            body=body, current_user=MagicMock(), detector=get_anomaly_detector()
        )
        assert result.score >= 0

    @pytest.mark.asyncio
    async def test_link_prediction(self) -> None:
        from src.api.v1.ml import predict_links, LinkPredictionRequest, get_link_predictor

        body = LinkPredictionRequest(
            nodes=[
                {"id": "1", "type": "person", "data": {}},
                {"id": "2", "type": "email", "data": {}},
            ],
            edges=[],
        )
        result = await predict_links(
            body=body, current_user=MagicMock(), predictor=get_link_predictor()
        )
        assert result.total >= 0
