"""Playbook condition evaluator for branching logic."""

from typing import Any

import structlog

log = structlog.get_logger()


class ConditionEvaluator:
    """Evaluates playbook conditions against scan results."""

    OPERATORS = {
        "eq": lambda a, b: str(a) == str(b),
        "ne": lambda a, b: str(a) != str(b),
        "gt": lambda a, b: float(a) > float(b),
        "lt": lambda a, b: float(a) < float(b),
        "gte": lambda a, b: float(a) >= float(b),
        "lte": lambda a, b: float(a) <= float(b),
        "contains": lambda a, b: str(b) in str(a),
        "not_contains": lambda a, b: str(b) not in str(a),
        "exists": lambda a, _: a is not None,
        "not_exists": lambda a, _: a is None,
        "in": lambda a, b: str(a) in str(b).split(","),
        "count_gt": lambda a, b: len(a) > int(b) if isinstance(a, (list, dict)) else False,
        "count_lt": lambda a, b: len(a) < int(b) if isinstance(a, (list, dict)) else False,
    }

    @classmethod
    def evaluate(
        cls,
        condition_type: str,
        field_path: str,
        operator: str,
        expected_value: str,
        scan_result: dict[str, Any],
    ) -> bool:
        """Evaluate a single condition against scan result data."""
        try:
            actual_value = cls._resolve_field_path(scan_result, field_path)
            op_func = cls.OPERATORS.get(operator)
            if op_func is None:
                log.warning("Unknown operator", operator=operator)
                return False
            return op_func(actual_value, expected_value)
        except (ValueError, TypeError, KeyError) as e:
            log.warning("Condition evaluation failed", error=str(e), field_path=field_path)
            return False

    @classmethod
    def evaluate_conditions(
        cls,
        conditions: list[dict[str, Any]],
        scan_result: dict[str, Any],
    ) -> int | None:
        """Evaluate a list of conditions and return the next step index.

        Returns then_goto_step for the first matching condition,
        or else_goto_step of the last condition if none match,
        or None if no routing is specified.
        """
        for condition in conditions:
            result = cls.evaluate(
                condition_type=condition.get("condition_type", ""),
                field_path=condition.get("field_path", ""),
                operator=condition.get("operator", "eq"),
                expected_value=condition.get("expected_value", ""),
                scan_result=scan_result,
            )
            if result and condition.get("then_goto_step") is not None:
                return condition["then_goto_step"]
            if not result and condition.get("else_goto_step") is not None:
                return condition["else_goto_step"]

        return None

    @staticmethod
    def _resolve_field_path(data: dict[str, Any], path: str) -> Any:
        """Resolve a dot-separated field path in nested dict data."""
        current = data
        for key in path.split("."):
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                try:
                    current = current[int(key)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current
