"""AWS IAM Auditor — checks for AWS infrastructure exposure related to the target domain.

Module 102 in the Infrastructure & Exploitation domain. Probes the target domain for
indicators of AWS exposure: open S3 buckets with domain-based names, public CloudFront
distributions, and metadata service accessibility hints. Does NOT attempt actual SSRF
against 169.254.169.254 — that would require being inside the target network. Instead,
checks publicly observable AWS footprints related to the domain.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_S3_BUCKET_TEMPLATES = [
    "{base}",
    "{base}-backup",
    "{base}-data",
    "{base}-static",
    "{base}-assets",
    "{base}-media",
    "{base}-prod",
    "{base}-dev",
    "{base}-staging",
    "{base}-logs",
    "{base}-config",
    "{base}-private",
    "{base}-public",
]

_CLOUDFRONT_INDICATORS = [
    "cloudfront.net",
    "X-Cache",
    "x-amz-cf-id",
    "x-amz-cf-pop",
    "Via: 1.1 CloudFront",
]

_AWS_HEADER_INDICATORS = [
    "x-amz-request-id",
    "x-amz-id-2",
    "x-amz-bucket-region",
    "x-amzn-requestid",
    "x-amzn-trace-id",
]

_S3_XML_SIGNATURES = ["ListBucketResult", "NoSuchBucket", "AccessDenied", "<Error><Code>", "amazonaws.com"]

_RE_AWS_ACCOUNT_ID = re.compile(r"\b\d{12}\b")
_RE_AKIA = re.compile(r"AKIA[0-9A-Z]{16}")


def _extract_domain_base(domain: str) -> str:
    domain = domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    parts = domain.split(".")
    return parts[-2] if len(parts) >= 2 else parts[0]


async def _probe_s3_bucket(client: httpx.AsyncClient, bucket: str) -> dict[str, Any] | None:
    """Check if an S3 bucket exists and its access level."""
    for url in [
        f"https://{bucket}.s3.amazonaws.com/",
        f"https://s3.amazonaws.com/{bucket}/",
    ]:
        try:
            resp = await client.get(url, timeout=8)
            body = resp.text
            if any(sig in body for sig in _S3_XML_SIGNATURES) or resp.status_code in (200, 403):
                is_public = resp.status_code == 200 and "ListBucketResult" in body
                exists = "NoSuchBucket" not in body and resp.status_code != 404
                if exists or resp.status_code == 403:
                    return {
                        "bucket": bucket,
                        "url": url,
                        "status_code": resp.status_code,
                        "public_listing": is_public,
                        "access_denied": resp.status_code == 403,
                        "exists": exists,
                        "risk": "Critical" if is_public else "Medium",
                    }
        except (httpx.RequestError, httpx.TimeoutException):
            pass
    return None


async def _check_cloudfront(client: httpx.AsyncClient, target_url: str) -> dict[str, Any]:
    """Check if the target domain is served via CloudFront."""
    result: dict[str, Any] = {
        "cloudfront_detected": False,
        "headers_found": [],
        "distribution_domain": "",
    }
    try:
        resp = await client.get(target_url, timeout=10)
        for indicator in _CLOUDFRONT_INDICATORS:
            if indicator in resp.headers.get("via", "") or indicator in str(resp.headers):
                result["cloudfront_detected"] = True
                result["headers_found"].append(indicator)

        # Look for CloudFront domain in CNAME or response
        cf_id = resp.headers.get("x-amz-cf-id", "")
        if cf_id:
            result["cloudfront_detected"] = True
            result["cf_request_id"] = cf_id[:20] + "***"
    except (httpx.RequestError, httpx.TimeoutException):
        pass
    return result


async def _check_aws_headers(client: httpx.AsyncClient, target_url: str) -> list[str]:
    """Check response headers for AWS service indicators."""
    found: list[str] = []
    try:
        resp = await client.get(target_url, timeout=10)
        for indicator in _AWS_HEADER_INDICATORS:
            if indicator in resp.headers:
                found.append(f"{indicator}: {resp.headers[indicator][:30]}***")
    except (httpx.RequestError, httpx.TimeoutException):
        pass
    return found


class AWSIAMAuditorScanner(BaseOsintScanner):
    """Checks for AWS infrastructure exposure associated with the target domain.

    Probes domain-based S3 bucket name variations, detects CloudFront distribution
    usage, and identifies AWS service response headers. Educational tool for
    understanding AWS footprint enumeration (Module 102). Does not perform SSRF
    or attempt metadata service access.
    """

    scanner_name = "aws_iam_auditor"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain_base = _extract_domain_base(input_value)
        target_url = f"https://{input_value.strip().lstrip('https://').lstrip('http://')}"
        if not target_url.startswith("https://"):
            target_url = f"https://{input_value.strip()}"

        bucket_names = [tmpl.format(base=domain_base) for tmpl in _S3_BUCKET_TEMPLATES]

        s3_findings: list[dict[str, Any]] = []
        cloudfront_info: dict[str, Any] = {}
        aws_headers: list[str] = []

        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            # Check S3 buckets in parallel
            s3_tasks = [_probe_s3_bucket(client, bucket) for bucket in bucket_names]
            s3_results = await asyncio.gather(*s3_tasks, return_exceptions=True)
            for result in s3_results:
                if isinstance(result, dict):
                    s3_findings.append(result)

            # Check CloudFront and AWS headers
            cloudfront_info, aws_headers = await asyncio.gather(
                _check_cloudfront(client, target_url),
                _check_aws_headers(client, target_url),
                return_exceptions=False,
            )

        public_buckets = [f for f in s3_findings if f.get("public_listing")]
        aws_footprint_detected = bool(s3_findings or cloudfront_info.get("cloudfront_detected") or aws_headers)

        severity = "None"
        if public_buckets:
            severity = "Critical"
        elif s3_findings or cloudfront_info.get("cloudfront_detected"):
            severity = "Medium"
        elif aws_headers:
            severity = "Low"

        return {
            "target": input_value,
            "domain_base": domain_base,
            "found": aws_footprint_detected,
            "severity": severity,
            "s3_buckets": {
                "tested": len(bucket_names),
                "found": len(s3_findings),
                "public": len(public_buckets),
                "findings": s3_findings,
            },
            "cloudfront": cloudfront_info,
            "aws_response_headers": aws_headers,
            "educational_note": (
                "AWS footprint enumeration reveals cloud infrastructure used by the target. "
                "Public S3 buckets are a leading cause of data breaches. CloudFront origin "
                "exposure and metadata service SSRF are critical attack vectors in AWS environments."
            ),
            "recommendations": [
                "Enable S3 Block Public Access at the account level.",
                "Review S3 bucket policies and ACLs for unintended public access.",
                "Implement IMDSv2 (Instance Metadata Service v2) to prevent SSRF attacks against EC2 metadata.",
                "Use AWS Config rules to continuously audit S3 bucket permissions.",
                "Enable CloudTrail for audit logging of all API actions.",
            ],
        }
