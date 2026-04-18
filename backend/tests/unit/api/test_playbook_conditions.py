"""Tests for playbook condition endpoints."""

import pytest
from unittest.mock import MagicMock


class TestPlaybookConditionEndpoints:
    async def test_add_condition(self):
        from src.api.v1.playbook_conditions import add_condition, ConditionCreate

        mock_user = MagicMock()
        body = ConditionCreate(
            step_index=1,
            condition_type="result_check",
            field_path="raw_data.found",
            operator="eq",
            expected_value="True",
            then_goto_step=3,
        )
        result = await add_condition(playbook_id="pb-1", body=body, current_user=mock_user)
        assert result["status"] == "created"

    async def test_list_conditions(self):
        from src.api.v1.playbook_conditions import list_conditions

        mock_user = MagicMock()
        result = await list_conditions(playbook_id="pb-1", current_user=mock_user)
        assert result["conditions"] == []

    async def test_test_conditions(self):
        from src.api.v1.playbook_conditions import test_conditions, ConditionTestRequest

        mock_user = MagicMock()
        body = ConditionTestRequest(
            conditions=[
                {"condition_type": "result", "field_path": "status", "operator": "eq", "expected_value": "success", "then_goto_step": 2}
            ],
            scan_result={"status": "success"},
        )
        result = await test_conditions(body=body, current_user=mock_user)
        assert result.next_step == 2
        assert len(result.evaluations) == 1
