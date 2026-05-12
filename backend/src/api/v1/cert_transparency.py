from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import random
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/cert-transparency", tags=["cert-transparency"])

class CertRecord(BaseModel):
    id: str
    common_name: str
    san_domains: list[str]
    issuer: str
    not_before: str
    not_after: str
    serial_number: str
    fingerprint_sha256: str
    ct_logs: list[str]
    is_wildcard: bool
    is_expired: bool
    days_until_expiry: Optional[int]

class CertTransparencyResult(BaseModel):
    query: str
    total_certs: int
    wildcard_count: int
    expiring_soon: int
    expired_count: int
    certs: list[CertRecord]

@router.get("/search", response_model=CertTransparencyResult)
async def search_certificates(domain: str, include_subdomains: bool = True, limit: int = 50):
    issuers = ["Let's Encrypt Authority X3", "DigiCert SHA2 Secure Server CA", "Sectigo RSA Domain Validation", "Amazon RSA 2048 M02", "Google Trust Services LLC"]
    ct_logs = ["Google Argon2024", "Cloudflare Nimbus2024", "DigiCert Yeti2024", "Let's Encrypt Oak2024"]

    certs = []
    subdomains = ["www", "mail", "api", "admin", "dev", "staging", "app", "cdn", "static", "blog", "shop", "vpn", "remote", "portal"]

    for i in range(random.randint(8, 25)):
        is_wildcard = random.random() < 0.2
        sub = random.choice(subdomains) if not is_wildcard else "*"
        cn = f"{sub}.{domain}" if random.random() > 0.3 else domain
        not_before = datetime.utcnow() - timedelta(days=random.randint(1, 400))
        days_valid = random.randint(30, 398)
        not_after = not_before + timedelta(days=days_valid)
        is_expired = not_after < datetime.utcnow()
        days_until = int((not_after - datetime.utcnow()).days) if not is_expired else None

        certs.append(CertRecord(
            id=f"cert_{i}",
            common_name=cn,
            san_domains=[cn, f"www.{domain}"] if not is_wildcard else [f"*.{domain}", domain],
            issuer=random.choice(issuers),
            not_before=not_before.isoformat(),
            not_after=not_after.isoformat(),
            serial_number=f"{random.randint(0, 0xFFFFFFFFFFFF):012X}",
            fingerprint_sha256=f"{''.join([f'{random.randint(0,255):02X}' for _ in range(32)])}",
            ct_logs=random.sample(ct_logs, random.randint(1, 3)),
            is_wildcard=is_wildcard,
            is_expired=is_expired,
            days_until_expiry=days_until
        ))

    return CertTransparencyResult(
        query=domain,
        total_certs=len(certs),
        wildcard_count=sum(1 for c in certs if c.is_wildcard),
        expiring_soon=sum(1 for c in certs if c.days_until_expiry is not None and c.days_until_expiry < 30),
        expired_count=sum(1 for c in certs if c.is_expired),
        certs=certs[:limit]
    )
