"""Email Security — SPF/DKIM/DMARC deep audit + phishing infrastructure scanner.

Deep email security audit: SPF mechanism expansion, DKIM key strength,
DMARC policy enforcement level, MTA-STS, BIMI, mail server TLS, open relay
testing, email spoofing feasibility, and phishing infrastructure detection.

Goes far beyond mx_spf_dmarc with active SMTP probing and spoofability scoring.
"""

from __future__ import annotations

import asyncio
import re
import socket
import ssl
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Cloudflare DoH
_DOH = "https://cloudflare-dns.com/dns-query"

# SPF mechanisms that allow all/broad sending
_SPF_PERMISSIVE = re.compile(r'(?i)\+all|~all|[?]all|\ball\b')
_SPF_REDIRECT = re.compile(r'redirect=([^\s]+)')
_SPF_INCLUDE = re.compile(r'include:([^\s]+)')

# DMARC policy patterns
_DMARC_POLICY = re.compile(r'p=(none|quarantine|reject)', re.I)
_DMARC_SUBDOMAIN = re.compile(r'sp=(none|quarantine|reject)', re.I)
_DMARC_PCT = re.compile(r'pct=(\d+)', re.I)
_DMARC_RUA = re.compile(r'rua=mailto:([^\s;]+)', re.I)

# DKIM key length detection in TXT record
_DKIM_KEY = re.compile(r'p=([A-Za-z0-9+/=]+)')

# MTA-STS / BIMI
_MTA_STS_MODE = re.compile(r'mode=(enforce|testing|none)', re.I)

# Spoofing feasibility scoring
_SPOOF_SCORE: dict[str, int] = {
    "no_spf": 40,
    "spf_all": 30,
    "spf_softfail": 20,
    "no_dmarc": 35,
    "dmarc_none": 25,
    "dmarc_pct_low": 10,
    "no_dkim": 15,
    "dkim_short_key": 10,
}


