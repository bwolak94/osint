"""Tests for mentions/notifications endpoints."""

import pytest
from unittest.mock import MagicMock


class TestMentionEndpoints:
    @pytest.mark.asyncio
    async def test_create_mention(self):
        from src.api.v1.mentions import create_mention, MentionCreate

        mock_user = MagicMock()
        mock_user.id = "author-1"

        body = MentionCreate(
            investigation_id="inv-1",
            mentioned_user_id="user-2",
            context_type="comment",
            context_id="comment-1",
            content_preview="Hey @user2, check this out",
        )
        result = await create_mention(body=body, current_user=mock_user)
        assert result.mentioned_user_id == "user-2"
        assert result.context_type == "comment"
        assert result.is_read is False

    @pytest.mark.asyncio
    async def test_list_notifications_empty(self):
        from src.api.v1.mentions import list_notifications

        mock_user = MagicMock()
        result = await list_notifications(current_user=mock_user)
        assert result.notifications == []
        assert result.unread_count == 0

    @pytest.mark.asyncio
    async def test_mark_notification_read(self):
        from src.api.v1.mentions import mark_notification_read

        mock_user = MagicMock()
        result = await mark_notification_read(notification_id="notif-1", current_user=mock_user)
        assert result["status"] == "read"

    @pytest.mark.asyncio
    async def test_mark_all_read(self):
        from src.api.v1.mentions import mark_all_notifications_read

        mock_user = MagicMock()
        result = await mark_all_notifications_read(current_user=mock_user)
        assert result["status"] == "all_read"
