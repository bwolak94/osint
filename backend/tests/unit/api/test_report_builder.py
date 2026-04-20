"""Tests for report builder endpoints."""
import pytest
from unittest.mock import MagicMock


class TestReportBuilderEndpoints:
    async def test_list_sections(self):
        from src.api.v1.report_builder import list_available_sections
        mock_user = MagicMock()
        result = await list_available_sections(current_user=mock_user)
        assert len(result["sections"]) >= 5

    async def test_list_templates_empty(self):
        from src.api.v1.report_builder import list_report_templates
        mock_user = MagicMock()
        result = await list_report_templates(current_user=mock_user)
        assert result.templates == []

    async def test_create_report_template(self):
        from src.api.v1.report_builder import create_report_template, ReportTemplateCreate
        mock_user = MagicMock()
        body = ReportTemplateCreate(name="My Template", description="Custom layout")
        result = await create_report_template(body=body, current_user=mock_user)
        assert result.name == "My Template"
        assert len(result.sections) >= 5

    async def test_build_report(self):
        from src.api.v1.report_builder import build_report, ReportBuildRequest
        mock_user = MagicMock()
        body = ReportBuildRequest(investigation_id="inv-1", format="html")
        result = await build_report(body=body, current_user=mock_user)
        assert result.status == "building"
        assert result.format == "html"
