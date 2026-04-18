"""Tests for link predictor."""
from src.adapters.ai.link_predictor import LinkPredictor


class TestLinkPredictor:
    def test_predict_compatible_types(self) -> None:
        predictor = LinkPredictor()
        nodes = [
            {"id": "1", "type": "person", "data": {"sources": ["maigret"]}},
            {"id": "2", "type": "email", "data": {"sources": ["maigret"]}},
        ]
        edges: list[dict[str, str]] = []
        predictions = predictor.predict_links(nodes, edges)
        assert len(predictions) >= 1
        assert predictions[0]["predicted_type"] == "owns"

    def test_no_predictions_for_empty(self) -> None:
        predictor = LinkPredictor()
        assert predictor.predict_links([], []) == []

    def test_no_duplicate_predictions(self) -> None:
        predictor = LinkPredictor()
        nodes = [
            {"id": "1", "type": "person", "data": {}},
            {"id": "2", "type": "email", "data": {}},
        ]
        edges = [{"source": "1", "target": "2"}]
        predictions = predictor.predict_links(nodes, edges)
        # Should not predict existing edge
        assert all(p["source"] != "1" or p["target"] != "2" for p in predictions)

    def test_predict_edge_type(self) -> None:
        predictor = LinkPredictor()
        assert predictor._predict_edge_type({"type": "domain"}, {"type": "ip"}) == "registered_to"
        assert predictor._predict_edge_type({"type": "person"}, {"type": "username"}) == "uses"
