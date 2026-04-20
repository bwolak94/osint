"""Tests for Telegram scanner."""

from unittest.mock import AsyncMock, MagicMock, patch

from src.core.domain.entities.types import ScanInputType, ScanStatus


def _mock_httpx_client(response_data, status_code=200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = str(response_data)
    mock_resp.url = "https://t.me/test"
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestTelegramScanner:
    async def test_telegram_found(self):
        from src.adapters.scanners.telegram_scanner import TelegramScanner

        scanner = TelegramScanner()
        mock = _mock_httpx_client(
            '<div class="tgme_page_title"><span>Test Channel</span></div>'
        )
        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("testuser", ScanInputType.USERNAME)
        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True

    async def test_telegram_supports_username(self):
        from src.adapters.scanners.telegram_scanner import TelegramScanner

        scanner = TelegramScanner()
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_telegram_not_found(self):
        from src.adapters.scanners.telegram_scanner import TelegramScanner

        scanner = TelegramScanner()
        mock = _mock_httpx_client("Not Found", status_code=404)
        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("nonexistent", ScanInputType.USERNAME)
        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False
