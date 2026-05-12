"""Web technology fingerprinting probe templates.

Identifies what technology stack a target is running. Useful for OSINT
investigations to build context and identify version-specific known issues.
These are purely passive detection — no modification attempts.
"""

from src.adapters.scanners.probe_template import (
    HeaderExtractor,
    MatcherCondition,
    MatcherPart,
    ProbeRequest,
    ProbeTemplate,
    RegexExtractor,
    Severity,
    StatusMatcher,
    WordMatcher,
)

TEMPLATES: list[ProbeTemplate] = [
    ProbeTemplate(
        id="tech-wordpress",
        name="WordPress CMS Detected",
        description="The target appears to be running WordPress. Consider checking for plugin vulnerabilities.",
        severity=Severity.INFO,
        category="web-tech",
        tags=("wordpress", "cms", "fingerprint"),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200, 301, 302)),
                    WordMatcher(words=("wp-content/", "wp-includes/", "WordPress")),
                ),
                matcher_condition=MatcherCondition.AND,
                extractors=(
                    RegexExtractor(
                        name="wp_version",
                        pattern=r'<meta name="generator" content="WordPress (?P<value>[^"]+)"',
                    ),
                ),
            ),
        ),
    ),
    ProbeTemplate(
        id="tech-drupal",
        name="Drupal CMS Detected",
        description="The target appears to be running Drupal.",
        severity=Severity.INFO,
        category="web-tech",
        tags=("drupal", "cms", "fingerprint"),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("Drupal", "sites/default/files", "drupal.js")),
                ),
                matcher_condition=MatcherCondition.AND,
                extractors=(
                    RegexExtractor(
                        name="drupal_version",
                        pattern=r'Drupal (?P<value>\d[\d.]+)',
                    ),
                ),
            ),
        ),
    ),
    ProbeTemplate(
        id="tech-joomla",
        name="Joomla CMS Detected",
        description="The target appears to be running Joomla.",
        severity=Severity.INFO,
        category="web-tech",
        tags=("joomla", "cms", "fingerprint"),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("Joomla!", "/components/com_", "mosConfig")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="tech-laravel",
        name="Laravel Framework Detected",
        description="The target appears to run on the Laravel PHP framework.",
        severity=Severity.INFO,
        category="web-tech",
        tags=("laravel", "php", "fingerprint"),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200, 500)),
                    WordMatcher(words=("laravel_session", "XSRF-TOKEN", "Laravel")),
                ),
                matcher_condition=MatcherCondition.AND,
                extractors=(
                    HeaderExtractor(name="laravel_session_cookie", header_name="Set-Cookie"),
                ),
            ),
        ),
    ),
    ProbeTemplate(
        id="tech-django",
        name="Django Framework Detected",
        description="The target appears to run on the Django Python framework.",
        severity=Severity.INFO,
        category="web-tech",
        tags=("django", "python", "fingerprint"),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200, 403)),
                    WordMatcher(words=("csrfmiddlewaretoken", "Django", "django")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="tech-rails",
        name="Ruby on Rails Framework Detected",
        description="The target appears to run on Ruby on Rails.",
        severity=Severity.INFO,
        category="web-tech",
        tags=("rails", "ruby", "fingerprint"),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("authenticity_token", "_rails_session")),
                ),
                matcher_condition=MatcherCondition.AND,
                extractors=(
                    HeaderExtractor(name="x_powered_by", header_name="X-Powered-By"),
                ),
            ),
        ),
    ),
    ProbeTemplate(
        id="tech-next-js",
        name="Next.js Framework Detected",
        description="The target is built with Next.js (React SSR framework).",
        severity=Severity.INFO,
        category="web-tech",
        tags=("nextjs", "react", "javascript", "fingerprint"),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("__NEXT_DATA__", "_next/static", "next/dist")),
                ),
                matcher_condition=MatcherCondition.AND,
                extractors=(
                    RegexExtractor(
                        name="next_build_id",
                        pattern=r'"buildId":"(?P<value>[^"]+)"',
                    ),
                ),
            ),
        ),
    ),
    ProbeTemplate(
        id="tech-nginx",
        name="Nginx Web Server Detected",
        description="Server response indicates Nginx is the web server.",
        severity=Severity.INFO,
        category="web-tech",
        tags=("nginx", "server", "fingerprint"),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200, 301, 302, 403, 404)),
                    WordMatcher(words=("nginx",), part=MatcherPart.HEADER),
                ),
                matcher_condition=MatcherCondition.AND,
                extractors=(
                    HeaderExtractor(name="server_header", header_name="Server"),
                ),
            ),
        ),
    ),
    ProbeTemplate(
        id="tech-apache",
        name="Apache Web Server Detected",
        description="Server response indicates Apache is the web server.",
        severity=Severity.INFO,
        category="web-tech",
        tags=("apache", "server", "fingerprint"),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200, 301, 302, 403, 404)),
                    WordMatcher(words=("apache",), part=MatcherPart.HEADER),
                ),
                matcher_condition=MatcherCondition.AND,
                extractors=(
                    HeaderExtractor(name="server_header", header_name="Server"),
                ),
            ),
        ),
    ),
    ProbeTemplate(
        id="tech-cloudflare",
        name="Cloudflare CDN Detected",
        description="The target is behind Cloudflare. Consider checking for origin IP exposure.",
        severity=Severity.INFO,
        category="web-tech",
        tags=("cloudflare", "cdn", "fingerprint"),
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200, 301, 302, 403, 404, 429, 503)),
                    WordMatcher(words=("cloudflare", "__cfduid", "cf-ray"), part=MatcherPart.HEADER),
                ),
                matcher_condition=MatcherCondition.AND,
                extractors=(
                    HeaderExtractor(name="cf_ray", header_name="CF-RAY"),
                ),
            ),
        ),
    ),
    ProbeTemplate(
        id="tech-graphql",
        name="GraphQL Endpoint Detected",
        description=(
            "A GraphQL endpoint is accessible. "
            "If introspection is enabled, the full schema can be enumerated."
        ),
        severity=Severity.INFO,
        category="web-tech",
        tags=("graphql", "api", "fingerprint"),
        requests=(
            ProbeRequest(
                method="POST",
                path="/graphql",
                headers=(("Content-Type", "application/json"),),
                body='{"query":"{__typename}"}',
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("__typename", "data")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="tech-graphql-introspection",
        name="GraphQL Introspection Enabled",
        description=(
            "GraphQL introspection is enabled in production. "
            "Attackers can enumerate the full API schema, types, and queries."
        ),
        severity=Severity.MEDIUM,
        category="web-tech",
        tags=("graphql", "api", "disclosure"),
        cvss_score=5.3,
        remediation="Disable introspection in production GraphQL deployments.",
        requests=(
            ProbeRequest(
                method="POST",
                path="/graphql",
                headers=(("Content-Type", "application/json"),),
                body='{"query":"{__schema{queryType{name}}}"}',
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("__schema", "queryType")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
]
