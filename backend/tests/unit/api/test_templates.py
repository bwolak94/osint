"""Tests for template marketplace endpoints."""

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException


class TestTemplateEndpoints:
    async def test_list_templates_returns_builtins(self):
        from src.api.v1.templates import list_templates
        mock_user = MagicMock()
        result = await list_templates(category=None, search=None, current_user=mock_user)
        assert result.total >= 5
        assert len(result.categories) >= 3

    async def test_list_templates_filter_by_category(self):
        from src.api.v1.templates import list_templates
        mock_user = MagicMock()
        result = await list_templates(category="email", search=None, current_user=mock_user)
        assert all(t.category == "email" for t in result.templates)

    async def test_list_templates_search(self):
        from src.api.v1.templates import list_templates
        mock_user = MagicMock()
        result = await list_templates(category=None, search="domain", current_user=mock_user)
        assert result.total >= 1

    async def test_create_template(self):
        from src.api.v1.templates import create_template, TemplateCreate
        mock_user = MagicMock()
        mock_user.id = "user-1"
        body = TemplateCreate(
            name="My Custom Template",
            category="custom",
            scanner_config=["holehe"],
        )
        result = await create_template(body=body, current_user=mock_user)
        assert result.name == "My Custom Template"
        assert result.usage_count == 0

    async def test_get_template_found(self):
        from src.api.v1.templates import get_template
        mock_user = MagicMock()
        result = await get_template(template_id="tpl-email-deep-scan", current_user=mock_user)
        assert result.name == "Email Deep Investigation"

    async def test_get_template_not_found(self):
        from src.api.v1.templates import get_template
        mock_user = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_template(template_id="nonexistent", current_user=mock_user)
        assert exc_info.value.status_code == 404
