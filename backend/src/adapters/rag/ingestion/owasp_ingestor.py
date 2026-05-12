"""OWASP knowledge base ingestors.

Two ingestors are provided:
- ``OWASPTop10Ingestor``  — the OWASP Top 10 (2021) as concise structured entries.
- ``OWASPCheatSheetIngestor`` — select OWASP Cheat Sheet Series entries.

Content is hardcoded rather than fetched live because the upstream Markdown files
are large and parsing them reliably adds unnecessary complexity.  The content
below captures the essential guidance needed for RAG-augmented pentest suggestions.
"""

from __future__ import annotations

import structlog

from src.adapters.rag.ingestion.base_ingestor import BaseIngestor, RawDocument

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# OWASP Top 10 — 2021 edition
# ---------------------------------------------------------------------------

_OWASP_TOP10_ENTRIES: list[dict] = [
    {
        "id": "A01:2021",
        "title": "Broken Access Control",
        "content": (
            "A01:2021 - Broken Access Control: Access control enforces policy such that users cannot act outside "
            "their intended permissions. Failures typically lead to unauthorized information disclosure, modification, "
            "or destruction of all data, or performing a business function outside the user's limits. "
            "Common vulnerabilities include IDOR, missing function-level access control, privilege escalation, "
            "and CORS misconfiguration. "
            "Mitigations: deny by default, implement least-privilege, enforce access control server-side, "
            "log access-control failures and alert admins on repeated failures."
        ),
        "cwe": [284, 285, 639],
        "wstg": "WSTG-ATHZ",
        "url": "https://owasp.org/Top10/A01_2021-Broken_Access_Control/",
    },
    {
        "id": "A02:2021",
        "title": "Cryptographic Failures",
        "content": (
            "A02:2021 - Cryptographic Failures: Previously known as Sensitive Data Exposure. "
            "Focuses on failures related to cryptography that expose sensitive data or compromise the system. "
            "Common issues: data transmitted in clear text, weak/old cryptographic algorithms (MD5, SHA1, DES), "
            "improper key management, missing HSTS, weak TLS configuration. "
            "Mitigations: encrypt data at rest and in transit, use strong modern algorithms (AES-256, SHA-256+), "
            "enforce TLS 1.2+, implement proper certificate validation."
        ),
        "cwe": [261, 296, 310, 319, 321, 326, 327],
        "wstg": "WSTG-CRYP",
        "url": "https://owasp.org/Top10/A02_2021-Cryptographic_Failures/",
    },
    {
        "id": "A03:2021",
        "title": "Injection",
        "content": (
            "A03:2021 - Injection: SQL, NoSQL, OS, LDAP injection occur when untrusted data is sent to an "
            "interpreter as part of a command or query. An attacker's hostile data can trick the interpreter "
            "into executing unintended commands or accessing data without proper authorisation. "
            "Includes SQL injection, XSS, SSTI, command injection, LDAP injection. "
            "Mitigations: use parameterised queries/prepared statements, input validation, escape all user-supplied "
            "data, use safe APIs, apply least privilege to database accounts."
        ),
        "cwe": [77, 78, 79, 89, 90, 943],
        "wstg": "WSTG-INPV",
        "url": "https://owasp.org/Top10/A03_2021-Injection/",
    },
    {
        "id": "A04:2021",
        "title": "Insecure Design",
        "content": (
            "A04:2021 - Insecure Design: A broad category representing different weaknesses expressed as "
            "missing or ineffective control design. An insecure design cannot be fixed by a perfect implementation "
            "as by definition, needed security controls were never created. "
            "Includes missing threat modelling, insecure business logic, weak anti-automation controls. "
            "Mitigations: establish a secure development lifecycle, use threat modelling for critical flows, "
            "integrate security requirements from design phase, use reference architectures."
        ),
        "cwe": [73, 183, 209, 213, 235, 256, 257, 266, 269, 280],
        "wstg": "WSTG-BUSL",
        "url": "https://owasp.org/Top10/A04_2021-Insecure_Design/",
    },
    {
        "id": "A05:2021",
        "title": "Security Misconfiguration",
        "content": (
            "A05:2021 - Security Misconfiguration: The most commonly seen issue. "
            "Includes missing hardening, unnecessary features enabled, default credentials unchanged, "
            "verbose error messages exposing stack traces, missing security headers, "
            "cloud storage misconfiguration (public S3 buckets), unnecessary open ports. "
            "Mitigations: minimal platform installation, automated configuration review, "
            "remove or disable unused features, proper cloud security posture management."
        ),
        "cwe": [2, 11, 13, 15, 16, 260, 315, 520, 526, 537, 541, 548, 732],
        "wstg": "WSTG-CONF",
        "url": "https://owasp.org/Top10/A05_2021-Security_Misconfiguration/",
    },
    {
        "id": "A06:2021",
        "title": "Vulnerable and Outdated Components",
        "content": (
            "A06:2021 - Vulnerable and Outdated Components: You are likely vulnerable if you do not know the "
            "versions of all components (client-side and server-side), if software is vulnerable/unsupported/out-of-date, "
            "or if you do not scan for vulnerabilities regularly. "
            "Mitigations: remove unused dependencies, continuously inventory component versions, "
            "monitor NVD/CVE feeds, subscribe to security bulletins, obtain components from official sources only."
        ),
        "cwe": [937, 1035, 1104],
        "wstg": "WSTG-CONF-02",
        "url": "https://owasp.org/Top10/A06_2021-Vulnerable_and_Outdated_Components/",
    },
    {
        "id": "A07:2021",
        "title": "Identification and Authentication Failures",
        "content": (
            "A07:2021 - Identification and Authentication Failures: Previously Broken Authentication. "
            "Includes weak passwords, credential stuffing, brute force attacks, missing MFA, "
            "insecure session management, session fixation, exposed session IDs in URL. "
            "Mitigations: implement MFA, use strong password policies, limit failed login attempts, "
            "use secure session management, invalidate sessions on logout and after inactivity."
        ),
        "cwe": [255, 259, 287, 288, 290, 294, 295, 297, 300, 302, 304, 306, 307, 346, 384, 521, 613, 620, 640, 798, 940, 1216],
        "wstg": "WSTG-ATHN",
        "url": "https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/",
    },
    {
        "id": "A08:2021",
        "title": "Software and Data Integrity Failures",
        "content": (
            "A08:2021 - Software and Data Integrity Failures: Relates to code and infrastructure that does not "
            "protect against integrity violations. Includes insecure deserialization, untrusted CI/CD pipelines, "
            "auto-update without integrity verification, insecure direct object deserialization (IDOR via pickle/java). "
            "Mitigations: use digital signatures to verify software, ensure dependencies come from trusted repos, "
            "use software composition analysis tools, review CI/CD pipeline for misconfigurations."
        ),
        "cwe": [345, 353, 426, 494, 502, 565, 784, 829, 830, 915, 916],
        "wstg": "WSTG-INPV-11",
        "url": "https://owasp.org/Top10/A08_2021-Software_and_Data_Integrity_Failures/",
    },
    {
        "id": "A09:2021",
        "title": "Security Logging and Monitoring Failures",
        "content": (
            "A09:2021 - Security Logging and Monitoring Failures: Without logging and monitoring, breaches cannot "
            "be detected. Includes insufficient logging of authentication events, audit trails not stored long enough, "
            "log messages not clear enough to identify malicious activity, penetration tests not triggering alerts. "
            "Mitigations: ensure all login, access control, and server-side input validation failures are logged "
            "with sufficient context, establish incident response and recovery plans, use a SIEM system."
        ),
        "cwe": [117, 223, 532, 778],
        "wstg": "WSTG-ERRH",
        "url": "https://owasp.org/Top10/A09_2021-Security_Logging_and_Monitoring_Failures/",
    },
    {
        "id": "A10:2021",
        "title": "Server-Side Request Forgery",
        "content": (
            "A10:2021 - Server-Side Request Forgery (SSRF): SSRF flaws occur whenever a web application is fetching "
            "a remote resource without validating the user-supplied URL. Allows an attacker to coerce the server to "
            "send requests to unexpected destinations. Can be used to scan internal networks, access cloud metadata "
            "endpoints (169.254.169.254), bypass firewalls, or access internal services. "
            "Mitigations: sanitise and validate all client-supplied input URLs, enforce URL schema allowlist, "
            "disable HTTP redirections, do not send raw responses to clients."
        ),
        "cwe": [918],
        "wstg": "WSTG-INPV-19",
        "url": "https://owasp.org/Top10/A10_2021-Server-Side_Request_Forgery_%28SSRF%29/",
    },
]


