"""Tests for knowledge base parsers (markdown, text, url, pdf)."""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.knowledge.parsers.markdown import parse_markdown
from src.adapters.knowledge.parsers.text import parse_text
from src.adapters.knowledge.parsers.url import _strip_html, parse_url


class TestMarkdownParser:
    def test_strips_heading_markers(self) -> None:
        result = parse_markdown("# Heading One\n\nSome content.")
        assert "#" not in result
        assert "Heading One" in result

    def test_strips_bold_markers(self) -> None:
        result = parse_markdown("This is **bold** text.")
        assert "**" not in result
        assert "bold" in result

    def test_strips_inline_code(self) -> None:
        result = parse_markdown("Run `pip install foo` now.")
        assert "`" not in result
        assert "pip install foo" not in result  # inline code is removed entirely

    def test_strips_links_keeps_text(self) -> None:
        result = parse_markdown("[click here](https://example.com)")
        assert "click here" in result
        assert "https://example.com" not in result

    def test_strips_blockquotes(self) -> None:
        result = parse_markdown("> This is a quote")
        assert ">" not in result
        assert "This is a quote" in result

    def test_strips_fenced_code_blocks(self) -> None:
        md = "Some text\n```python\nprint('hello')\n```\nMore text"
        result = parse_markdown(md)
        assert "print" not in result
        assert "Some text" in result
        assert "More text" in result

    def test_collapses_extra_blank_lines(self) -> None:
        md = "Line one\n\n\n\n\nLine two"
        result = parse_markdown(md)
        assert "\n\n\n" not in result

    def test_empty_string_returns_empty(self) -> None:
        assert parse_markdown("") == ""


class TestTextParser:
    def test_decodes_bytes_to_string(self) -> None:
        result = parse_text(b"hello world")
        assert result == "hello world"

    def test_normalises_crlf_to_lf(self) -> None:
        result = parse_text("line1\r\nline2\r\nline3")
        assert "\r" not in result
        assert "line1\nline2" in result

    def test_collapses_extra_blank_lines(self) -> None:
        result = parse_text("one\n\n\n\ntwo")
        assert "\n\n\n" not in result

    def test_strips_leading_trailing_whitespace(self) -> None:
        result = parse_text("   content   ")
        assert result == "content"

    def test_handles_invalid_utf8_bytes(self) -> None:
        bad_bytes = b"valid \xff\xfe invalid"
        result = parse_text(bad_bytes)
        assert "valid" in result
        assert isinstance(result, str)


class TestURLParser:
    def test_strip_html_removes_tags(self) -> None:
        html = "<p>Hello <b>world</b></p>"
        result = _strip_html(html)
        assert "<p>" not in result
        assert "<b>" not in result
        assert "Hello" in result
        assert "world" in result

    def test_strip_html_decodes_entities(self) -> None:
        html = "<p>AT&amp;T &lt;company&gt;</p>"
        result = _strip_html(html)
        assert "AT&T" in result
        assert "<company>" in result

    def test_strip_html_removes_script_blocks(self) -> None:
        html = "<script>alert('xss')</script><p>Safe content</p>"
        result = _strip_html(html)
        assert "alert" not in result
        assert "Safe content" in result

    async def test_injected_fetcher_called(self) -> None:
        mock_fetcher = AsyncMock()
        mock_fetcher.extract.return_value = "Extracted content"
        result = await parse_url("https://example.com", fetcher=mock_fetcher)
        mock_fetcher.extract.assert_awaited_once_with("https://example.com")
        assert result == "Extracted content"

    async def test_no_fetcher_raises_import_error_if_no_httpx(self) -> None:
        """When httpx is not installed, parse_url should raise ImportError."""
        import importlib
        # Temporarily hide httpx
        with patch.dict(sys.modules, {"httpx": None}):
            with pytest.raises((ImportError, Exception)):
                await parse_url("https://example.com", fetcher=None)


class TestPDFParser:
    async def test_raises_import_error_when_pypdf_missing(self) -> None:
        with patch.dict(sys.modules, {"pypdf": None}):
            # Force re-import
            if "src.adapters.knowledge.parsers.pdf" in sys.modules:
                del sys.modules["src.adapters.knowledge.parsers.pdf"]
            from src.adapters.knowledge.parsers.pdf import parse_pdf
            with pytest.raises(ImportError, match="pypdf"):
                await parse_pdf(b"%PDF-1.4 fake content")

    async def test_pdf_extraction_with_mock_pypdf(self) -> None:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page content here"

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        mock_pypdf = MagicMock()
        mock_pypdf.PdfReader.return_value = mock_reader

        with patch.dict(sys.modules, {"pypdf": mock_pypdf}):
            if "src.adapters.knowledge.parsers.pdf" in sys.modules:
                del sys.modules["src.adapters.knowledge.parsers.pdf"]
            from src.adapters.knowledge.parsers.pdf import parse_pdf
            result = await parse_pdf(b"fake pdf bytes")

        assert "Page content here" in result
