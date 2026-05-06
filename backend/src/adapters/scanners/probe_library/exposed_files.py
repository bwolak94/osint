"""Exposed-file probe templates.

Detects sensitive files and directories that are publicly accessible.
All checks are read-only HTTP GETs — no modification, no injection.
"""

from src.adapters.scanners.probe_template import (
    MatcherCondition,
    MatcherPart,
    ProbeRequest,
    ProbeTemplate,
    RegexMatcher,
    Severity,
    StatusMatcher,
    WordMatcher,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _file_template(
    template_id: str,
    name: str,
    path: str,
    severity: Severity,
    description: str,
    remediation: str,
    tags: tuple[str, ...],
    cvss_score: float | None = None,
    extra_word_matchers: tuple[str, ...] = (),
) -> ProbeTemplate:
    """Factory for simple path-existence templates with optional word matchers."""
    matchers: list = [StatusMatcher(codes=(200,))]
    if extra_word_matchers:
        matchers.append(WordMatcher(words=extra_word_matchers, condition=MatcherCondition.OR))
    return ProbeTemplate(
        id=template_id,
        name=name,
        description=description,
        severity=severity,
        category="exposed-files",
        tags=tags,
        cvss_score=cvss_score,
        remediation=remediation,
        requests=(
            ProbeRequest(
                path=path,
                matchers=tuple(matchers),
                matcher_condition=MatcherCondition.AND if extra_word_matchers else MatcherCondition.OR,
            ),
        ),
    )


TEMPLATES: list[ProbeTemplate] = [
    ProbeTemplate(
        id="exposed-git-repo",
        name="Exposed .git Repository",
        description=(
            "The .git/HEAD file is publicly accessible. "
            "This may allow an attacker to reconstruct the entire source code repository."
        ),
        severity=Severity.CRITICAL,
        category="exposed-files",
        tags=("git", "source-code", "disclosure"),
        cvss_score=9.1,
        remediation="Deny access to the .git directory in your web server configuration.",
        references=("https://owasp.org/www-project-web-security-testing-guide/",),
        requests=(
            ProbeRequest(
                path="/.git/HEAD",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("ref: refs/", "HEAD")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="exposed-env-file",
        name="Exposed .env Configuration File",
        description=(
            "An .env file is publicly accessible. "
            "These files commonly contain database credentials, API keys, and secrets."
        ),
        severity=Severity.CRITICAL,
        category="exposed-files",
        tags=("env", "credentials", "disclosure"),
        cvss_score=9.8,
        remediation="Move .env files outside the web root or deny access at the server level.",
        requests=(
            ProbeRequest(
                path="/.env",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("DB_PASSWORD", "APP_KEY", "SECRET", "DATABASE_URL", "API_KEY")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="exposed-env-local",
        name="Exposed .env.local File",
        description="A .env.local override file is accessible, potentially exposing local secrets.",
        severity=Severity.HIGH,
        category="exposed-files",
        tags=("env", "credentials", "disclosure"),
        cvss_score=8.1,
        remediation="Deny access to all .env* files in your server configuration.",
        requests=(
            ProbeRequest(
                path="/.env.local",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("=", "DB_", "SECRET", "KEY", "TOKEN")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="exposed-phpinfo",
        name="PHP Info Page Exposed",
        description=(
            "A phpinfo() page is publicly accessible. "
            "It discloses server configuration, loaded modules, environment variables, and file paths."
        ),
        severity=Severity.MEDIUM,
        category="exposed-files",
        tags=("php", "disclosure", "fingerprint"),
        cvss_score=5.3,
        remediation="Remove phpinfo() calls from production or restrict access by IP.",
        requests=(
            ProbeRequest(
                path="/phpinfo.php",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("PHP Version", "PHP License", "phpinfo()")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="exposed-backup-zip",
        name="Exposed Backup Archive (.zip)",
        description=(
            "A backup zip file is accessible at the web root. "
            "This often contains the full application source code and configuration."
        ),
        severity=Severity.CRITICAL,
        category="exposed-files",
        tags=("backup", "disclosure"),
        cvss_score=9.1,
        remediation="Remove backup files from web-accessible directories.",
        requests=(
            ProbeRequest(
                path="/backup.zip",
                matchers=(StatusMatcher(codes=(200,)),),
                matcher_condition=MatcherCondition.OR,
            ),
        ),
    ),
    ProbeTemplate(
        id="exposed-backup-sql",
        name="Exposed SQL Dump File",
        description="A database dump (.sql) file is accessible, potentially exposing full database contents.",
        severity=Severity.CRITICAL,
        category="exposed-files",
        tags=("backup", "database", "disclosure"),
        cvss_score=9.8,
        remediation="Never place SQL dumps in web-accessible directories.",
        requests=(
            ProbeRequest(
                path="/backup.sql",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("INSERT INTO", "CREATE TABLE", "DROP TABLE", "-- MySQL dump")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="exposed-ds-store",
        name="Exposed .DS_Store File",
        description=(
            ".DS_Store is a macOS metadata file. "
            "When exposed, it leaks directory structure and filenames."
        ),
        severity=Severity.LOW,
        category="exposed-files",
        tags=("disclosure", "macos"),
        cvss_score=3.7,
        remediation="Add a rule to deny access to .DS_Store files in your web server.",
        requests=(
            ProbeRequest(
                path="/.DS_Store",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    # DS_Store files are binary; checking for the magic bytes is more reliable
                    RegexMatcher(pattern=r"Bud1|\x00\x00\x00"),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="exposed-config-yml",
        name="Exposed Application Config (config.yml)",
        description="An application configuration YAML file is accessible at the web root.",
        severity=Severity.HIGH,
        category="exposed-files",
        tags=("config", "disclosure"),
        cvss_score=7.5,
        remediation="Store configuration files outside the web root.",
        requests=(
            ProbeRequest(
                path="/config.yml",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("database:", "password:", "secret:", "host:", "port:")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="exposed-composer-json",
        name="Exposed composer.json (PHP Dependency Manifest)",
        description="composer.json lists all PHP dependencies and their versions, aiding targeted attacks.",
        severity=Severity.INFO,
        category="exposed-files",
        tags=("composer", "php", "fingerprint"),
        requests=(
            ProbeRequest(
                path="/composer.json",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("require", "autoload", "repositories")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="exposed-package-json",
        name="Exposed package.json (Node.js Dependency Manifest)",
        description="package.json reveals all Node.js dependencies and project structure.",
        severity=Severity.INFO,
        category="exposed-files",
        tags=("nodejs", "npm", "fingerprint"),
        requests=(
            ProbeRequest(
                path="/package.json",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("dependencies", "scripts", "version")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="exposed-wp-config",
        name="Exposed WordPress wp-config.php",
        description=(
            "wp-config.php is a WordPress configuration file containing database credentials. "
            "Direct access should always be blocked by the web server."
        ),
        severity=Severity.CRITICAL,
        category="exposed-files",
        tags=("wordpress", "credentials", "disclosure"),
        cvss_score=9.8,
        remediation="Ensure your web server denies direct PHP execution outside the web root, or add explicit Deny rules.",
        requests=(
            ProbeRequest(
                path="/wp-config.php",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("DB_PASSWORD", "DB_NAME", "DB_HOST", "table_prefix")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="exposed-htpasswd",
        name="Exposed .htpasswd File",
        description=".htpasswd contains hashed passwords for HTTP Basic Authentication.",
        severity=Severity.HIGH,
        category="exposed-files",
        tags=("auth", "credentials", "disclosure"),
        cvss_score=8.0,
        remediation="Deny access to .htpasswd via server configuration.",
        requests=(
            ProbeRequest(
                path="/.htpasswd",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    RegexMatcher(pattern=r":\$apr1\$|:\$2y\$|:\{SHA\}|:[a-zA-Z0-9+/]{13}"),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
    ProbeTemplate(
        id="exposed-swagger-ui",
        name="Swagger / OpenAPI UI Exposed",
        description=(
            "An API documentation UI (Swagger/OpenAPI) is publicly accessible. "
            "This exposes the full API surface to unauthenticated users."
        ),
        severity=Severity.LOW,
        category="exposed-files",
        tags=("api", "swagger", "disclosure"),
        cvss_score=4.3,
        remediation="Restrict access to API documentation to authenticated/internal users.",
        requests=(
            ProbeRequest(
                path="/swagger-ui.html",
                matchers=(
                    StatusMatcher(codes=(200,)),
                    WordMatcher(words=("swagger", "openapi", "Swagger UI")),
                ),
                matcher_condition=MatcherCondition.AND,
            ),
        ),
    ),
]
