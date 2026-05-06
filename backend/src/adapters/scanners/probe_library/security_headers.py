"""Security-header probe templates.

Checks for missing or misconfigured HTTP security headers.
These are detection-only: no payloads, no side effects.
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
        id="missing-csp",
        name="Missing Content-Security-Policy Header",
        description=(
            "The Content-Security-Policy header is not present. "
            "Without CSP, the page is vulnerable to cross-site scripting (XSS) injection."
        ),
        severity=Severity.MEDIUM,
        category="security-headers",
        tags=("csp", "xss", "headers"),
        cvss_score=6.1,
        remediation=(
            "Add a strict Content-Security-Policy header. "
            "Start with 'default-src \\'self\\'' and tighten as needed."
        ),
        references=("https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP",),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    HeaderMatcher(header_name="Content-Security-Policy", present=False),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="missing-hsts",
        name="Missing Strict-Transport-Security Header",
        description=(
            "The Strict-Transport-Security (HSTS) header is absent. "
            "This allows downgrade attacks and cookie theft over HTTP."
        ),
        severity=Severity.MEDIUM,
        category="security-headers",
        tags=("hsts", "tls", "headers"),
        cvss_score=5.9,
        remediation=(
            "Add: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload"
        ),
        references=("https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security",),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    HeaderMatcher(header_name="Strict-Transport-Security", present=False),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="missing-x-frame-options",
        name="Missing X-Frame-Options Header",
        description=(
            "The X-Frame-Options header is not set. "
            "The page may be embeddable in iframes, enabling clickjacking attacks."
        ),
        severity=Severity.LOW,
        category="security-headers",
        tags=("clickjacking", "x-frame-options", "headers"),
        cvss_score=4.3,
        remediation="Add: X-Frame-Options: DENY (or SAMEORIGIN if embedding is intentional).",
        references=("https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options",),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    HeaderMatcher(header_name="X-Frame-Options", present=False),
                    HeaderMatcher(header_name="Content-Security-Policy", contains="frame-ancestors", negative=True),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="missing-x-content-type-options",
        name="Missing X-Content-Type-Options Header",
        description=(
            "X-Content-Type-Options: nosniff is not set. "
            "Browsers may MIME-sniff responses, potentially executing non-script content as scripts."
        ),
        severity=Severity.LOW,
        category="security-headers",
        tags=("mime-sniff", "headers"),
        cvss_score=3.7,
        remediation="Add: X-Content-Type-Options: nosniff",
        references=("https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options",),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    HeaderMatcher(header_name="X-Content-Type-Options", present=False),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="missing-referrer-policy",
        name="Missing Referrer-Policy Header",
        description=(
            "No Referrer-Policy header found. "
            "By default, browsers may send the full URL as Referer to third parties."
        ),
        severity=Severity.INFO,
        category="security-headers",
        tags=("privacy", "referrer", "headers"),
        remediation="Add: Referrer-Policy: strict-origin-when-cross-origin",
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    HeaderMatcher(header_name="Referrer-Policy", present=False),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="server-header-disclosure",
        name="Server Version Disclosure via Header",
        description=(
            "The Server response header reveals the web-server software and version. "
            "Attackers use this to target version-specific vulnerabilities."
        ),
        severity=Severity.INFO,
        category="security-headers",
        tags=("disclosure", "fingerprint", "headers"),
        remediation="Configure the web server to suppress or genericise the Server header.",
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200, 301, 302, 403, 404)),
                    WordMatcher(
                        words=("apache/", "nginx/", "iis/", "lighttpd/", "openresty/", "tomcat/", "jetty/"),
                        part=MatcherPart.HEADER,
                    ),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="cors-wildcard",
        name="CORS Wildcard Allow-Origin",
        description=(
            "The server responds with Access-Control-Allow-Origin: * "
            "This allows any origin to read cross-origin responses."
        ),
        severity=Severity.MEDIUM,
        category="security-headers",
        tags=("cors", "headers"),
        cvss_score=5.4,
        remediation="Restrict Access-Control-Allow-Origin to specific trusted origins.",
        references=("https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS",),
        requests=(
            ProbeRequest(
                path="/",
                headers=(("Origin", "https://evil.example.com"),),
                matchers=(
                    StatusMatcher(codes=(200,)),
                    HeaderMatcher(header_name="Access-Control-Allow-Origin", contains="*"),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
]
