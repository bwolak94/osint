"""TLS / certificate probe templates.

These perform HTTPS-level checks. The engine uses httpx which follows
redirects and validates TLS by default; these templates catch cases
where the engine is instructed to skip verification (verify=False)
and then surface cert issues independently.

Note: Full certificate chain inspection is done by the CertTransparency scanner.
These templates focus on HTTP-level TLS signals only.
"""

from src.adapters.scanners.probe_template import (
    HeaderMatcher,
    MatcherCondition,
    MatcherPart,
    ProbeRequest,
    ProbeTemplate,
    Severity,
    StatusMatcher,
    WordMatcher,
)

TEMPLATES: list[ProbeTemplate] = [
    ProbeTemplate(
        id="http-no-redirect-to-https",
        name="HTTP Does Not Redirect to HTTPS",
        description=(
            "The server accepts plain HTTP connections without redirecting to HTTPS. "
            "Credentials and cookies transmitted over HTTP are exposed to interception."
        ),
        severity=Severity.HIGH,
        category="tls",
        tags=("http", "tls", "transport"),
        cvss_score=7.4,
        remediation=(
            "Configure your web server or load balancer to redirect all HTTP (port 80) "
            "traffic to HTTPS (port 443) using a 301 redirect."
        ),
        references=("https://developer.mozilla.org/en-US/docs/Web/HTTP/Redirections",),
        requests=(
            ProbeRequest(
                # We probe the HTTP URL explicitly; engine handles this via http:// prefix
                path="/",
                follow_redirects=False,
                matchers=(
                    # Expecting a non-redirect response on HTTP = bad
                    StatusMatcher(codes=(200, 403, 404)),
                ),
                matcher_condition=MatcherCondition.OR,
            ),
        ),
    ),
    ProbeTemplate(
        id="hsts-max-age-short",
        name="HSTS max-age Too Short",
        description=(
            "The Strict-Transport-Security header is present but its max-age is less than 6 months. "
            "Short max-age allows downgrade attacks during the unprotected window."
        ),
        severity=Severity.LOW,
        category="tls",
        tags=("hsts", "tls", "headers"),
        cvss_score=3.7,
        remediation="Set HSTS max-age to at least 15768000 seconds (6 months). Recommended: 31536000.",
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    HeaderMatcher(header_name="Strict-Transport-Security", present=True),
                    # max-age below 6 months (15768000 ≈ 5 digits ≤ 5 chars before semicolon)
                    WordMatcher(
                        words=("max-age=0", "max-age=1", "max-age=2", "max-age=3",
                               "max-age=4", "max-age=5", "max-age=6", "max-age=7",
                               "max-age=8", "max-age=9"),
                        part=MatcherPart.HEADER,
                    ),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="mixed-content-http",
        name="Mixed Content — HTTP Resources on HTTPS Page",
        description=(
            "The HTTPS page loads resources (scripts, stylesheets) over plain HTTP. "
            "Mixed content downgrades security and is blocked by modern browsers."
        ),
        severity=Severity.MEDIUM,
        category="tls",
        tags=("mixed-content", "tls"),
        cvss_score=4.3,
        remediation="Update all resource URLs to use HTTPS or protocol-relative URLs.",
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(
                        words=("src=\"http://", "href=\"http://", "url(http://"),
                        condition=MatcherCondition.OR,
                    ),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
]
