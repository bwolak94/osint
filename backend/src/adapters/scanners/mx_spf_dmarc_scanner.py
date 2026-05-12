"""MX / SPF / DMARC scanner — analyses email security DNS configuration."""

from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


def _parse_spf(txt: str) -> dict[str, Any]:
    mechanisms: list[str] = []
    all_qualifier = "?"
    for token in txt.split():
        if token.startswith("v=spf1"):
            continue
        if token in ("+all", "-all", "~all", "?all", "all"):
            all_qualifier = token
        else:
            mechanisms.append(token)
    return {"mechanisms": mechanisms, "all_qualifier": all_qualifier}


def _parse_dmarc(txt: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for part in txt.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            result[k.strip()] = v.strip()
    return result


def _email_security_score(
    spf_found: bool,
    spf_all: str,
    dmarc_found: bool,
    dmarc_policy: str,
    dkim_found: bool,
) -> int:
    """Returns 0-100 email security score."""
    score = 0
    if spf_found:
        score += 30
        if spf_all == "-all":
            score += 10
        elif spf_all == "~all":
            score += 5
    if dmarc_found:
        score += 30
        if dmarc_policy == "reject":
            score += 20
        elif dmarc_policy == "quarantine":
            score += 10
    if dkim_found:
        score += 10
    return min(score, 100)


class MXSPFDMARCScanner(BaseOsintScanner):
    """Analyses MX, SPF, DMARC, and DKIM DNS records for email security posture."""

    scanner_name = "mx_spf_dmarc"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            import dns.resolver
        except ImportError:
            return {"domain": input_value, "found": False, "_stub": True, "extracted_identifiers": []}

        mx_records: list[dict[str, Any]] = []
        spf_record: str | None = None
        dmarc_record: str | None = None
        dkim_found = False

        # MX records
        try:
            for rdata in dns.resolver.resolve(input_value, "MX"):
                mx_records.append({
                    "priority": rdata.preference,
                    "hostname": str(rdata.exchange).rstrip("."),
                })
        except Exception:
            pass

        # SPF (TXT records matching v=spf1)
        try:
            for rdata in dns.resolver.resolve(input_value, "TXT"):
                txt = b"".join(rdata.strings).decode("utf-8", errors="replace")
                if txt.startswith("v=spf1"):
                    spf_record = txt
                    break
        except Exception:
            pass

        # DMARC (_dmarc.<domain> TXT)
        try:
            for rdata in dns.resolver.resolve(f"_dmarc.{input_value}", "TXT"):
                txt = b"".join(rdata.strings).decode("utf-8", errors="replace")
                if txt.startswith("v=DMARC1"):
                    dmarc_record = txt
                    break
        except Exception:
            pass

        # DKIM (default._domainkey.<domain> TXT)
        try:
            dns.resolver.resolve(f"default._domainkey.{input_value}", "TXT")
            dkim_found = True
        except Exception:
            pass

        spf_parsed = _parse_spf(spf_record) if spf_record else {"mechanisms": [], "all_qualifier": "?"}
        dmarc_parsed = _parse_dmarc(dmarc_record) if dmarc_record else {}
        dmarc_policy = dmarc_parsed.get("p", "none")

        score = _email_security_score(
            spf_found=spf_record is not None,
            spf_all=spf_parsed["all_qualifier"],
            dmarc_found=dmarc_record is not None,
            dmarc_policy=dmarc_policy,
            dkim_found=dkim_found,
        )

        findings: list[str] = []
        if not spf_record:
            findings.append("No SPF record found — domain is vulnerable to email spoofing")
        elif spf_parsed["all_qualifier"] not in ("-all", "~all"):
            findings.append("SPF uses weak or missing 'all' qualifier")
        if not dmarc_record:
            findings.append("No DMARC record found — no email authentication policy enforced")
        elif dmarc_policy == "none":
            findings.append("DMARC policy is 'none' — emails not rejected or quarantined")
        if not dkim_found:
            findings.append("Default DKIM selector not found")

        identifiers = [f"domain:{mx['hostname']}" for mx in mx_records]

        return {
            "domain": input_value,
            "found": bool(mx_records or spf_record or dmarc_record),
            "mx_records": mx_records,
            "spf_record": spf_record,
            "spf_mechanisms": spf_parsed["mechanisms"],
            "spf_all_qualifier": spf_parsed["all_qualifier"],
            "dmarc_record": dmarc_record,
            "dmarc_policy": dmarc_policy,
            "dmarc_pct": dmarc_parsed.get("pct", "100"),
            "dmarc_rua": dmarc_parsed.get("rua"),
            "dkim_found": dkim_found,
            "email_security_score": score,
            "findings": findings,
            "extracted_identifiers": identifiers,
        }
