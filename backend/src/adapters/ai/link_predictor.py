"""Graph link prediction for OSINT investigations."""
from typing import Any
import structlog

log = structlog.get_logger()


class LinkPredictor:
    """Predict likely connections between graph nodes using heuristics."""

    def predict_links(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Predict potential new edges based on node properties and graph structure."""
        if not nodes:
            return []

        predictions: list[dict[str, Any]] = []
        node_map = {n["id"]: n for n in nodes}
        existing_edges = {(e.get("source"), e.get("target")) for e in edges}
        existing_edges |= {(e.get("target"), e.get("source")) for e in edges}

        # Common neighbor heuristic
        adjacency: dict[str, set[str]] = {}
        for edge in edges:
            src, tgt = edge.get("source"), edge.get("target")
            if src and tgt:
                adjacency.setdefault(src, set()).add(tgt)
                adjacency.setdefault(tgt, set()).add(src)

        for i, n1 in enumerate(nodes):
            for n2 in nodes[i + 1 :]:
                if (n1["id"], n2["id"]) in existing_edges:
                    continue

                score = self._compute_link_score(n1, n2, adjacency, node_map)
                if score > 0.3:
                    predictions.append({
                        "source": n1["id"],
                        "target": n2["id"],
                        "score": round(score, 3),
                        "reason": self._explain_prediction(n1, n2, adjacency),
                        "predicted_type": self._predict_edge_type(n1, n2),
                    })

        predictions.sort(key=lambda p: p["score"], reverse=True)
        return predictions[:20]

    def _compute_link_score(
        self,
        n1: dict[str, Any],
        n2: dict[str, Any],
        adjacency: dict[str, set[str]],
        node_map: dict[str, Any],
    ) -> float:
        score = 0.0

        # Common neighbors (Jaccard similarity)
        neighbors1 = adjacency.get(n1["id"], set())
        neighbors2 = adjacency.get(n2["id"], set())
        if neighbors1 and neighbors2:
            common = neighbors1 & neighbors2
            union = neighbors1 | neighbors2
            if union:
                jaccard = len(common) / len(union)
                score += jaccard * 0.5

        # Same source scanner bonus
        sources1 = set(n1.get("data", {}).get("sources", []))
        sources2 = set(n2.get("data", {}).get("sources", []))
        if sources1 & sources2:
            score += 0.2

        # Type compatibility bonus
        compatible_pairs = {
            ("person", "email"),
            ("person", "phone"),
            ("person", "username"),
            ("domain", "ip"),
            ("company", "person"),
            ("email", "domain"),
        }
        t1, t2 = n1.get("type", ""), n2.get("type", "")
        if (t1, t2) in compatible_pairs or (t2, t1) in compatible_pairs:
            score += 0.3

        return min(score, 1.0)

    def _explain_prediction(
        self,
        n1: dict[str, Any],
        n2: dict[str, Any],
        adjacency: dict[str, set[str]],
    ) -> str:
        reasons: list[str] = []
        neighbors1 = adjacency.get(n1["id"], set())
        neighbors2 = adjacency.get(n2["id"], set())
        common = neighbors1 & neighbors2
        if common:
            reasons.append(f"{len(common)} common neighbor(s)")

        compatible_pairs = {
            ("person", "email"),
            ("person", "phone"),
            ("domain", "ip"),
        }
        t1, t2 = n1.get("type", ""), n2.get("type", "")
        if (t1, t2) in compatible_pairs or (t2, t1) in compatible_pairs:
            reasons.append("compatible entity types")

        return "; ".join(reasons) if reasons else "statistical similarity"

    def _predict_edge_type(self, n1: dict[str, Any], n2: dict[str, Any]) -> str:
        t1, t2 = n1.get("type", ""), n2.get("type", "")
        type_pairs = {
            ("person", "email"): "owns",
            ("person", "phone"): "owns",
            ("person", "username"): "uses",
            ("company", "person"): "employed_by",
            ("domain", "ip"): "registered_to",
            ("email", "domain"): "registered_to",
        }
        return type_pairs.get((t1, t2), type_pairs.get((t2, t1), "connected_to"))
