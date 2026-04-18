"""PDF investigation report generator.

Uses Playwright (headless Chromium) to:
  1. Optionally screenshot the live graph view from a URL.
  2. Render an HTML report template to a print-ready PDF.

Playwright is an optional dependency — if it is not installed the module
still imports cleanly; ``generate()`` will raise a clear RuntimeError
rather than an ImportError at call time.

Report structure:
  - Cover page  — classification banner, investigation name, analyst, date.
  - Executive summary — free-text section supplied by the caller.
  - Findings table    — scan results sorted by scanner name.
  - Graph image       — base64-embedded screenshot (if captured).
  - Appendix sections — any additional ReportSection objects passed in.

Usage::

    gen = PDFReportGenerator()
    pdf_bytes = await gen.generate(
        config=PDFReportConfig(
            title="Threat Actor Alpha — OSINT Report",
            investigation_name="Alpha Investigation",
            analyst_name="J. Smith",
            classification="TLP:AMBER",
        ),
        sections=[
            ReportSection(title="Executive Summary", content="<p>...</p>"),
        ],
        graph_screenshot_url="http://localhost:5173/investigations/abc/graph",
    )
    with open("report.pdf", "wb") as fh:
        fh.write(pdf_bytes)
"""

from __future__ import annotations

import base64
import html
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

log = structlog.get_logger()

# Guard Playwright import — the class can be instantiated even without it.
try:
    from playwright.async_api import async_playwright as _async_playwright  # type: ignore
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PLAYWRIGHT_AVAILABLE = False
    _async_playwright = None  # type: ignore


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ReportSection:
    """A single named section of the investigation report.

    ``content`` is raw HTML injected into the report body. Callers are
    responsible for sanitising any user-supplied text before passing it here.
    """

    title: str
    content: str  # HTML fragment


