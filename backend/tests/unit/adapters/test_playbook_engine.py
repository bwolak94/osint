"""Tests for the playbook condition evaluator."""

import pytest
from src.adapters.playbook_engine import ConditionEvaluator


class TestConditionEvaluator:
    def test_eq_operator(self):
        assert ConditionEvaluator.evaluate("result", "status", "eq", "success", {"status": "success"})
        assert not ConditionEvaluator.evaluate("result", "status", "eq", "failed", {"status": "success"})

    def test_gt_operator(self):
        assert ConditionEvaluator.evaluate("result", "count", "gt", "5", {"count": 10})
        assert not ConditionEvaluator.evaluate("result", "count", "gt", "15", {"count": 10})

    def test_contains_operator(self):
        assert ConditionEvaluator.evaluate("result", "data", "contains", "found", {"data": "entity found here"})
        assert not ConditionEvaluator.evaluate("result", "data", "contains", "missing", {"data": "entity found"})

    def test_exists_operator(self):
        assert ConditionEvaluator.evaluate("result", "field", "exists", "", {"field": "value"})
        assert not ConditionEvaluator.evaluate("result", "missing", "exists", "", {"field": "value"})

    def test_nested_field_path(self):
        data = {"raw_data": {"ports": [80, 443], "status": "open"}}
        assert ConditionEvaluator.evaluate("result", "raw_data.status", "eq", "open", data)

    def test_count_gt_operator(self):
        data = {"ports": [80, 443, 8080]}
        assert ConditionEvaluator.evaluate("result", "ports", "count_gt", "2", data)
        assert not ConditionEvaluator.evaluate("result", "ports", "count_gt", "5", data)

    def test_evaluate_conditions_returns_then_step(self):
        conditions = [
            {"condition_type": "result", "field_path": "found", "operator": "eq", "expected_value": "True", "then_goto_step": 3, "else_goto_step": 5}
        ]
        result = ConditionEvaluator.evaluate_conditions(conditions, {"found": "True"})
        assert result == 3

    def test_evaluate_conditions_returns_else_step(self):
        conditions = [
            {"condition_type": "result", "field_path": "found", "operator": "eq", "expected_value": "True", "then_goto_step": 3, "else_goto_step": 5}
        ]
        result = ConditionEvaluator.evaluate_conditions(conditions, {"found": "False"})
        assert result == 5

    def test_evaluate_conditions_returns_none_when_no_routing(self):
        conditions = [
            {"condition_type": "result", "field_path": "x", "operator": "eq", "expected_value": "y"}
        ]
        result = ConditionEvaluator.evaluate_conditions(conditions, {"x": "z"})
        assert result is None

    def test_unknown_operator_returns_false(self):
        assert not ConditionEvaluator.evaluate("result", "field", "unknown_op", "", {"field": "value"})