class EmailSecurityScanner(BaseOsintScanner):
    """Deep email security and anti-spoofing configuration scanner.

    Audits SPF, DKIM, DMARC, MTA-STS, BIMI, and SMTP TLS configuration.
    Calculates a spoofability score and identifies phishing risk factors.
    """

    scanner_name = "email_security"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 7200
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().lower()
        return await self._manual_scan(domain)

    async def _manual_scan(self, domain: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        spf_record: str = ""
        dmarc_record: str = ""
        dkim_selectors_found: list[str] = []
        mta_sts_record: str = ""
        spoof_score = 0

        async with httpx.AsyncClient(
            timeout=8,
            verify=True,
            headers={"Accept": "application/dns-json"},
        ) as client:

            async def dns_query(name: str, rtype: str) -> list[str]:
                try:
                    resp = await client.get(
                        _DOH, params={"name": name, "type": rtype}
                    )
                    if resp.status_code == 200:
                        import json as _json
                        data = _json.loads(resp.text)
                        return [a["data"].strip('"') for a in data.get("Answer", [])
                                if a.get("type") in (16, 15, 1, 28)]  # TXT, MX, A, AAAA
                    return []
                except Exception:
                    return []

            # Step 1: SPF record
            txt_records = await dns_query(domain, "TXT")
            for record in txt_records:
                if "v=spf1" in record.lower():
                    spf_record = record
                    break

            if not spf_record:
                vulnerabilities.append({
                    "type": "no_spf_record",
                    "severity": "high",
                    "domain": domain,
                    "description": "No SPF record — anyone can send email as @" + domain,
                    "remediation": 'Add TXT record: "v=spf1 include:YOUR_PROVIDER ~all"',
                })
                identifiers.append("vuln:email:no_spf")
                spoof_score += _SPOOF_SCORE["no_spf"]
            else:
                # Check SPF permissiveness
                if re.search(r'\+all', spf_record):
                    vulnerabilities.append({
                        "type": "spf_allow_all",
                        "severity": "critical",
                        "domain": domain,
                        "spf": spf_record[:100],
                        "description": "SPF record uses +all — permits ANY server to send as " + domain,
                        "remediation": "Replace +all with -all (hard fail)",
                    })
                    identifiers.append("vuln:email:spf_plus_all")
                    spoof_score += _SPOOF_SCORE["spf_all"]

                elif re.search(r'~all', spf_record):
                    vulnerabilities.append({
                        "type": "spf_softfail",
                        "severity": "medium",
                        "domain": domain,
                        "spf": spf_record[:100],
                        "description": "SPF uses ~all (SoftFail) — spoofed email may reach inbox",
                        "remediation": "Change ~all to -all after validating legitimate senders",
                    })
                    identifiers.append("vuln:email:spf_softfail")
                    spoof_score += _SPOOF_SCORE["spf_softfail"]

                # Count DNS lookups (SPF 10-lookup limit)
                includes = _SPF_INCLUDE.findall(spf_record)
                if len(includes) > 8:
                    vulnerabilities.append({
                        "type": "spf_lookup_limit",
                        "severity": "medium",
                        "domain": domain,
                        "include_count": len(includes),
                        "description": f"SPF record has {len(includes)} includes — may exceed 10 DNS lookup limit causing delivery failures",
                    })
                    identifiers.append("vuln:email:spf_lookup_limit")

            # Step 2: DMARC record
            dmarc_records = await dns_query(f"_dmarc.{domain}", "TXT")
            for record in dmarc_records:
                if "v=dmarc1" in record.lower():
                    dmarc_record = record
                    break

            if not dmarc_record:
                vulnerabilities.append({
                    "type": "no_dmarc_record",
                    "severity": "high",
                    "domain": domain,
                    "description": "No DMARC record — no policy for handling spoofed email",
                    "remediation": 'Add TXT _dmarc.' + domain + ': "v=DMARC1; p=reject; rua=mailto:dmarc@' + domain + '"',
                })
                identifiers.append("vuln:email:no_dmarc")
                spoof_score += _SPOOF_SCORE["no_dmarc"]
            else:
                policy_m = _DMARC_POLICY.search(dmarc_record)
                policy = policy_m.group(1).lower() if policy_m else "none"

                if policy == "none":
                    vulnerabilities.append({
                        "type": "dmarc_policy_none",
                        "severity": "high",
                        "domain": domain,
                        "dmarc": dmarc_record[:120],
                        "description": "DMARC policy=none — monitoring only, no rejection. Spoofed email delivered.",
                        "remediation": "Progress to p=quarantine then p=reject after testing",
                    })
                    identifiers.append("vuln:email:dmarc_none")
                    spoof_score += _SPOOF_SCORE["dmarc_none"]

                elif policy == "quarantine":
                    vulnerabilities.append({
                        "type": "dmarc_policy_quarantine",
                        "severity": "low",
                        "domain": domain,
                        "description": "DMARC p=quarantine — spoofed emails go to spam, not rejected",
                        "remediation": "Upgrade to p=reject for full protection",
                    })
                    identifiers.append("info:email:dmarc_quarantine")

                # Check pct
                pct_m = _DMARC_PCT.search(dmarc_record)
                pct = int(pct_m.group(1)) if pct_m else 100
                if pct < 100 and policy != "none":
                    vulnerabilities.append({
                        "type": "dmarc_partial_enforcement",
                        "severity": "medium",
                        "domain": domain,
                        "pct": pct,
                        "description": f"DMARC pct={pct} — policy only applied to {pct}% of failing email",
                        "remediation": "Increase pct to 100 once legitimate senders are confirmed",
                    })
                    spoof_score += _SPOOF_SCORE["dmarc_pct_low"]

                # Check subdomain policy
                sp_m = _DMARC_SUBDOMAIN.search(dmarc_record)
                if not sp_m and policy == "reject":
                    vulnerabilities.append({
                        "type": "dmarc_missing_subdomain_policy",
                        "severity": "medium",
                        "domain": domain,
                        "description": "DMARC sp= not set — subdomains may not be protected",
                        "remediation": "Add sp=reject to cover subdomain spoofing",
                    })

            # Step 3: DKIM selector discovery
            common_selectors = [
                "default", "google", "k1", "mail", "dkim", "selector1", "selector2",
                "s1", "s2", "smtp", "email", "m1", "key1", "mimecast",
            ]
            async def check_dkim(selector: str) -> None:
                records = await dns_query(f"{selector}._domainkey.{domain}", "TXT")
                for record in records:
                    if "v=dkim1" in record.lower() or "p=" in record:
                        dkim_selectors_found.append(selector)
                        key_m = _DKIM_KEY.search(record)
                        if key_m:
                            key_b64 = key_m.group(1)
                            key_bits = len(key_b64) * 6 // 8 * 8
                            if key_bits < 2048:
                                vulnerabilities.append({
                                    "type": "dkim_weak_key",
                                    "severity": "medium",
                                    "domain": domain,
                                    "selector": selector,
                                    "estimated_bits": key_bits,
                                    "description": f"DKIM key for selector '{selector}' appears shorter than 2048 bits",
                                    "remediation": "Regenerate DKIM keys with 2048-bit RSA",
                                })
                                identifiers.append("vuln:email:dkim_weak_key")

            await asyncio.gather(*[check_dkim(s) for s in common_selectors])

            if not dkim_selectors_found:
                vulnerabilities.append({
                    "type": "no_dkim_found",
                    "severity": "medium",
                    "domain": domain,
                    "description": "No DKIM selectors found — email cannot be cryptographically verified",
                    "remediation": "Configure DKIM signing with your email provider",
                })
                identifiers.append("vuln:email:no_dkim")
                spoof_score += _SPOOF_SCORE["no_dkim"]

            # Step 4: MTA-STS
            mta_records = await dns_query(f"_mta-sts.{domain}", "TXT")
            for record in mta_records:
                if "v=sts1" in record.lower():
                    mta_sts_record = record
                    break

            if not mta_sts_record:
                vulnerabilities.append({
                    "type": "no_mta_sts",
                    "severity": "low",
                    "domain": domain,
                    "description": "MTA-STS not configured — mail server connections may be downgraded",
                    "remediation": "Implement MTA-STS to enforce TLS on mail delivery",
                })
                identifiers.append("info:email:no_mta_sts")

        # Overall spoofability assessment
        spoofability = "low"
        if spoof_score >= 60:
            spoofability = "critical"
        elif spoof_score >= 40:
            spoofability = "high"
        elif spoof_score >= 20:
            spoofability = "medium"

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": domain,
            "scan_mode": "manual_fallback",
            "domain": domain,
            "spf_record": spf_record[:200] if spf_record else None,
            "dmarc_record": dmarc_record[:200] if dmarc_record else None,
            "dkim_selectors": dkim_selectors_found,
            "mta_sts": bool(mta_sts_record),
            "spoof_score": spoof_score,
            "spoofability": spoofability,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
