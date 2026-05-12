"""Probe engine — executes ProbeTemplates against HTTP targets.

Responsibilities:
- Build the full URL for each ProbeRequest
- Execute the HTTP request with timeout and redirect handling
- Apply matcher chain (AND across matchers unless template overrides)
- Run extractors on matching responses
- Return structured ProbeResult objects

Deliberately has no knowledge of OSINT infrastructure — it works with
pure URLs and returns pure dataclass results.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from src.adapters.scanners.probe_template import (
    Extractor,
    HeaderExtractor,
    Matcher,
    MatcherCondition,
    ProbeRequest,
    ProbeTemplate,
    RegexExtractor,
    Severity,
)

log = structlog.get_logger(__name__)

_REQUEST_TIMEOUT = 10          # seconds per HTTP request
_BODY_READ_LIMIT = 32_768      # 32 KB cap on response body
_DEFAULT_CONCURRENCY = 20      # max simultaneous requests across all templates
_USER_AGENT = (
    "Mozilla/5.0 (compatible; OSINTPlatform-Probe/1.0; +https://github.com/osint)"
)


@dataclass
class ProbeResult:
    """A confirmed finding from a single template execution."""

    template_id: str
    name: str
    severity: Severity
    category: str
    description: str
    matched_at: str          # full URL that triggered the match
    evidence: str            # snippet of the matching content (truncated)
    extracted: dict[str, str]  # extractor name → value
    request_ms: int
    remediation: str
    references: tuple[str, ...]
    cvss_score: float | None
    tags: tuple[str, ...]


@dataclass
class ProbeEngineResult:
    """Aggregate output of running all templates against a single target."""

    target_url: str
    findings: list[ProbeResult] = field(default_factory=list)
    total_templates: int = 0
    elapsed_ms: int = 0
    errors: list[str] = field(default_factory=list)

    # Convenience groupings
    def by_severity(self, severity: Severity) -> list[ProbeResult]:
        return [f for f in self.findings if f.severity == severity]

    @property
    def critical(self) -> list[ProbeResult]:
        return self.by_severity(Severity.CRITICAL)

    @property
    def high(self) -> list[ProbeResult]:
        return self.by_severity(Severity.HIGH)

    @property
    def medium(self) -> list[ProbeResult]:
        return self.by_severity(Severity.MEDIUM)


class ProbeEngine:
    """Stateless executor for ProbeTemplates.

    Usage::

        engine = ProbeEngine(concurrency=15)
        result = await engine.run_all(templates, "https://example.com")
    """

    def __init__(self, concurrency: int = _DEFAULT_CONCURRENCY) -> None:
        self._sem = asyncio.Semaphore(concurrency)

    async def run_all(
        self,
        templates: list[ProbeTemplate],
        target_url: str,
    ) -> ProbeEngineResult:
        """Run all templates concurrently against target_url."""
        result = ProbeEngineResult(target_url=target_url, total_templates=len(templates))
        t0 = time.monotonic()

        tasks = [self._run_template(t, target_url) for t in templates]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        for outcome in outcomes:
            if isinstance(outcome, Exception):
                result.errors.append(str(outcome))
            elif isinstance(outcome, ProbeResult):
                result.findings.append(outcome)

        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        log.debug(
            "probe_engine_done",
            target=target_url,
            findings=len(result.findings),
            templates=len(templates),
            elapsed_ms=result.elapsed_ms,
        )
        return result

    async def _run_template(
        self,
        template: ProbeTemplate,
        target_url: str,
    ) -> ProbeResult | None:
        """Execute all requests in a template; return a finding if any matches."""
        async with self._sem:
            for probe_req in template.requests:
                finding = await self._execute_request(template, probe_req, target_url)
                if finding is not None:
                    return finding
        return None

    async def _execute_request(
        self,
        template: ProbeTemplate,
        probe_req: ProbeRequest,
        target_url: str,
    ) -> ProbeResult | None:
        full_url = _build_url(target_url, probe_req.path)
        extra_headers = dict(probe_req.headers)
        t0 = time.monotonic()

        try:
            async with httpx.AsyncClient(
                timeout=_REQUEST_TIMEOUT,
                follow_redirects=probe_req.follow_redirects,
                verify=False,  # noqa: S501 — probe scanner checks for TLS issues separately
                headers={"User-Agent": _USER_AGENT, **extra_headers},
            ) as client:
                resp = await client.request(
                    method=probe_req.method,
                    url=full_url,
                    content=probe_req.body,
                )
                body = (await resp.aread())[:_BODY_READ_LIMIT].decode(errors="replace")
                response_ms = int((time.monotonic() - t0) * 1000)

            headers_dict = dict(resp.headers)
            final_url = str(resp.url)
            status = resp.status_code

        except Exception as exc:
            log.debug("probe_request_error", template=template.id, url=full_url, error=str(exc))
            return None

        # Evaluate matchers
        if not self._evaluate_matchers(
            probe_req.matchers,
            probe_req.matcher_condition,
            status=status,
            body=body,
            headers=headers_dict,
            url=final_url,
        ):
            return None

        # We have a match — run extractors
        extracted = self._run_extractors(probe_req.extractors, body=body, headers=headers_dict, url=final_url)
        evidence = _build_evidence(body, probe_req.matchers)

        return ProbeResult(
            template_id=template.id,
            name=template.name,
            severity=template.severity,
            category=template.category,
            description=template.description,
            matched_at=full_url,
            evidence=evidence,
            extracted=extracted,
            request_ms=response_ms,
            remediation=template.remediation,
            references=template.references,
            cvss_score=template.cvss_score,
            tags=template.tags,
        )

    # ── Matcher evaluation ────────────────────────────────────────────────────

    @staticmethod
    def _evaluate_matchers(
        matchers: tuple[Matcher, ...],
        condition: MatcherCondition,
        *,
        status: int,
        body: str,
        headers: dict[str, str],
        url: str,
    ) -> bool:
        if not matchers:
            return False
        ctx = {"status": status, "body": body, "headers": headers, "url": url}
        results = [m.match(**ctx) for m in matchers]
        if condition == MatcherCondition.AND:
            return all(results)
        return any(results)

    # ── Extractor execution ───────────────────────────────────────────────────

    @staticmethod
    def _run_extractors(
        extractors: tuple[Extractor, ...],
        *,
        body: str,
        headers: dict[str, str],
        url: str,
    ) -> dict[str, str]:
        out: dict[str, str] = {}
        for ext in extractors:
            value = ext.extract(body=body, headers=headers, url=url)
            if value is not None:
                out[ext.name] = value
        return out


# ── URL helpers ───────────────────────────────────────────────────────────────

def _build_url(base: str, path: str) -> str:
    """Join base URL and path, normalising slashes."""
    base = base.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _build_evidence(body: str, matchers: tuple[Matcher, ...]) -> str:
    """Return a short snippet of matching evidence for reporting."""
    from src.adapters.scanners.probe_template import WordMatcher, RegexMatcher
    for m in matchers:
        if isinstance(m, WordMatcher):
            for word in m.words:
                idx = body.lower().find(word.lower())
                if idx >= 0:
                    start = max(0, idx - 40)
                    end = min(len(body), idx + len(word) + 40)
                    return f"...{body[start:end].strip()}..."
        if isinstance(m, RegexMatcher):
            import re
            match = re.search(m.pattern, body, re.IGNORECASE | re.DOTALL)
            if match:
                span = match.group(0)
                return span[:120]
    return body[:200] if body else ""