@dataclass
class PDFReportConfig:
    """Top-level metadata for the generated PDF."""

    title: str
    investigation_name: str
    analyst_name: str
    classification: str = "TLP:WHITE"
    include_graph_screenshot: bool = True
    include_raw_data: bool = False


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class PDFReportGenerator:
    """Generates formatted PDF investigation reports via Playwright.

    All rendering work happens inside async coroutines so this class is
    safe to use from FastAPI route handlers and Celery async tasks.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        config: PDFReportConfig,
        sections: list[ReportSection],
        graph_screenshot_url: str | None = None,
        output_path: str | None = None,
    ) -> bytes:
        """Render the investigation report to PDF bytes.

        Args:
            config:                 Report metadata and options.
            sections:               Ordered list of HTML content sections.
            graph_screenshot_url:   If set and ``config.include_graph_screenshot``
                                    is True, Playwright will screenshot this URL.
            output_path:            If provided, PDF bytes are also written to
                                    this file path.

        Returns:
            Raw PDF bytes.

        Raises:
            RuntimeError: If Playwright is not installed.
        """
        if not _PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright is required for PDF generation. "
                "Install it with: pip install playwright && playwright install chromium"
            )

        # --- Optionally capture graph screenshot ---
        graph_b64: str | None = None
        if config.include_graph_screenshot and graph_screenshot_url:
            try:
                graph_b64 = await self._capture_graph(graph_screenshot_url)
                log.info("Graph screenshot captured", url=graph_screenshot_url)
            except Exception as exc:
                log.warning("Graph screenshot failed — skipping", error=str(exc))

        # --- Build HTML ---
        html_content = self._build_html(config, sections, graph_b64)

        # --- Render to PDF ---
        pdf_bytes = await self._html_to_pdf(html_content)

        # --- Optional disk write ---
        if output_path:
            try:
                with open(output_path, "wb") as fh:
                    fh.write(pdf_bytes)
                log.info("PDF written to disk", path=output_path, bytes=len(pdf_bytes))
            except OSError as exc:
                log.error("PDF disk write failed", path=output_path, error=str(exc))

        log.info(
            "PDF report generated",
            investigation=config.investigation_name,
            classification=config.classification,
            sections=len(sections),
            bytes=len(pdf_bytes),
        )
        return pdf_bytes

    # ------------------------------------------------------------------
    # HTML construction
    # ------------------------------------------------------------------

    def _build_html(
        self,
        config: PDFReportConfig,
        sections: list[ReportSection],
        graph_b64: str | None,
    ) -> str:
        """Assemble the full HTML document for the report.

        Structure:
            <head> with embedded CSS
            Cover page
            Per-section <div class="section"> blocks
            Graph image page (if available)
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        cover_html = self._build_cover_html(config, now)
        sections_html = "\n".join(self._build_section_html(s) for s in sections)

        graph_html = ""
        if graph_b64:
            graph_html = f"""
            <div class="section page-break">
                <h2>Investigation Graph</h2>
                <img src="data:image/png;base64,{graph_b64}"
                     alt="Investigation graph"
                     style="max-width:100%; border:1px solid #ddd; border-radius:4px;" />
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html.escape(config.title)}</title>
    <style>
    {self._apply_css()}
    </style>
</head>
<body>
{cover_html}
{sections_html}
{graph_html}
</body>
</html>"""

    def _build_cover_html(self, config: PDFReportConfig, generated_at: str) -> str:
        """Build the full-page cover div."""
        classification_class = self._classification_css_class(config.classification)
        return f"""<div class="cover">
    <div class="classification {classification_class}">{html.escape(config.classification)}</div>
    <h1>{html.escape(config.title)}</h1>
    <p class="subtitle">{html.escape(config.investigation_name)}</p>
    <div class="cover-meta">
        <p><strong>Analyst:</strong> {html.escape(config.analyst_name)}</p>
        <p><strong>Generated:</strong> {html.escape(generated_at)}</p>
        <p><strong>Classification:</strong> {html.escape(config.classification)}</p>
    </div>
    <div class="classification-footer {classification_class}">{html.escape(config.classification)}</div>
</div>"""

    def _build_section_html(self, section: ReportSection) -> str:
        """Wrap a ReportSection in a styled div block."""
        return f"""<div class="section">
    <h2>{html.escape(section.title)}</h2>
    <div class="section-content">
        {section.content}
    </div>
</div>"""

    def _build_findings_table_html(self, scan_results: list[dict[str, Any]]) -> str:
        """Build an HTML table of scan findings sorted by scanner name.

        Args:
            scan_results: List of dicts with at minimum scanner_name, value,
                          type, and confidence keys.

        Returns:
            An HTML ``<table>`` string.
        """
        if not scan_results:
            return "<p><em>No scan results available.</em></p>"

        sorted_results = sorted(scan_results, key=lambda r: r.get("scanner_name", ""))

        rows = ""
        for result in sorted_results:
            scanner = html.escape(str(result.get("scanner_name", "")))
            value = html.escape(str(result.get("value", "")))
            entity_type = html.escape(str(result.get("type", "")))
            confidence = html.escape(str(result.get("confidence", "")))
            timestamp = html.escape(str(result.get("timestamp", "")))
            rows += f"""<tr>
                <td>{scanner}</td>
                <td><code>{entity_type}</code></td>
                <td>{value}</td>
                <td>{confidence}</td>
                <td>{timestamp}</td>
            </tr>\n"""

        return f"""<table>
    <thead>
        <tr>
            <th>Scanner</th>
            <th>Type</th>
            <th>Value</th>
            <th>Confidence</th>
            <th>Timestamp</th>
        </tr>
    </thead>
    <tbody>
        {rows}
    </tbody>
</table>"""

    # ------------------------------------------------------------------
    # Playwright helpers
    # ------------------------------------------------------------------

    async def _capture_graph(self, url: str) -> str | None:
        """Screenshot the graph view at ``url`` and return a base64 PNG.

        Waits for the network to be idle and for a ``#graph-container``
        element to appear, giving the React graph time to render.

        Returns:
            Base64-encoded PNG string, or None if capture fails.
        """
        async with _async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            try:
                page = await browser.new_page(viewport={"width": 1600, "height": 900})
                await page.goto(url, wait_until="networkidle", timeout=30_000)

                # Wait for the graph container (best-effort; don't abort if absent)
                try:
                    await page.wait_for_selector("#graph-container", timeout=10_000)
                except Exception:
                    log.debug("Graph container selector not found — screenshotting anyway")

                screenshot_bytes: bytes = await page.screenshot(full_page=False)
                return base64.b64encode(screenshot_bytes).decode("ascii")
            finally:
                await browser.close()

    async def _html_to_pdf(self, html_content: str) -> bytes:
        """Render an HTML string to PDF bytes via Playwright's print-to-PDF.

        Uses A4 paper with 15 mm margins, landscape for wide tables.
        Background graphics (colours, borders) are enabled so the dark
        cover page renders correctly.

        Returns:
            Raw PDF bytes.
        """
        async with _async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            try:
                page = await browser.new_page()
                await page.set_content(html_content, wait_until="networkidle")

                pdf_bytes: bytes = await page.pdf(
                    format="A4",
                    print_background=True,
                    margin={
                        "top": "15mm",
                        "right": "15mm",
                        "bottom": "15mm",
                        "left": "15mm",
                    },
                )
                return pdf_bytes
            finally:
                await browser.close()

    # ------------------------------------------------------------------
    # CSS
    # ------------------------------------------------------------------

    def _apply_css(self) -> str:
        """Return the embedded CSS for the professional report theme."""
        return """
        /* ---- Reset & Base ---- */
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            color: #1a1a2e;
            font-size: 11pt;
            line-height: 1.6;
        }

        /* ---- Cover page ---- */
        .cover {
            background: #1a1a2e;
            color: #ffffff;
            height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 60px;
            page-break-after: always;
            position: relative;
        }

        .cover h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            font-weight: 700;
            letter-spacing: -0.5px;
        }

        .cover .subtitle {
            font-size: 1.2rem;
            color: #a0aec0;
            margin-bottom: 2rem;
        }

        .cover-meta {
            border-top: 1px solid rgba(255,255,255,0.15);
            padding-top: 1.5rem;
            margin-top: 1rem;
            color: #cbd5e0;
            font-size: 0.9rem;
        }

        .cover-meta p { margin-bottom: 0.4rem; }

        /* ---- Classification banners ---- */
        .classification {
            font-size: 0.7rem;
            font-weight: bold;
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-bottom: 2rem;
        }

        .classification-footer {
            position: absolute;
            bottom: 30px;
            left: 60px;
            font-size: 0.7rem;
            font-weight: bold;
            letter-spacing: 3px;
            text-transform: uppercase;
        }

        .tlp-white  { color: #ffffff; }
        .tlp-green  { color: #38a169; }
        .tlp-amber  { color: #d69e2e; }
        .tlp-red    { color: #e53e3e; }

        /* ---- Sections ---- */
        .section {
            padding: 40px 60px;
            page-break-inside: avoid;
        }

        .section h2 {
            font-size: 1.4rem;
            color: #1a1a2e;
            border-bottom: 2px solid #1a1a2e;
            padding-bottom: 0.4rem;
            margin-bottom: 1.2rem;
        }

        .section-content { color: #2d3748; }

        .section-content p { margin-bottom: 0.8rem; }

        .page-break { page-break-before: always; }

        /* ---- Tables ---- */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 0.85rem;
        }

        th {
            background: #1a1a2e;
            color: #ffffff;
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
        }

        td {
            padding: 8px 12px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: top;
        }

        tr:nth-child(even) { background: #f7fafc; }
        tr:hover { background: #edf2f7; }

        code {
            background: #edf2f7;
            padding: 1px 5px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.8em;
        }

        /* ---- Print overrides ---- */
        @media print {
            .cover { height: 100vh; }
            .section { padding: 30px 50px; }
        }
        """

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classification_css_class(classification: str) -> str:
        """Map a TLP classification string to a CSS utility class."""
        upper = classification.upper()
        if "WHITE" in upper:
            return "tlp-white"
        if "GREEN" in upper:
            return "tlp-green"
        if "AMBER" in upper:
            return "tlp-amber"
        if "RED" in upper:
            return "tlp-red"
        return "tlp-white"
