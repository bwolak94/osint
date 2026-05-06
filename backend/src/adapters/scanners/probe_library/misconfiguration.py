"""Misconfiguration probe templates.

Detects web application misconfigurations: directory listing, admin panels,
information disclosure via error pages, and default installations.
"""

from src.adapters.scanners.probe_template import (
    HeaderMatcher,
    MatcherCondition,
    MatcherPart,
    ProbeRequest,
    ProbeTemplate,
    RegexMatcher,
    Severity,
    StatusMatcher,
    WordMatcher,
)

TEMPLATES: list[ProbeTemplate] = [
    ProbeTemplate(
        id="directory-listing",
        name="Directory Listing Enabled",
        description=(
            "The web server is configured to list directory contents when no index file is present. "
            "This discloses file structure and may reveal sensitive files."
        ),
        severity=Severity.MEDIUM,
        category="misconfiguration",
        tags=("directory-listing", "disclosure"),
        cvss_score=5.3,
        remediation="Disable directory listing in your web server configuration (Apache: Options -Indexes, Nginx: autoindex off).",
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("Index of /", "Directory listing for", "[PARENTDIR]", "Parent Directory")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="wordpress-admin-exposed",
        name="WordPress Admin Login Page Accessible",
        description=(
            "The WordPress admin login page (/wp-admin or /wp-login.php) is publicly accessible. "
            "Exposed admin pages are high-value brute-force targets."
        ),
        severity=Severity.LOW,
        category="misconfiguration",
        tags=("wordpress", "auth", "admin"),
        remediation="Restrict access to /wp-admin and /wp-login.php to trusted IP ranges.",
        requests=(
            ProbeRequest(
                path="/wp-login.php",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("WordPress", "wp-login", "Lost your password?")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="generic-admin-panel",
        name="Generic Admin Panel Accessible",
        description="An administrative panel path is reachable from the public internet.",
        severity=Severity.INFO,
        category="misconfiguration",
        tags=("admin", "panel"),
        remediation="Restrict admin paths to internal networks or require MFA.",
        requests=(
            ProbeRequest(
                path="/admin/",
                matchers=(StatusMatcher(codes=(200, 301, 302)),),
                matcher_condition=MatcherCondition.OR,
            ),
        ),
    ),
    ProbeTemplate(
        id="debug-mode-active",
        name="Application Debug Mode Active",
        description=(
            "The application appears to be running in debug mode. "
            "Debug pages expose stack traces, source code, environment variables, and internal paths."
        ),
        severity=Severity.HIGH,
        category="misconfiguration",
        tags=("debug", "disclosure", "django", "laravel"),
        cvss_score=7.5,
        remediation="Disable debug mode in production (DEBUG=False in Django, APP_DEBUG=false in Laravel).",
        requests=(
            ProbeRequest(
                path="/",
                matchers=(
                    StatusMatcher(codes=(500,)),
                    WordMatcher(
                        words=(
                            "Django Version", "Traceback (most recent call last)",
                            "Whoops! There was an error", "Application Traceback",
                            "Fatal error:", "Call to undefined function",
                        ),
                    ),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="phpmyadmin-exposed",
        name="phpMyAdmin Exposed",
        description=(
            "A phpMyAdmin database management interface is publicly accessible. "
            "This is a common target for automated attacks and credential stuffing."
        ),
        severity=Severity.HIGH,
        category="misconfiguration",
        tags=("phpmyadmin", "database", "admin"),
        cvss_score=7.3,
        remediation="Restrict phpMyAdmin access to localhost or a VPN.",
        requests=(
            ProbeRequest(
                path="/phpmyadmin/",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("phpMyAdmin", "Welcome to phpMyAdmin")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="grafana-exposed",
        name="Grafana Dashboard Exposed",
        description="A Grafana monitoring dashboard login page is publicly accessible.",
        severity=Severity.MEDIUM,
        category="misconfiguration",
        tags=("grafana", "monitoring", "admin"),
        cvss_score=5.3,
        remediation="Place Grafana behind a VPN or restrict access by IP.",
        requests=(
            ProbeRequest(
                path="/grafana/",
                matchers=(
                    StatusMatcher(codes=(200, 302)),
                    WordMatcher(words=("Grafana", "grafana")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="kibana-exposed",
        name="Kibana Dashboard Exposed",
        description="An Elasticsearch / Kibana dashboard is publicly accessible without authentication.",
        severity=Severity.HIGH,
        category="misconfiguration",
        tags=("kibana", "elasticsearch", "data"),
        cvss_score=7.5,
        remediation="Enable X-Pack security or place Kibana behind an authenticated reverse proxy.",
        requests=(
            ProbeRequest(
                path="/app/kibana",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("Kibana", "Elastic")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="jenkins-exposed",
        name="Jenkins CI/CD Dashboard Exposed",
        description=(
            "A Jenkins build server is publicly accessible. "
            "Unauthenticated Jenkins often allows arbitrary code execution on build agents."
        ),
        severity=Severity.CRITICAL,
        category="misconfiguration",
        tags=("jenkins", "cicd", "rce"),
        cvss_score=9.8,
        remediation="Enable Jenkins authentication and place it behind a VPN.",
        requests=(
            ProbeRequest(
                path="/jenkins/",
                matchers=(
                    StatusMatcher(codes=(200, 403)),
                    WordMatcher(words=("Jenkins", "Dashboard [Jenkins]")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="spring-actuator-exposed",
        name="Spring Boot Actuator Endpoints Exposed",
        description=(
            "Spring Boot Actuator management endpoints are publicly accessible. "
            "These may expose environment variables, heap dumps, and shutdown capabilities."
        ),
        severity=Severity.HIGH,
        category="misconfiguration",
        tags=("spring", "actuator", "java", "disclosure"),
        cvss_score=7.5,
        remediation="Restrict Actuator endpoints to localhost or authenticated management ports.",
        requests=(
            ProbeRequest(
                path="/actuator",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("\"_links\"", "health", "actuator")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="robots-txt-sensitive",
        name="robots.txt Reveals Sensitive Paths",
        description=(
            "The robots.txt file contains Disallow entries for administrative or sensitive paths, "
            "inadvertently advertising them to attackers."
        ),
        severity=Severity.INFO,
        category="misconfiguration",
        tags=("robots", "disclosure"),
        requests=(
            ProbeRequest(
                path="/robots.txt",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(
                        words=("Disallow: /admin", "Disallow: /backup", "Disallow: /config",
                               "Disallow: /private", "Disallow: /api"),
                    ),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="http-options-trace",
        name="HTTP TRACE Method Enabled",
        description=(
            "The TRACE HTTP method is enabled. "
            "Cross-Site Tracing (XST) attacks can exploit this in combination with XSS."
        ),
        severity=Severity.LOW,
        category="misconfiguration",
        tags=("trace", "http-method"),
        cvss_score=3.7,
        remediation="Disable the TRACE method in your web server configuration.",
        requests=(
            ProbeRequest(
                method="TRACE",
                path="/",
                matchers=(StatusMatcher(codes=(200,)),),
                matcher_condition=MatcherCondition.OR,
            ),
        ),
    ),
    ProbeTemplate(
        id="cors-credentials-wildcard",
        name="CORS Credentials with Wildcard Origin",
        description=(
            "The server responds with Access-Control-Allow-Credentials: true "
            "alongside Access-Control-Allow-Origin: *. "
            "Browsers block this combination, but misconfigurations elsewhere can allow CSRF."
        ),
        severity=Severity.HIGH,
        category="misconfiguration",
        tags=("cors", "csrf", "credentials"),
        cvss_score=7.5,
        remediation="Specify explicit trusted origins instead of using a wildcard with credentials.",
        requests=(
            ProbeRequest(
                path="/",
                headers=(("Origin", "https://evil.example.com"),),
                matchers=(
                    StatusMatcher(codes=(200,)),
                    HeaderMatcher(header_name="Access-Control-Allow-Credentials", contains="true"),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
]