# ---------------------------------------------------------------------------
# OWASP Cheat Sheet Series — select high-value entries
# ---------------------------------------------------------------------------

_OWASP_CHEATSHEETS: list[dict] = [
    {
        "id": "CS-SQL-INJECTION",
        "title": "SQL Injection Prevention Cheat Sheet",
        "content": (
            "OWASP SQL Injection Prevention: Use prepared statements (parameterised queries) as the primary defence. "
            "Stored procedures can provide the same level of protection when implemented safely. "
            "Allow-list input validation for values that cannot be parameterised (table/column names). "
            "Escape all user-supplied input as a last resort using database-specific escaping routines. "
            "Enforce least privilege — application accounts should only have SELECT/INSERT/UPDATE on needed tables. "
            "Never concatenate user input directly into SQL strings."
        ),
        "url": "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html",
        "cwe": [89],
    },
    {
        "id": "CS-XSS-PREVENTION",
        "title": "Cross Site Scripting Prevention Cheat Sheet",
        "content": (
            "OWASP XSS Prevention: Encode all untrusted data before inserting into HTML, attributes, JavaScript, "
            "CSS, and URLs. Use a Content Security Policy (CSP) as a defence-in-depth layer. "
            "Use the HTTPOnly flag on session cookies. "
            "Validate and sanitise HTML content using a trusted library (e.g., DOMPurify). "
            "Never insert untrusted data into script blocks, event handlers, or CSS. "
            "Use modern frameworks (React, Angular) that auto-escape by default."
        ),
        "url": "https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html",
        "cwe": [79],
    },
    {
        "id": "CS-AUTHENTICATION",
        "title": "Authentication Cheat Sheet",
        "content": (
            "OWASP Authentication: Implement MFA for all users. Use strong password policies (12+ chars, complexity). "
            "Hash passwords with bcrypt, scrypt, or Argon2 — never MD5/SHA1. "
            "Implement account lockout after failed attempts to prevent brute force. "
            "Use secure password reset flows (time-limited tokens, not security questions). "
            "Protect against credential stuffing with rate limiting and CAPTCHA. "
            "Rotate session tokens after login."
        ),
        "url": "https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html",
        "cwe": [287, 521, 640],
    },
    {
        "id": "CS-ACCESS-CONTROL",
        "title": "Access Control Cheat Sheet",
        "content": (
            "OWASP Access Control: Deny access by default. Apply principle of least privilege. "
            "Enforce access control checks server-side, never solely on the client. "
            "Log all access-control failures. Rate-limit API endpoints. "
            "Validate that the user owns the resources they request (prevent IDOR). "
            "Use centralised access control logic rather than scattered checks. "
            "Review access control matrix during design phase."
        ),
        "url": "https://cheatsheetseries.owasp.org/cheatsheets/Access_Control_Cheat_Sheet.html",
        "cwe": [284, 285, 639],
    },
    {
        "id": "CS-CSRF-PREVENTION",
        "title": "Cross-Site Request Forgery Prevention Cheat Sheet",
        "content": (
            "OWASP CSRF Prevention: Use synchronised token pattern — embed unique CSRF token in each state-changing form. "
            "Validate the token server-side on every state-changing request. "
            "Use SameSite=Strict or SameSite=Lax cookie attribute. "
            "Verify Origin/Referer headers as secondary defence. "
            "Avoid using GET for state-changing operations. "
            "Double-submit cookie pattern for stateless APIs."
        ),
        "url": "https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html",
        "cwe": [352],
    },
    {
        "id": "CS-SECRETS-MANAGEMENT",
        "title": "Secrets Management Cheat Sheet",
        "content": (
            "OWASP Secrets Management: Never hard-code secrets in source code. "
            "Use a secrets manager (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault). "
            "Rotate secrets regularly and automate rotation. "
            "Scan repositories for accidentally committed secrets using tools like TruffleHog, GitLeaks. "
            "Use environment variables or mounted secrets in container deployments. "
            "Apply least privilege to secret access — each service should only access secrets it needs."
        ),
        "url": "https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html",
        "cwe": [259, 798],
    },
    {
        "id": "CS-SSRF-PREVENTION",
        "title": "Server Side Request Forgery Prevention Cheat Sheet",
        "content": (
            "OWASP SSRF Prevention: Validate and sanitise all user-supplied URLs. "
            "Use an allowlist of permitted domains/IPs for outbound requests. "
            "Block requests to loopback (127.0.0.1, ::1), RFC1918 private ranges, and cloud metadata endpoints. "
            "Disable HTTP redirections or validate redirect destinations. "
            "Use a dedicated egress proxy that enforces the allowlist. "
            "Never return raw server-side responses to the client."
        ),
        "url": "https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html",
        "cwe": [918],
    },
    {
        "id": "CS-INPUT-VALIDATION",
        "title": "Input Validation Cheat Sheet",
        "content": (
            "OWASP Input Validation: Validate all input on the server side — never rely on client-side validation alone. "
            "Use allowlists over denylists for input validation. "
            "Validate data type, length, format, and range. "
            "Sanitise HTML input with a trusted library before rendering. "
            "Reject inputs that fail validation rather than attempting to sanitise dangerous data. "
            "Use structured data formats (JSON schema, Protobuf) with strict validation."
        ),
        "url": "https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html",
        "cwe": [20, 79, 89],
    },
]


