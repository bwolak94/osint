"""ML-based anomaly detection for OSINT scan results."""
import math
from typing import Any
import structlog

log = structlog.get_logger()


class AnomalyDetector:
    """Detect anomalies in scan results using statistical methods."""

    def __init__(self) -> None:
        self._thresholds = {
            "port_count": 50,
            "vuln_count": 10,
            "breach_count": 5,
            "service_count": 30,
            "scan_duration_ms": 30000,
        }

    def detect_anomalies(self, scan_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Analyze scan results for anomalies."""
        anomalies = []
        for result in scan_results:
            result_anomalies = self._check_result(result)
            if result_anomalies:
                anomalies.append({
                    "scanner": result.get("scanner_name", "unknown"),
                    "input": result.get("input_value", ""),
                    "anomalies": result_anomalies,
                    "severity": self._calculate_severity(result_anomalies),
                })
        return anomalies

    def _check_result(self, result: dict[str, Any]) -> list[dict[str, str]]:
        anomalies: list[dict[str, str]] = []
        raw = result.get("raw_data", {})

        # Check for unusual port counts
        ports = raw.get("ports", [])
        if isinstance(ports, list) and len(ports) > self._thresholds["port_count"]:
            anomalies.append({
                "type": "high_port_count",
                "message": f"Unusually high number of open ports: {len(ports)}",
                "metric": str(len(ports)),
            })

        # Check for high vulnerability count
        vulns = raw.get("vulns", [])
        if isinstance(vulns, list) and len(vulns) > self._thresholds["vuln_count"]:
            anomalies.append({
                "type": "high_vuln_count",
                "message": f"High vulnerability count: {len(vulns)}",
                "metric": str(len(vulns)),
            })

        # Check for excessive breach exposure
        breaches = raw.get("registered_on", raw.get("breaches", []))
        if isinstance(breaches, list) and len(breaches) > self._thresholds["breach_count"]:
            anomalies.append({
                "type": "high_breach_exposure",
                "message": f"Found in {len(breaches)} breaches/services",
                "metric": str(len(breaches)),
            })

        # Check scan duration anomaly
        duration = result.get("duration_ms", 0)
        if duration > self._thresholds["scan_duration_ms"]:
            anomalies.append({
                "type": "slow_scan",
                "message": f"Scan took {duration}ms (threshold: {self._thresholds['scan_duration_ms']}ms)",
                "metric": str(duration),
            })

        # Check for suspicious patterns
        identifiers = result.get("extracted_identifiers", [])
        if isinstance(identifiers, list) and len(identifiers) > 100:
            anomalies.append({
                "type": "excessive_identifiers",
                "message": f"Unusually high identifier count: {len(identifiers)}",
                "metric": str(len(identifiers)),
            })

        return anomalies

    def _calculate_severity(self, anomalies: list[dict[str, str]]) -> str:
        count = len(anomalies)
        if count >= 3:
            return "critical"
        if count == 2:
            return "high"
        if count == 1:
            return "medium"
        return "low"

    def compute_risk_score(self, scan_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute an overall risk score from scan results."""
        if not scan_results:
            return {"score": 0.0, "level": "unknown", "factors": []}

        factors: list[dict[str, Any]] = []
        score = 0.0

        total_vulns = sum(
            len(r.get("raw_data", {}).get("vulns", []))
            for r in scan_results
            if isinstance(r.get("raw_data", {}).get("vulns"), list)
        )
        if total_vulns > 0:
            vuln_score = min(total_vulns * 5, 40)
            score += vuln_score
            factors.append({"factor": "vulnerabilities", "count": total_vulns, "contribution": vuln_score})

        total_breaches = sum(
            len(r.get("raw_data", {}).get("registered_on", r.get("raw_data", {}).get("breaches", [])))
            for r in scan_results
            if isinstance(
                r.get("raw_data", {}).get("registered_on", r.get("raw_data", {}).get("breaches")),
                list,
            )
        )
        if total_breaches > 0:
            breach_score = min(total_breaches * 8, 40)
            score += breach_score
            factors.append({"factor": "breach_exposure", "count": total_breaches, "contribution": breach_score})

        anomalies = self.detect_anomalies(scan_results)
        if anomalies:
            anomaly_score = min(len(anomalies) * 10, 20)
            score += anomaly_score
            factors.append({"factor": "anomalies", "count": len(anomalies), "contribution": anomaly_score})

        score = min(score, 100)
        level = (
            "critical" if score >= 75
            else "high" if score >= 50
            else "medium" if score >= 25
            else "low"
        )

        return {"score": round(score, 1), "level": level, "factors": factors}
