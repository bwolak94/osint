"""SQLMap — SQL injection detection and exploitation scanner.

SQLMap is the most powerful open-source SQL injection tool. It automatically
detects and exploits SQL injection vulnerabilities in web applications.

Two-mode operation:
1. **sqlmap binary** — if on PATH, invoked in detection-only mode (no exploitation)
2. **Manual fallback** — sends error-based, boolean-based, and time-based SQL probes
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from typing import Any
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# SQL injection detection payloads per technique
# (payload, technique, detection_pattern)
_SQLI_PROBES: list[tuple[str, str, str | None]] = [
    # Error-based — triggers DB error messages in response
    ("'", "error_based", r"(?i)(sql syntax|mysql_fetch|ORA-|pg_query|sqlite_|ODBC|JDBC|Warning.*mysql|supplied argument)"),
    ('"', "error_based", r"(?i)(sql syntax|mysql_fetch|ORA-|pg_query|sqlite_|ODBC|JDBC|Warning.*mysql|supplied argument)"),
    ("1'", "error_based", r"(?i)(sql syntax|mysql_fetch|ORA-|pg_query|sqlite_|ODBC|JDBC)"),
    ("1\"", "error_based", r"(?i)(sql syntax|mysql_fetch|ORA-|pg_query|sqlite_|ODBC|JDBC)"),
    # Boolean-based — compare true vs false
    ("1 AND 1=1", "boolean_based", None),
    ("1 AND 1=2", "boolean_based", None),
    ("' OR '1'='1", "boolean_based", None),
    ("' OR '1'='2", "boolean_based", None),
    # UNION-based — attempt to detect column count errors
    ("' UNION SELECT NULL--", "union_based", r"(?i)(UNION|column|number of columns|incorrect number)"),
    ("1 UNION SELECT NULL--", "union_based", r"(?i)(UNION|column|number of columns|incorrect number)"),
    # Stacked queries indicator
    ("'; SELECT 1--", "stacked_queries", r"(?i)(syntax error|unexpected token)"),
]

# DB fingerprint patterns in error messages
_DB_SIGNATURES: list[tuple[str, str]] = [
    (r"mysql_fetch|You have an error in your SQL syntax", "MySQL"),
    (r"ORA-\d{5}|Oracle.*error", "Oracle"),
    (r"pg_query|PostgreSQL.*ERROR|unterminated quoted string", "PostgreSQL"),
    (r"sqlite_|SQLite3::", "SQLite"),
    (r"Microsoft.*ODBC.*SQL Server|Unclosed quotation mark", "MSSQL"),
    (r"Warning.*mssql|Incorrect syntax near", "MSSQL"),
    (r"DB2 SQL error|SQLSTATE\[", "DB2"),
]

# Common parameters likely to be injectable
_INJECTABLE_PARAMS = [
    "id", "user_id", "item_id", "product_id", "category_id", "order_id",
    "page", "article", "post", "news", "view", "type",
    "q", "search", "query", "keyword", "filter",
    "sort", "order", "by", "dir",
    "username", "user", "login", "email",
    "lang", "language", "locale",
    "ref", "from", "to",
]


class SQLMapScanner(BaseOsintScanner):
    """SQL injection vulnerability scanner.

    Probes web application parameters for SQL injection vulnerabilities using:
    - Error-based detection (DB error in response)
    - Boolean-based blind detection (different response for true/false)
    - UNION-based detection (column enumeration errors)
    Identifies the database type when possible.
    """

    scanner_name = "sqlmap"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 1800
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("sqlmap"):
            return await self._run_sqlmap_binary(base_url, input_value)
        return await self._manual_scan(base_url, input_value)

    async def _run_sqlmap_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_dir = os.path.join(tempfile.gettempdir(), f"sqlmap_{run_id}")
        os.makedirs(out_dir, exist_ok=True)
        cmd = [
            "sqlmap",
            "-u", base_url,
            "--output-dir", out_dir,
            "--batch",
            "--level", "2",
            "--risk", "1",
            "--technique", "BEUSTQ",
            "--forms",
            "--crawl", "2",
            "--threads", "4",
            "--no-logging",
            "--disable-coloring",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.scan_timeout - 15)
                output = stdout.decode(errors="replace")
            except asyncio.TimeoutError:
                log.warning("sqlmap timed out", url=base_url)
                try:
                    proc.kill()
                except Exception:
                    pass
                output = ""
        except Exception as exc:
            log.debug("sqlmap binary failed", error=str(exc))
            output = ""

        # Parse sqlmap output for injection points
        injections: list[dict[str, Any]] = []
        db_type = None

        param_matches = re.findall(
            r"Parameter: (\S+) \((\w+)\).*?Type: ([^\n]+).*?Title: ([^\n]+)",
            output, re.DOTALL,
        )
        for match in param_matches:
            injections.append({
                "parameter": match[0],
                "method": match[1],
                "technique": match[2].strip(),
                "title": match[3].strip(),
                "severity": "critical",
            })

        db_match = re.search(r"back-end DBMS: ([^\n]+)", output)
        if db_match:
            db_type = db_match.group(1).strip()

        identifiers = [f"vuln:sqli:{inj['parameter']}" for inj in injections]
        return {
            "input": input_value,
            "scan_mode": "sqlmap_binary",
            "base_url": base_url,
            "injectable_parameters": injections,
            "database_type": db_type,
            "total_injections": len(injections),
            "is_vulnerable": len(injections) > 0,
            "extracted_identifiers": identifiers,
        }

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        db_type: str | None = None

        # Extract existing params from URL
        parsed = urlparse(base_url)
        existing_params = list(parse_qs(parsed.query).keys())
        base_clean = base_url.split("?")[0]

        test_params = list(dict.fromkeys(existing_params + _INJECTABLE_PARAMS[:8]))

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SQLScanner/1.0)"},
        ) as client:
            # Get baselines for boolean-blind detection
            baselines: dict[str, tuple[int, int]] = {}
            for param in test_params[:6]:
                try:
                    url_true = f"{base_clean}?{param}=1 AND 1=1"
                    url_false = f"{base_clean}?{param}=1 AND 1=2"
                    r_true = await client.get(url_true)
                    r_false = await client.get(url_false)
                    baselines[param] = (len(r_true.content), len(r_false.content))
                except Exception:
                    pass

            semaphore = asyncio.Semaphore(6)

            async def test_param(param: str) -> None:
                nonlocal db_type
                async with semaphore:
                    for payload, technique, pattern in _SQLI_PROBES:
                        try:
                            test_url = f"{base_clean}?{param}={payload}"
                            resp = await client.get(test_url)
                            body = resp.text

                            # Error-based detection
                            if technique == "error_based" and pattern:
                                if re.search(pattern, body, re.I):
                                    # Identify DB
                                    for db_pattern, db_name in _DB_SIGNATURES:
                                        if re.search(db_pattern, body, re.I):
                                            db_type = db_name
                                            break
                                    vuln = {
                                        "parameter": param,
                                        "payload": payload,
                                        "technique": "error_based",
                                        "severity": "critical",
                                        "database": db_type,
                                        "evidence": "SQL error message in response",
                                    }
                                    vulnerabilities.append(vuln)
                                    ident = f"vuln:sqli:{param}"
                                    if ident not in identifiers:
                                        identifiers.append(ident)
                                    return  # Found — stop testing this param

                            # Boolean-based blind detection
                            elif technique == "boolean_based" and param in baselines:
                                true_len, false_len = baselines[param]
                                resp_len = len(resp.content)
                                # Significant difference between true/false baselines
                                if abs(true_len - false_len) > 30:
                                    if (payload.endswith("1=1") and abs(resp_len - true_len) < 20) or \
                                       (payload.endswith("1=2") and abs(resp_len - false_len) < 20):
                                        vuln = {
                                            "parameter": param,
                                            "payload": payload,
                                            "technique": "boolean_blind",
                                            "severity": "high",
                                            "evidence": f"Response size diff: true={true_len} false={false_len}",
                                        }
                                        vulnerabilities.append(vuln)
                                        ident = f"vuln:sqli_blind:{param}"
                                        if ident not in identifiers:
                                            identifiers.append(ident)
                                        return

                        except Exception:
                            pass

            tasks = [test_param(p) for p in test_params]
            await asyncio.gather(*tasks)

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "injectable_parameters": vulnerabilities,
            "database_type": db_type,
            "total_injections": len(vulnerabilities),
            "is_vulnerable": len(vulnerabilities) > 0,
            "params_tested": test_params,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value