class OWASPTop10Ingestor(BaseIngestor):
    """Emits one RawDocument per OWASP Top 10 category (2021 edition)."""

    def should_skip(self, doc: RawDocument) -> bool:
        # Content is static; skip once ingested.  In practice the Celery task
        # uses upsert semantics so this is only advisory.
        return False

    async def fetch(self) -> list[RawDocument]:
        docs = [
            RawDocument(
                source="owasp-top10",
                source_id=entry["id"],
                content=entry["content"],
                metadata={
                    "title": entry["title"],
                    "cwe": entry.get("cwe", []),
                    "wstg": entry.get("wstg", ""),
                    "url": entry["url"],
                },
            )
            for entry in _OWASP_TOP10_ENTRIES
        ]
        log.info("owasp_top10_ingestor.fetch.complete", count=len(docs))
        return docs


class OWASPCheatSheetIngestor(BaseIngestor):
    """Emits one RawDocument per OWASP Cheat Sheet Series entry."""

    def should_skip(self, doc: RawDocument) -> bool:
        return False

    async def fetch(self) -> list[RawDocument]:
        docs = [
            RawDocument(
                source="owasp-cheatsheet",
                source_id=entry["id"],
                content=entry["content"],
                metadata={
                    "title": entry["title"],
                    "cwe": entry.get("cwe", []),
                    "url": entry["url"],
                },
            )
            for entry in _OWASP_CHEATSHEETS
        ]
        log.info("owasp_cheatsheet_ingestor.fetch.complete", count=len(docs))
        return docs
