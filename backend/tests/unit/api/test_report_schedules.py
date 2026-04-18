"""Tests for report schedule endpoints."""
import pytest
from unittest.mock import MagicMock


class TestReportScheduleEndpoints:
    async def test_list_schedules_empty(self):
        from src.api.v1.report_schedules import list_report_schedules
        mock_user = MagicMock()
        result = await list_report_schedules(current_user=mock_user)
        assert result.schedules == []

    async def test_create_schedule(self):
        from src.api.v1.report_schedules import create_report_schedule, ReportScheduleCreate
        mock_user = MagicMock()
        body = ReportScheduleCreate(name="Weekly Report", recipients=["team@example.com"])
        result = await create_report_schedule(body=body, current_user=mock_user)
        assert result.name == "Weekly Report"
        assert result.is_active is True

    async def test_delete_schedule(self):
        from src.api.v1.report_schedules import delete_report_schedule
        mock_user = MagicMock()
        result = await delete_report_schedule(schedule_id="s-1", current_user=mock_user)
        assert result["status"] == "deleted"

    async def test_send_now(self):
        from src.api.v1.report_schedules import send_report_now
        mock_user = MagicMock()
        result = await send_report_now(schedule_id="s-1", current_user=mock_user)
        assert result["status"] == "sending"
