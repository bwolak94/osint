"""Tests for anomaly detector."""
from src.adapters.ai.anomaly_detector import AnomalyDetector


class TestAnomalyDetector:
    def test_detect_high_port_count(self) -> None:
        detector = AnomalyDetector()
        results = [{
            "scanner_name": "shodan",
            "input_value": "1.2.3.4",
            "raw_data": {"ports": list(range(60))},
            "extracted_identifiers": [],
        }]
        anomalies = detector.detect_anomalies(results)
        assert len(anomalies) == 1
        assert anomalies[0]["anomalies"][0]["type"] == "high_port_count"

    def test_no_anomalies_for_normal_data(self) -> None:
        detector = AnomalyDetector()
        results = [{
            "scanner_name": "dns",
            "input_value": "example.com",
            "raw_data": {"records": ["A"]},
            "extracted_identifiers": ["domain:example.com"],
        }]
        anomalies = detector.detect_anomalies(results)
        assert len(anomalies) == 0

    def test_risk_score_with_vulns(self) -> None:
        detector = AnomalyDetector()
        results = [{"raw_data": {"vulns": ["CVE-1", "CVE-2", "CVE-3"]}}]
        score = detector.compute_risk_score(results)
        assert score["score"] > 0
        assert score["level"] in ("low", "medium", "high", "critical")

    def test_risk_score_empty(self) -> None:
        detector = AnomalyDetector()
        score = detector.compute_risk_score([])
        assert score["score"] == 0.0
        assert score["level"] == "unknown"

    def test_severity_calculation(self) -> None:
        detector = AnomalyDetector()
        assert detector._calculate_severity([{}, {}, {}]) == "critical"
        assert detector._calculate_severity([{}]) == "medium"
        assert detector._calculate_severity([]) == "low"
