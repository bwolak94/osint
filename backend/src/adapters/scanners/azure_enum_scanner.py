"""Azure AD / Office 365 Enumeration — tenant and user discovery scanner.

Enumerates Azure Active Directory tenants, domains, users, and exposed
cloud assets via Microsoft's public APIs and endpoints that don't require
authentication: tenant discovery, user enumeration via timing/error analysis,
Office 365 geolocation, and Azure subdomain discovery.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Microsoft public tenant discovery endpoints (no auth required)
_TENANT_DISCOVERY_URLS: list[str] = [
    "https://login.microsoftonline.com/{domain}/.well-known/openid-configuration",
    "https://login.microsoftonline.com/{domain}/v2.0/.well-known/openid-configuration",
    "https://login.windows.net/{domain}/.well-known/openid-configuration",
]

# Office 365 geolocation/tenant info
_O365_INFO_URLS: list[str] = [
    "https://autodiscover-s.outlook.com/autodiscover/autodiscover.svc",
    "https://login.microsoftonline.com/getuserrealm.srf?login=user@{domain}&json=1",
    "https://outlook.office365.com/autodiscover/autodiscover.json?Email=user@{domain}",
]

# Azure blob storage patterns
_AZURE_STORAGE_TEMPLATES: list[str] = [
    "https://{name}.blob.core.windows.net",
    "https://{name}.file.core.windows.net",
    "https://{name}.queue.core.windows.net",
    "https://{name}.table.core.windows.net",
]

# Azure AD common username formats to enumerate
_USERNAME_FORMATS: list[str] = [
    "admin",
    "administrator",
    "sysadmin",
    "info",
    "support",
    "helpdesk",
    "noreply",
    "service",
]

# Azure AD user enumeration endpoint (returns different errors for valid/invalid users)
_AZURE_USER_ENUM_URL = "https://login.microsoftonline.com/common/GetCredentialType"

# Azure subdomain prefixes commonly used
_AZURE_SUBDOMAINS: list[str] = [
    "",           # domain itself
    "mail",
    "remote",
    "vpn",
    "portal",
    "login",
    "sso",
    "auth",
    "admin",
    "app",
    "api",
]


class AzureEnumScanner(BaseOsintScanner):
    """Azure AD and Office 365 enumeration scanner.

    Discovers: tenant IDs, federated domains, O365 geolocation, Azure storage
    accounts, and valid user accounts via unauthenticated Microsoft API endpoints.
    """

    scanner_name = "azure_enum"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 7200
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().lower()
        return await self._manual_scan(domain)

    async def _manual_scan(self, domain: str) -> dict[str, Any]:
        tenant_info: dict[str, Any] = {}
        o365_info: dict[str, Any] = {}
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        valid_users: list[str] = []
        exposed_storage: list[str] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AzureEnumScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            # Step 1: Tenant discovery
            for url_template in _TENANT_DISCOVERY_URLS:
                url = url_template.replace("{domain}", domain)
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        import json as _json
                        try:
                            data = _json.loads(resp.text)
                            tenant_id_match = re.search(
                                r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
                                resp.text,
                            )
                            tenant_info = {
                                "tenant_id": tenant_id_match.group(1) if tenant_id_match else None,
                                "issuer": data.get("issuer"),
                                "authorization_endpoint": data.get("authorization_endpoint"),
                                "token_endpoint": data.get("token_endpoint"),
                                "discovery_url": url,
                            }
                            identifiers.append("info:azure:tenant_discovered")
                        except Exception:
                            pass
                        break
                except Exception:
                    pass

            # Step 2: O365 geolocation and realm info
            o365_realm_url = f"https://login.microsoftonline.com/getuserrealm.srf?login=probe@{domain}&json=1"
            try:
                resp = await client.get(o365_realm_url)
                if resp.status_code == 200:
                    import json as _json
                    try:
                        realm = _json.loads(resp.text)
                        o365_info = {
                            "name_space_type": realm.get("NameSpaceType"),
                            "federation_brand_name": realm.get("FederationBrandName"),
                            "cloud_instance_name": realm.get("CloudInstanceName"),
                            "domain_name": realm.get("DomainName"),
                            "is_federated": realm.get("NameSpaceType") == "Federated",
                            "federation_protocol": realm.get("FederationProtocol"),
                        }
                        # Federated = SSO/ADFS — useful for attackers
                        if o365_info.get("is_federated"):
                            identifiers.append("info:azure:federated_domain")
                    except Exception:
                        pass
            except Exception:
                pass

            # Step 3: Azure user enumeration via GetCredentialType
            # Different "IfExistsResult" values reveal valid accounts
            async def enum_user(username: str) -> None:
                async with semaphore:
                    email = f"{username}@{domain}"
                    try:
                        resp = await client.post(
                            _AZURE_USER_ENUM_URL,
                            json={
                                "Username": email,
                                "isOtherIdpSupported": True,
                                "checkPhones": False,
                                "isRemoteNGCSupported": True,
                                "isCookieBannerShown": False,
                                "isFidoSupported": False,
                                "originalRequest": "",
                            },
                        )
                        if resp.status_code == 200:
                            import json as _json
                            try:
                                data = _json.loads(resp.text)
                                # IfExistsResult: 0=unknown, 1=exists, 5=exists(different tenant), 6=exists(federated)
                                if_exists = data.get("IfExistsResult", 0)
                                if if_exists in (1, 5, 6):
                                    valid_users.append(email)
                            except Exception:
                                pass
                    except Exception:
                        pass

            if tenant_info or o365_info:
                # Only enumerate if Azure tenant confirmed
                await asyncio.gather(*[enum_user(u) for u in _USERNAME_FORMATS])

            # Step 4: Azure storage enumeration
            domain_parts = domain.split(".")
            storage_names = [
                domain_parts[0],
                domain.replace(".", ""),
                domain_parts[0].replace("-", ""),
            ]

            async def check_storage(name: str, template: str) -> None:
                async with semaphore:
                    url = template.replace("{name}", name)
                    try:
                        resp = await client.get(url)
                        if resp.status_code in (200, 403, 400):
                            # 403 = exists but private, 400 = may exist but no container in path
                            exposed_storage.append(url)
                            if resp.status_code == 200:
                                vulnerabilities.append({
                                    "type": "azure_storage_public",
                                    "severity": "high",
                                    "url": url,
                                    "description": "Azure storage account publicly accessible",
                                    "remediation": "Set container access to private; use SAS tokens for authenticated access",
                                })
                                identifiers.append("vuln:azure:public_storage")
                    except Exception:
                        pass

            storage_tasks = []
            for name in storage_names[:3]:
                for template in _AZURE_STORAGE_TEMPLATES[:2]:
                    storage_tasks.append(check_storage(name, template))
            await asyncio.gather(*storage_tasks)

            # Step 5: Report valid users
            if valid_users:
                vulnerabilities.append({
                    "type": "azure_ad_user_enumeration",
                    "severity": "medium",
                    "valid_users": valid_users,
                    "count": len(valid_users),
                    "description": f"Azure AD user enumeration via GetCredentialType API — {len(valid_users)} valid accounts found",
                    "remediation": "Cannot be fully mitigated (Microsoft design); enforce MFA and monitor sign-in logs",
                })
                identifiers.append("vuln:azure:user_enumeration")

        return {
            "input": domain,
            "scan_mode": "manual_fallback",
            "azure_tenant": tenant_info,
            "o365_realm": o365_info,
            "azure_detected": bool(tenant_info or o365_info),
            "valid_users_found": valid_users,
            "exposed_storage": exposed_storage,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
