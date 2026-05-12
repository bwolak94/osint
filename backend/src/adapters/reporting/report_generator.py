"""Pentest report generator — produces HTML, Markdown, and PDF outputs."""

from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


class PentestReportGenerator:
    """Generates pentest reports from scan data and findings.

    Supported formats:
    - ``html`` — rendered Jinja2 HTML template
    - ``md``   — Markdown summary
    - ``pdf``  — wkhtmltopdf-rendered PDF from HTML (requires wkhtmltopdf in PATH)
    """

    async def generate(
        self,
        scan: Any,
        findings: list[Any],
        format: str = "pdf",
        language: str = "en",
    ) -> bytes:
        """Generate a report and return raw bytes.

        Args:
            scan: PentestScanModel instance (or None for stub).
            findings: List of PentestFindingModel instances.
            format: One of ``pdf``, ``html``, ``md``.
            language: ``en`` or ``pl``.

        Returns:
            Raw bytes of the generated report.
        """
        context = self._build_context(scan, findings, language)

        match format:
            case "html":
                return self._render_html(context).encode("utf-8")
            case "md":
                return self._render_markdown(context).encode("utf-8")
            case "pdf":
                html = self._render_html(context)
                return await self._render_pdf(html)
            case _:
                raise ValueError(f"Unsupported report format: {format!r}")

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    def _build_context(self, scan: Any, findings: list[Any], language: str) -> dict[str, Any]:
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

        sorted_findings = sorted(
            findings, key=lambda f: severity_order.get(f.severity or "info", 4)
        )

        severity_counts: dict[str, int] = {}
        for f in findings:
            sev = f.severity or "info"
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "scan": scan,
            "findings": sorted_findings,
            "severity_counts": severity_counts,
            "total_findings": len(findings),
            "language": language,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }

    # ------------------------------------------------------------------
    # HTML rendering via Jinja2
    # ------------------------------------------------------------------

    def _render_html(self, context: dict[str, Any]) -> str:
        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape

            env = Environment(
                loader=FileSystemLoader(str(TEMPLATES_DIR)),
                autoescape=select_autoescape(["html"]),
            )
            template = env.get_template("pentest_report.html")
            return template.render(**context)
        except Exception as exc:
            log.warning("jinja2_render_failed", error=str(exc))
            return self._fallback_html(context)

    def _fallback_html(self, context: dict[str, Any]) -> str:
        """Minimal HTML fallback when Jinja2 is unavailable."""
        findings_html = "".join(
            f"<li><strong>[{f.severity or 'info'}]</strong> {f.title}</li>"
            for f in context["findings"]
        )
        return (
            f"<html><body>"
            f"<h1>Pentest Report</h1>"
            f"<p>Generated: {context['generated_at']}</p>"
            f"<p>Total findings: {context['total_findings']}</p>"
            f"<ul>{findings_html}</ul>"
            f"</body></html>"
        )

    # ------------------------------------------------------------------
    # Markdown rendering
    # ------------------------------------------------------------------

    def _render_markdown(self, context: dict[str, Any]) -> str:
        lines = [
            "# Pentest Report",
            f"**Generated:** {context['generated_at']}",
            f"**Total Findings:** {context['total_findings']}",
            "",
            "## Findings Summary",
        ]
        for sev, count in sorted(context["severity_counts"].items()):
            lines.append(f"- {sev.upper()}: {count}")
        lines.append("")
        lines.append("## Detailed Findings")
        for i, f in enumerate(context["findings"], 1):
            lines += [
                f"### {i}. {f.title}",
                f"**Severity:** {f.severity or 'info'}  ",
                f"**Status:** {f.status}  ",
                f"**Tool:** {f.tool or 'unknown'}  ",
                "",
                f.description or "_No description provided._",
                "",
                f"**Remediation:** {f.remediation or '_Not specified._'}",
                "",
                "---",
                "",
            ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # PDF rendering via wkhtmltopdf
    # ------------------------------------------------------------------

    async def _render_pdf(self, html: str) -> bytes:
        """Render HTML to PDF using wkhtmltopdf subprocess."""
        import asyncio
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tf:
            tf.write(html)
            html_path = tf.name

        pdf_path = html_path.replace(".html", ".pdf")
        try:
            proc = await asyncio.create_subprocess_exec(
                "wkhtmltopdf",
                "--quiet",
                "--page-size", "A4",
                "--margin-top", "20mm",
                "--margin-bottom", "20mm",
                "--margin-left", "15mm",
                "--margin-right", "15mm",
                html_path,
                pdf_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    return f.read()
            else:
                # Fallback: return HTML as bytes if PDF fails
                await log.awarn("wkhtmltopdf_failed_returning_html")
                return html.encode("utf-8")
        finally:
            for p in (html_path, pdf_path):
                if os.path.exists(p):
                    os.unlink(p)
