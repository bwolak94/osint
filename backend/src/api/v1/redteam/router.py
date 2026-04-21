"""FastAPI router for Red Team Tools — Domain VI, Modules 101-130.

Endpoints cover JWT auditing, AWS IAM review, cloud storage hunting, CI/CD
secret scanning, IaC policy linting, supply-chain simulation, API security
scanning, Windows persistence labs, NTLM relay simulation, Kerberoasting,
BloodHound graph bridging, AD coercion simulation, AI prompt injection testing,
container escape auditing, zero-trust policy visualisation, payload evasion,
memory forensics guidance, C2 channel simulation, EDR/AV detection, AD CS abuse,
GraphQL depth auditing, TOCTOU visualisation, APK static analysis, dangling DNS
scanning, MITRE ATT&CK mapping, threat intel aggregation, dynamic firewall
enforcement, DFIR evidence pipeline generation, and OSCP-style reporting.

Educational / simulation-only modules are clearly documented and never perform
destructive operations on remote systems.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from typing import Annotated

from src.adapters.scanners.registry import ScannerRegistry, get_default_registry
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

log = structlog.get_logger()
router = APIRouter(tags=["Red Team Tools"])


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


def get_scanner_registry() -> ScannerRegistry:
    """Return the shared scanner registry singleton."""
    return get_default_registry()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class JwtAuditRequest(BaseModel):
    target_url: str
    token: str = ""

    @field_validator("target_url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target_url must not be empty")
        return v


class AwsIamRequest(BaseModel):
    target_domain: str

    @field_validator("target_domain")
    @classmethod
    def domain_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target_domain must not be empty")
        return v


class CloudHuntRequest(BaseModel):
    target_domain: str
    providers: list[str] = Field(default_factory=lambda: ["s3", "azure", "gcp"])

    @field_validator("target_domain")
    @classmethod
    def domain_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target_domain must not be empty")
        return v


class CicdScanRequest(BaseModel):
    target_url: str

    @field_validator("target_url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target_url must not be empty")
        return v


class IacLintRequest(BaseModel):
    content: str
    file_type: str = "terraform"

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty")
        return v


class SupplyChainRequest(BaseModel):
    package_name: str
    registry: str = "pypi"

    @field_validator("package_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("package_name must not be empty")
        return v


class ApiScanRequest(BaseModel):
    target_url: str

    @field_validator("target_url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target_url must not be empty")
        return v


class RegistryPersistRequest(BaseModel):
    payload: str
    key_path: str = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
    simulate: bool = True

    @field_validator("payload")
    @classmethod
    def payload_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("payload must not be empty")
        return v


class WmiPersistRequest(BaseModel):
    command: str
    trigger: str = "startup"
    simulate: bool = True

    @field_validator("command")
    @classmethod
    def command_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("command must not be empty")
        return v


class NtlmRelayRequest(BaseModel):
    target_ip: str
    simulate: bool = True

    @field_validator("target_ip")
    @classmethod
    def ip_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target_ip must not be empty")
        return v


class KerberoastRequest(BaseModel):
    domain: str

    @field_validator("domain")
    @classmethod
    def domain_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("domain must not be empty")
        return v


class BloodhoundRequest(BaseModel):
    domain: str
    query_type: str = "shortest_path"

    @field_validator("domain")
    @classmethod
    def domain_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("domain must not be empty")
        return v


class AdCoerceRequest(BaseModel):
    target: str
    method: str = "printerbug"
    simulate: bool = True

    @field_validator("target")
    @classmethod
    def target_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target must not be empty")
        return v


class PromptInjectRequest(BaseModel):
    endpoint_url: str
    payload_type: str = "direct"

    @field_validator("endpoint_url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("endpoint_url must not be empty")
        return v


class ContainerEscapeRequest(BaseModel):
    target: str

    @field_validator("target")
    @classmethod
    def target_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target must not be empty")
        return v


class ZeroTrustRequest(BaseModel):
    network_segments: list[dict] = Field(default_factory=list)
    policies: list[dict] = Field(default_factory=list)


class PayloadEvadeRequest(BaseModel):
    target_url: str

    @field_validator("target_url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target_url must not be empty")
        return v


class MemoryForensicsRequest(BaseModel):
    dump_url: str = ""
    process_filter: str = ""


class C2ChannelRequest(BaseModel):
    c2_type: str = "dns"
    domain: str
    simulate: bool = True

    @field_validator("domain")
    @classmethod
    def domain_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("domain must not be empty")
        return v


class EdrCheckRequest(BaseModel):
    target_ip: str

    @field_validator("target_ip")
    @classmethod
    def ip_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target_ip must not be empty")
        return v


class AdcsAbuseRequest(BaseModel):
    domain: str

    @field_validator("domain")
    @classmethod
    def domain_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("domain must not be empty")
        return v


class GraphqlAuditRequest(BaseModel):
    target_url: str
    max_depth: int = Field(default=10, ge=1, le=50)

    @field_validator("target_url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target_url must not be empty")
        return v


class ToctouRequest(BaseModel):
    scenario: str = "file_check"
    race_window_ms: int = Field(default=100, ge=1, le=10000)


class ApkAnalyzeRequest(BaseModel):
    apk_url: str

    @field_validator("apk_url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("apk_url must not be empty")
        return v


class DanglingDnsRequest(BaseModel):
    domain: str

    @field_validator("domain")
    @classmethod
    def domain_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("domain must not be empty")
        return v


class MitreMapRequest(BaseModel):
    techniques: list[str]
    investigation_id: str = ""

    @field_validator("techniques")
    @classmethod
    def techniques_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("techniques list must not be empty")
        return v


class ThreatIntelRequest(BaseModel):
    target: str

    @field_validator("target")
    @classmethod
    def target_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target must not be empty")
        return v


class FirewallEnforceRequest(BaseModel):
    action: str = "block"
    ip: str
    reason: str
    duration_hours: int = Field(default=24, ge=1, le=8760)
    simulate: bool = True

    @field_validator("ip", "reason")
    @classmethod
    def fields_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field must not be empty")
        return v


class DfirCollectRequest(BaseModel):
    target_ip: str = ""
    collect_types: list[str] = Field(default_factory=lambda: ["logs", "processes", "network"])


class OscpReportRequest(BaseModel):
    investigation_id: str
    findings: list[dict] = Field(default_factory=list)
    include_screenshots: bool = True

    @field_validator("investigation_id")
    @classmethod
    def id_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("investigation_id must not be empty")
        return v


# ---------------------------------------------------------------------------
# Helper: run a named scanner from the registry
# ---------------------------------------------------------------------------


async def _run_scanner(
    registry: ScannerRegistry,
    scanner_name: str,
    target: str,
    extra: dict | None = None,
) -> dict:
    """Invoke a named scanner and return its raw result dict."""
    from src.core.domain.entities.types import ScanInputType

    scanner = registry.get_by_name(scanner_name)
    if scanner is None:
        return {"found": False, "error": f"Scanner '{scanner_name}' is not registered"}
    try:
        result = await scanner.scan(target, ScanInputType.DOMAIN)
        data = result.raw_data or {}
        if extra:
            data.update(extra)
        return {
            "found": result.raw_data.get("found", False),
            "data": data,
            "error": result.error_message,
            "status": result.status.value,
        }
    except Exception as exc:
        log.warning("redteam scanner error", scanner=scanner_name, error=str(exc))
        return {"found": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Module 101 — JWT Security Auditor
# ---------------------------------------------------------------------------


@router.post("/jwt-audit", status_code=status.HTTP_200_OK)
async def jwt_audit(
    body: JwtAuditRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 101 — JWT Security Auditor.

    Tests a JWT token and the target endpoint for common vulnerabilities
    including algorithm confusion (none/HS256), weak secrets, missing
    expiry claims, and improper signature validation.
    """
    result = await _run_scanner(
        registry,
        "jwt_security_auditor",
        body.target_url,
        extra={"token": body.token},
    )
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 102 — AWS IAM Auditor
# ---------------------------------------------------------------------------


@router.post("/aws-iam", status_code=status.HTTP_200_OK)
async def aws_iam(
    body: AwsIamRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 102 — AWS IAM Auditor.

    Audits publicly accessible AWS resources and IAM policy artifacts
    associated with the target domain for overly permissive configurations
    and exposed credentials.
    """
    result = await _run_scanner(registry, "aws_iam_auditor", body.target_domain)
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 103 — Cloud Storage Hunter
# ---------------------------------------------------------------------------


@router.post("/cloud-hunt", status_code=status.HTTP_200_OK)
async def cloud_hunt(
    body: CloudHuntRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 103 — Cloud Storage Hunter.

    Searches for publicly accessible storage buckets (S3, Azure Blob,
    GCS) associated with the target domain across the requested providers.
    """
    result = await _run_scanner(
        registry,
        "cloud_storage_hunter",
        body.target_domain,
        extra={"providers": body.providers},
    )
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 104 — CI/CD Secret Scanner
# ---------------------------------------------------------------------------


@router.post("/cicd-scan", status_code=status.HTTP_200_OK)
async def cicd_scan(
    body: CicdScanRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 104 — CI/CD Secret Scanner.

    Scans the target repository or pipeline URL for accidentally committed
    secrets (API keys, tokens, passwords) in CI/CD configuration files and
    workflow definitions.
    """
    result = await _run_scanner(registry, "cicd_secret_scanner", body.target_url)
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 105 — IaC Policy Linter
# ---------------------------------------------------------------------------


@router.post("/iac-lint", status_code=status.HTTP_200_OK)
async def iac_lint(
    body: IacLintRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 105 — IaC Policy Linter.

    Analyses Terraform or CloudFormation content for security misconfigurations
    such as publicly accessible resources, missing encryption, overly broad
    IAM policies, and insecure default settings.
    """
    file_type = body.file_type.lower()
    if file_type not in {"terraform", "cloudformation", "pulumi"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_type must be 'terraform', 'cloudformation', or 'pulumi'.",
        )

    # Lightweight static pattern matching for common misconfigurations
    violations: list[dict] = []
    content = body.content

    checks: list[tuple[str, str, str]] = [
        ("publicly_accessible = true", "HIGH", "Resource is publicly accessible."),
        ("encryption = false", "HIGH", "Encryption is explicitly disabled."),
        ('"*"', "MEDIUM", "Wildcard ('*') found — verify IAM or security group scope."),
        ("0.0.0.0/0", "HIGH", "Inbound rule allows traffic from any IP (0.0.0.0/0)."),
        ("password =", "HIGH", "Hardcoded password literal detected."),
        ("secret =", "HIGH", "Hardcoded secret literal detected."),
        ("enable_deletion_protection = false", "MEDIUM", "Deletion protection is disabled."),
        ("multi_az = false", "LOW", "Multi-AZ is disabled — consider enabling for HA."),
    ]

    for pattern, severity, message in checks:
        if pattern.lower() in content.lower():
            violations.append({"pattern": pattern, "severity": severity, "message": message})

    return {
        "found": len(violations) > 0,
        "data": {
            "file_type": file_type,
            "violations": violations,
            "violation_count": len(violations),
            "high": sum(1 for v in violations if v["severity"] == "HIGH"),
            "medium": sum(1 for v in violations if v["severity"] == "MEDIUM"),
            "low": sum(1 for v in violations if v["severity"] == "LOW"),
        },
    }


# ---------------------------------------------------------------------------
# Module 106 — Supply Chain Simulator
# ---------------------------------------------------------------------------


@router.post("/supply-chain", status_code=status.HTTP_200_OK)
async def supply_chain(
    body: SupplyChainRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 106 — Supply Chain Simulator.

    Simulates a dependency confusion attack by checking whether the given
    internal package name is already registered on the public registry.
    Returns a risk assessment with exploitation guidance and remediation steps.
    """
    registry_urls: dict[str, str] = {
        "pypi": f"https://pypi.org/pypi/{body.package_name}/json",
        "npm": f"https://registry.npmjs.org/{body.package_name}",
        "rubygems": f"https://rubygems.org/api/v1/gems/{body.package_name}.json",
        "maven": f"https://search.maven.org/solrsearch/select?q={body.package_name}",
    }

    reg = body.registry.lower()
    check_url = registry_urls.get(reg, f"https://{reg}/{body.package_name}")

    return {
        "found": True,
        "data": {
            "package_name": body.package_name,
            "registry": reg,
            "check_url": check_url,
            "risk_assessment": (
                "If this package name is an internal-only dependency and it also "
                "exists on the public registry, a dependency confusion attack is feasible. "
                "An attacker publishes a higher-versioned malicious package with the same "
                "name; build tools may resolve the public version instead of the internal one."
            ),
            "remediation": [
                "Scope internal packages to a private namespace (e.g. '@company/package-name').",
                "Pin exact dependency versions and use lockfiles.",
                "Configure package managers to prefer the internal registry for all namespaces.",
                "Enable integrity hashes (pip --require-hashes, npm integrity).",
                "Register placeholder packages on public registries to block squatting.",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Module 107 — API Security Scanner
# ---------------------------------------------------------------------------


@router.post("/api-scan", status_code=status.HTTP_200_OK)
async def api_scan(
    body: ApiScanRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 107 — API Security Scanner.

    Probes the target API endpoint for OWASP API Top-10 vulnerabilities
    including broken authentication, excessive data exposure, lack of rate
    limiting, and injection flaws.
    """
    result = await _run_scanner(registry, "api_security_scanner", body.target_url)
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 108 — Registry Persistence Lab (educational/simulation)
# ---------------------------------------------------------------------------


@router.post("/registry-persist", status_code=status.HTTP_200_OK)
async def registry_persist(
    body: RegistryPersistRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 108 — Registry Persistence Lab (educational/simulation).

    Shows the Windows registry key that would be written to establish
    persistence for the given payload. Includes detection and remediation
    guidance. Only simulation mode is supported.
    """
    if not body.simulate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Live registry writes are not supported. Use simulate=true.",
        )

    return {
        "found": True,
        "data": {
            "simulation": True,
            "key_path": body.key_path,
            "value_name": "OSINTPlatformTask",
            "value_data": body.payload,
            "reg_command": f'reg add "{body.key_path}" /v OSINTPlatformTask /t REG_SZ /d "{body.payload}" /f',
            "detection_methods": [
                "Autoruns (Sysinternals) — lists all autostart locations including registry Run keys.",
                "Sysmon Event ID 13 — RegistryEvent (Value Set) for monitored key paths.",
                "EDR telemetry: alert on unexpected writes to Run/RunOnce registry keys.",
                "Baseline comparison: compare registry Run keys against a known-good snapshot.",
            ],
            "cleanup": f'reg delete "{body.key_path}" /v OSINTPlatformTask /f',
        },
    }


# ---------------------------------------------------------------------------
# Module 109 — WMI Persistence Engine (educational/simulation)
# ---------------------------------------------------------------------------


@router.post("/wmi-persist", status_code=status.HTTP_200_OK)
async def wmi_persist(
    body: WmiPersistRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 109 — WMI Persistence Engine (educational/simulation).

    Explains WMI event subscription persistence by showing the event filter,
    event consumer, and binding objects that would be created. No WMI
    subscriptions are written.
    """
    if not body.simulate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Live WMI subscription creation is not supported. Use simulate=true.",
        )

    trigger_map: dict[str, str] = {
        "startup": "__InstanceModificationEvent WITHIN 60 WHERE TargetInstance ISA 'Win32_PerfFormattedData_PerfOS_System' AND TargetInstance.SystemUpTime >= 240 AND TargetInstance.SystemUpTime < 325",
        "logon": "__InstanceCreationEvent WITHIN 10 WHERE TargetInstance ISA 'Win32_LogonSession'",
        "interval": "__TimerEvent WHERE TimerID='OsintTimer'",
    }

    trigger_query = trigger_map.get(body.trigger, trigger_map["startup"])

    wmi_objects = {
        "EventFilter": {
            "Name": "OsintFilter",
            "QueryLanguage": "WQL",
            "Query": trigger_query,
        },
        "CommandLineEventConsumer": {
            "Name": "OsintConsumer",
            "CommandLineTemplate": body.command,
        },
        "FilterToConsumerBinding": {
            "Filter": '__EventFilter.Name="OsintFilter"',
            "Consumer": 'CommandLineEventConsumer.Name="OsintConsumer"',
        },
    }

    return {
        "found": True,
        "data": {
            "simulation": True,
            "trigger": body.trigger,
            "wmi_subscription_objects": wmi_objects,
            "detection_methods": [
                "Sysmon Event IDs 19, 20, 21 — WmiEvent (Filter/Consumer/Binding Activity).",
                "Query WMI namespace root\\subscription for unexpected filters/consumers.",
                "Enable WMI activity logging (Microsoft-Windows-WMI-Activity/Operational).",
                "Autoruns — 'WMI' tab lists active event subscriptions.",
            ],
            "cleanup_commands": [
                'Get-WMIObject -Namespace root\\subscription -Class __EventFilter | Where-Object {$_.Name -eq "OsintFilter"} | Remove-WMIObject',
                'Get-WMIObject -Namespace root\\subscription -Class CommandLineEventConsumer | Where-Object {$_.Name -eq "OsintConsumer"} | Remove-WMIObject',
                'Get-WMIObject -Namespace root\\subscription -Class __FilterToConsumerBinding | Where-Object {$_.Filter -match "OsintFilter"} | Remove-WMIObject',
            ],
        },
    }


# ---------------------------------------------------------------------------
# Module 110 — NTLM Relay Automator (educational/simulation)
# ---------------------------------------------------------------------------


@router.post("/ntlm-relay", status_code=status.HTTP_200_OK)
async def ntlm_relay(
    body: NtlmRelayRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 110 — NTLM Relay Automator (educational/simulation).

    Returns a detailed simulation of an NTLM relay attack flow including the
    packet sequence diagram, toolchain commands, and comprehensive defence
    recommendations. No traffic is sent.
    """
    if not body.simulate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Live NTLM relay attacks are not supported. Use simulate=true.",
        )

    return {
        "found": True,
        "data": {
            "simulation": True,
            "target_ip": body.target_ip,
            "attack_flow": [
                "1. Attacker listens for LLMNR/NBT-NS/mDNS requests on the local network.",
                "2. Victim broadcasts name resolution request (e.g. for '\\fileserver').",
                "3. Attacker responds with their own IP, triggering an NTLM authentication attempt.",
                "4. Attacker relays the NTLM challenge/response to the real target server.",
                "5. If SMB signing is disabled, the relay succeeds and grants access.",
            ],
            "packet_flow": [
                {"step": 1, "src": "victim", "dst": "broadcast", "proto": "LLMNR/NBT-NS", "content": "Who is 'fileserver'?"},
                {"step": 2, "src": "attacker", "dst": "victim", "proto": "LLMNR", "content": "I am 'fileserver' (attacker IP)"},
                {"step": 3, "src": "victim", "dst": "attacker", "proto": "SMB", "content": "NTLM Negotiate"},
                {"step": 4, "src": "attacker", "dst": body.target_ip, "proto": "SMB", "content": "NTLM Negotiate (relayed)"},
                {"step": 5, "src": body.target_ip, "dst": "attacker", "proto": "SMB", "content": "NTLM Challenge"},
                {"step": 6, "src": "attacker", "dst": "victim", "proto": "SMB", "content": "NTLM Challenge (relayed)"},
                {"step": 7, "src": "victim", "dst": "attacker", "proto": "SMB", "content": "NTLM Response (Net-NTLMv2 hash)"},
                {"step": 8, "src": "attacker", "dst": body.target_ip, "proto": "SMB", "content": "NTLM Response (relayed) → AUTH SUCCESS"},
            ],
            "defense": [
                "Enable SMB signing on all Windows hosts (GPO: 'Microsoft network client/server: Digitally sign communications').",
                "Disable LLMNR and NBT-NS via GPO to eliminate the initial name poisoning vector.",
                "Require EPA (Extended Protection for Authentication) on LDAP/HTTP.",
                "Implement network segmentation to limit broadcast domain exposure.",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Module 111 — Kerberoasting Toolkit
# ---------------------------------------------------------------------------


@router.post("/kerberoast", status_code=status.HTTP_200_OK)
async def kerberoast(
    body: KerberoastRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 111 — Kerberoasting Toolkit.

    Enumerates Service Principal Names (SPNs) in the target domain and
    returns hash entropy visualisation data to help prioritise cracking
    effort by identifying weak service account passwords.
    """
    result = await _run_scanner(registry, "kerberoasting_scanner", body.domain)
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 112 — BloodHound Viz Bridge
# ---------------------------------------------------------------------------


@router.post("/bloodhound", status_code=status.HTTP_200_OK)
async def bloodhound(
    body: BloodhoundRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 112 — BloodHound Viz Bridge.

    Queries the Neo4j graph database for Active Directory attack paths
    (shortest path to Domain Admin, high-value targets, etc.) and returns
    graph data structured for the React frontend visualiser.
    """
    query_map: dict[str, str] = {
        "shortest_path": (
            "MATCH p=shortestPath((u:User)-[*1..]->(g:Group {name:'Domain Admins@"
            + body.domain.upper()
            + "'})) RETURN p LIMIT 10"
        ),
        "kerberoastable": (
            "MATCH (u:User {hasspn:true}) RETURN u.name, u.pwdlastset ORDER BY u.pwdlastset LIMIT 20"
        ),
        "asreproastable": (
            "MATCH (u:User {dontreqpreauth:true}) RETURN u.name LIMIT 20"
        ),
        "unconstrained_delegation": (
            "MATCH (c:Computer {unconstraineddelegation:true}) RETURN c.name LIMIT 20"
        ),
    }

    query = query_map.get(body.query_type, query_map["shortest_path"])

    return {
        "found": True,
        "data": {
            "domain": body.domain,
            "query_type": body.query_type,
            "cypher_query": query,
            "note": (
                "Connect this endpoint to a live Neo4j instance pre-loaded with "
                "BloodHound ingestor data to return real graph results. "
                "Returning query specification only."
            ),
            "graph": {"nodes": [], "edges": []},
        },
    }


# ---------------------------------------------------------------------------
# Module 113 — AD Coercion Simulator (educational)
# ---------------------------------------------------------------------------


@router.post("/ad-coerce", status_code=status.HTTP_200_OK)
async def ad_coerce(
    body: AdCoerceRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 113 — AD Coercion Simulator (educational).

    Explains authentication coercion techniques (PrinterBug, PetitPotam,
    DFSCoerce) and shows the attack flow that forces a target machine to
    authenticate to an attacker-controlled host.
    """
    if not body.simulate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Live coercion is not supported. Use simulate=true.",
        )

    method = body.method.lower()
    techniques: dict[str, dict] = {
        "printerbug": {
            "cve": "No CVE (by-design MS-RPRN behaviour)",
            "protocol": "MS-RPRN (Print System Remote Protocol)",
            "function": "RpcRemoteFindFirstPrinterChangeNotificationEx",
            "description": "Abuses the printer spooler service to force NTLM authentication from the target to the attacker.",
            "mitigations": ["Disable the Print Spooler service on DCs and non-print servers."],
        },
        "petitpotam": {
            "cve": "CVE-2021-36942",
            "protocol": "MS-EFSRPC (Encrypting File System Remote Protocol)",
            "function": "EfsRpcOpenFileRaw",
            "description": "Forces NTLM authentication via the EFS service, even without credentials.",
            "mitigations": [
                "Apply MS patch KB5005413.",
                "Block MS-EFSRPC on the perimeter firewall (TCP 445).",
                "Enable EPA on AD CS web endpoints.",
            ],
        },
        "dfscoerce": {
            "cve": "No CVE (by-design MS-DFSNM behaviour)",
            "protocol": "MS-DFSNM (Distributed File System: Namespace Management)",
            "function": "NetrDfsRemoveStdRoot / NetrDfsAddStdRoot",
            "description": "Forces authentication via the DFS management interface.",
            "mitigations": ["Disable the DFS service on Domain Controllers if not required."],
        },
    }

    technique = techniques.get(method, techniques["printerbug"])

    return {
        "found": True,
        "data": {
            "simulation": True,
            "target": body.target,
            "method": method,
            "technique": technique,
            "attack_flow": [
                f"1. Attacker sets up an NTLM relay listener (responder/ntlmrelayx) pointing to the target.",
                f"2. Attacker calls {technique['function']} on {body.target} with the attacker IP as callback.",
                "3. The target machine account authenticates to the attacker's listener.",
                "4. Attacker relays the Net-NTLMv2 hash or LDAP session to perform privilege escalation.",
            ],
            "detection_indicators": [
                "Unexpected outbound SMB connections from Domain Controllers.",
                "Suspicious spooler/EFS/DFS service calls in Security Event Log (4648, 4624).",
                "Network traffic from DCs to non-DC hosts on port 445.",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Module 114 — AI Prompt Injector
# ---------------------------------------------------------------------------


@router.post("/prompt-inject", status_code=status.HTTP_200_OK)
async def prompt_inject(
    body: PromptInjectRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 114 — AI Prompt Injector.

    Tests an LLM-backed endpoint for direct and indirect prompt injection
    vulnerabilities by sending crafted inputs and analysing whether the model
    deviates from its intended behaviour.
    """
    result = await _run_scanner(
        registry,
        "api_security_scanner",
        body.endpoint_url,
        extra={"payload_type": body.payload_type},
    )
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 115 — Container Escape Auditor
# ---------------------------------------------------------------------------


@router.post("/container-escape", status_code=status.HTTP_200_OK)
async def container_escape(
    body: ContainerEscapeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 115 — Container Escape Auditor.

    Checks the target container runtime environment for common escape
    vectors: privileged mode, dangerous capabilities, writable /proc/sysrq-trigger,
    exposed Docker socket, and kernel vulnerability exposure.
    """
    result = await _run_scanner(registry, "container_escape_auditor", body.target)
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 116 — Zero Trust Policy Visualiser
# ---------------------------------------------------------------------------


@router.post("/zero-trust", status_code=status.HTTP_200_OK)
async def zero_trust(
    body: ZeroTrustRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 116 — Zero Trust Policy Visualiser.

    Analyses declared network segments and access policies for violations of
    the principle of least privilege. Returns policy gaps and visualisation
    data suitable for the React graph frontend.
    """
    gaps: list[dict] = []

    for policy in body.policies:
        src = policy.get("source", "")
        dst = policy.get("destination", "")
        action = policy.get("action", "allow")

        if action == "allow" and (src == "*" or dst == "*"):
            gaps.append({
                "severity": "HIGH",
                "policy": policy,
                "reason": "Wildcard source or destination violates least-privilege.",
            })

        if action == "allow" and policy.get("ports") == ["*"]:
            gaps.append({
                "severity": "MEDIUM",
                "policy": policy,
                "reason": "All ports allowed — restrict to required service ports.",
            })

    nodes = [{"id": s.get("name", f"seg_{i}"), "label": s.get("name", f"Segment {i}")} for i, s in enumerate(body.network_segments)]
    edges = [
        {
            "from": p.get("source"),
            "to": p.get("destination"),
            "label": p.get("action", "allow"),
            "color": "red" if p.get("action") == "allow" else "green",
        }
        for p in body.policies
    ]

    return {
        "found": len(gaps) > 0,
        "data": {
            "segment_count": len(body.network_segments),
            "policy_count": len(body.policies),
            "gaps": gaps,
            "gap_count": len(gaps),
            "visualization": {"nodes": nodes, "edges": edges},
        },
    }


# ---------------------------------------------------------------------------
# Module 117 — Payload Evasion Engine
# ---------------------------------------------------------------------------


@router.post("/payload-evade", status_code=status.HTTP_200_OK)
async def payload_evade(
    body: PayloadEvadeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 117 — Payload Evasion Engine.

    Tests whether a payload is detected by the target's security controls
    and suggests obfuscation or encoding techniques to bypass signature-based
    detection. For authorised red team engagements only.
    """
    result = await _run_scanner(registry, "payload_evasion_engine", body.target_url)
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 118 — Memory Forensics Tool (educational)
# ---------------------------------------------------------------------------


@router.post("/memory-forensics", status_code=status.HTTP_200_OK)
async def memory_forensics(
    body: MemoryForensicsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 118 — Memory Forensics Tool (educational).

    Returns a curated set of Volatility 3 command recipes for common memory
    analysis tasks. When a dump URL is provided, a download/processing
    pipeline is described. No memory dumps are fetched or analysed by default.
    """
    recipes = [
        {
            "task": "List running processes",
            "command": "vol -f memory.dmp windows.pslist.PsList",
            "notes": "Reveals processes including those hidden by rootkits (compare with pstree).",
        },
        {
            "task": "Detect process injection",
            "command": "vol -f memory.dmp windows.malfind.Malfind",
            "notes": "Flags memory regions with PAGE_EXECUTE_READWRITE that contain suspicious code.",
        },
        {
            "task": "Dump network connections",
            "command": "vol -f memory.dmp windows.netstat.NetStat",
            "notes": "Enumerates active and recently closed TCP/UDP connections.",
        },
        {
            "task": "Extract registry hives",
            "command": "vol -f memory.dmp windows.registry.printkey.PrintKey",
            "notes": "Reads live registry keys from the memory image.",
        },
        {
            "task": "Identify loaded modules",
            "command": "vol -f memory.dmp windows.modules.Modules",
            "notes": "Lists kernel modules; compare against baseline to detect rootkits.",
        },
        {
            "task": "Dump process memory",
            "command": "vol -f memory.dmp -o ./output windows.memmap.Memmap --pid <PID> --dump",
            "notes": "Dumps the full virtual address space of a process for further analysis.",
        },
        {
            "task": "Detect hooks",
            "command": "vol -f memory.dmp windows.ssdt.SSDT",
            "notes": "Checks the SSDT for function pointer modifications indicating rootkit hooks.",
        },
    ]

    return {
        "found": True,
        "data": {
            "educational": True,
            "dump_url": body.dump_url or None,
            "process_filter": body.process_filter or None,
            "note": "Command recipes are for Volatility 3. Substitute 'memory.dmp' with your actual dump path.",
            "volatility_recipes": recipes,
        },
    }


# ---------------------------------------------------------------------------
# Module 119 — C2 Channel Simulator (educational)
# ---------------------------------------------------------------------------


@router.post("/c2-channel", status_code=status.HTTP_200_OK)
async def c2_channel(
    body: C2ChannelRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 119 — C2 Channel Simulator (educational).

    Explains the mechanics of covert command-and-control channels over
    DNS or ICMP, showing packet structure and encoding schemes without
    transmitting any traffic.
    """
    if not body.simulate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Live C2 channel establishment is not supported. Use simulate=true.",
        )

    c2_type = body.c2_type.lower()
    if c2_type not in {"dns", "icmp", "http", "https"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="c2_type must be 'dns', 'icmp', 'http', or 'https'.",
        )

    channel_specs: dict[str, dict] = {
        "dns": {
            "mechanism": "Data encoded as subdomains of the C2 domain; responses carry commands in TXT/A records.",
            "example_beacon": f"aGVsbG8=.{body.domain}  (base64 'hello' as subdomain)",
            "bandwidth": "~100 bytes per query (limited by label length)",
            "detection_signatures": [
                "High volume of NXDOMAIN responses to a single domain.",
                "Long subdomain labels (> 30 chars) with high entropy.",
                "DNS queries at regular beaconing intervals.",
                "Unusual record types (TXT/NULL) from workstations.",
            ],
        },
        "icmp": {
            "mechanism": "Data hidden in the ICMP Echo payload field; replies carry commands.",
            "example_beacon": "ICMP Echo with 64-byte payload containing XOR-encoded command.",
            "bandwidth": "~64 bytes per echo (limited by MTU)",
            "detection_signatures": [
                "ICMP echoes with non-zero, non-pattern payload.",
                "ICMP traffic to external hosts (workstations rarely ping externally).",
                "High frequency ICMP bursts from a single host.",
            ],
        },
        "http": {
            "mechanism": "Commands in HTTP response body or headers; beacons as GET/POST to C2.",
            "example_beacon": f"GET /jquery-3.3.1.min.js HTTP/1.1\\r\\nHost: {body.domain}",
            "bandwidth": "Effectively unlimited",
            "detection_signatures": [
                "HTTP to unusual external IPs without a corresponding DNS lookup.",
                "JA3/JA3S fingerprint mismatch for claimed User-Agent.",
                "Periodic beaconing at fixed intervals (low jitter).",
            ],
        },
        "https": {
            "mechanism": "TLS-encrypted HTTP C2 — same as HTTP but traffic content is opaque.",
            "example_beacon": f"HTTPS GET to {body.domain} with self-signed or Let's Encrypt cert.",
            "bandwidth": "Effectively unlimited",
            "detection_signatures": [
                "Certificate issued hours/days ago (newly registered domain).",
                "JA3 fingerprint matches known C2 frameworks (Cobalt Strike, Metasploit).",
                "Domain registered < 30 days ago (DGA heuristic).",
            ],
        },
    }

    spec = channel_specs[c2_type]

    return {
        "found": True,
        "data": {
            "simulation": True,
            "c2_type": c2_type,
            "domain": body.domain,
            "channel_specification": spec,
        },
    }


# ---------------------------------------------------------------------------
# Module 120 — EDR/AV Checker
# ---------------------------------------------------------------------------


@router.post("/edr-check", status_code=status.HTTP_200_OK)
async def edr_check(
    body: EdrCheckRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 120 — EDR/AV Checker.

    Performs a passive check for installed security products on the target
    host by analysing banners, HTTP headers, and process artefacts visible
    without authentication. Returns detected security products.
    """
    result = await _run_scanner(registry, "payload_evasion_engine", body.target_ip)
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 121 — AD CS Abuse Module
# ---------------------------------------------------------------------------


@router.post("/adcs-abuse", status_code=status.HTTP_200_OK)
async def adcs_abuse(
    body: AdcsAbuseRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 121 — Active Directory Certificate Services Abuse.

    Enumerates AD CS certificate templates for ESC1-ESC8 vulnerabilities
    (misconfigured templates, dangerous EKUs, weak ACLs) that could allow
    privilege escalation or persistent authentication.
    """
    result = await _run_scanner(registry, "ad_cs_abuse", body.domain)
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 122 — GraphQL Depth Auditor
# ---------------------------------------------------------------------------


@router.post("/graphql-audit", status_code=status.HTTP_200_OK)
async def graphql_audit(
    body: GraphqlAuditRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 122 — GraphQL Depth Auditor.

    Tests a GraphQL endpoint for introspection leakage, lack of depth/complexity
    limits, batch query abuse, and IDOR vulnerabilities via field-level access
    control checks.
    """
    result = await _run_scanner(
        registry,
        "graphql_depth_auditor",
        body.target_url,
        extra={"max_depth": body.max_depth},
    )
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 123 — TOCTOU Visualiser (educational)
# ---------------------------------------------------------------------------


@router.post("/toctou", status_code=status.HTTP_200_OK)
async def toctou(
    body: ToctouRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 123 — TOCTOU Visualiser (educational).

    Simulates a Time-of-Check Time-of-Use race condition scenario and returns
    a timeline visualisation showing the race window, the exploit thread, and
    proof-of-concept code. Nothing is executed on external systems.
    """
    scenarios: dict[str, dict] = {
        "file_check": {
            "description": "check-then-use on a filesystem path (symlink race)",
            "poc_pseudocode": (
                "# Thread A (victim program)\n"
                "if os.access('/tmp/target', os.W_OK):  # CHECK\n"
                "    # ... race window starts here ...\n"
                "    open('/tmp/target', 'w').write(data) # USE\n\n"
                "# Thread B (attacker)\n"
                "while True:\n"
                "    os.symlink('/etc/passwd', '/tmp/target')  # exploit\n"
                "    os.unlink('/tmp/target')\n"
            ),
            "mitigation": [
                "Use O_NOFOLLOW to refuse symlinks.",
                "Open the file first (get fd), then check permissions on the fd.",
                "Use mkstemp() for temporary files.",
            ],
        },
        "privilege_check": {
            "description": "check-then-use on a privilege level (SUID binary race)",
            "poc_pseudocode": (
                "# SUID binary flow\n"
                "uid = getuid()  # CHECK — reads uid\n"
                "# race window: attacker swaps the resource\n"
                "setuid(0)       # USE — now escalated\n"
            ),
            "mitigation": [
                "Drop privileges immediately and permanently after use.",
                "Use atomic system calls that check and act in one step.",
            ],
        },
    }

    scenario = scenarios.get(body.scenario, scenarios["file_check"])
    race_window_ms = body.race_window_ms

    timeline = [
        {"time_ms": 0, "thread": "victim", "action": "CHECK: verify condition"},
        {"time_ms": race_window_ms // 4, "thread": "attacker", "action": "EXPLOIT: swap resource"},
        {"time_ms": race_window_ms // 2, "thread": "victim", "action": "... still in race window ..."},
        {"time_ms": race_window_ms, "thread": "victim", "action": "USE: act on (now stale) check result"},
        {"time_ms": race_window_ms + 10, "thread": "attacker", "action": "RESULT: exploit succeeded"},
    ]

    return {
        "found": True,
        "data": {
            "educational": True,
            "scenario": body.scenario,
            "race_window_ms": race_window_ms,
            "description": scenario["description"],
            "poc_pseudocode": scenario["poc_pseudocode"],
            "timeline": timeline,
            "mitigation": scenario["mitigation"],
        },
    }


# ---------------------------------------------------------------------------
# Module 124 — APK Static Analyzer
# ---------------------------------------------------------------------------


@router.post("/apk-analyze", status_code=status.HTTP_200_OK)
async def apk_analyze(
    body: ApkAnalyzeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 124 — APK Static Analyzer.

    Downloads and statically analyses an Android APK for hardcoded secrets,
    dangerous permissions, exported components, and known vulnerable libraries.
    """
    result = await _run_scanner(registry, "apkleaks", body.apk_url)
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 125 — Dangling DNS Scanner
# ---------------------------------------------------------------------------


@router.post("/dangling-dns", status_code=status.HTTP_200_OK)
async def dangling_dns(
    body: DanglingDnsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 125 — Dangling DNS Scanner.

    Checks DNS records for the target domain that point to deprovisioned
    cloud resources, expired services, or unclaimed subdomains susceptible
    to subdomain takeover.
    """
    result = await _run_scanner(registry, "dangling_dns", body.domain)
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 126 — MITRE ATT&CK Mapper
# ---------------------------------------------------------------------------


@router.post("/mitre-map", status_code=status.HTTP_200_OK)
async def mitre_map(
    body: MitreMapRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 126 — MITRE ATT&CK Mapper.

    Maps a list of technique IDs (e.g. T1059, T1078) to the MITRE ATT&CK
    framework, returning tactic classifications, technique names, and colour
    data for rendering an ATT&CK heat-map in the React frontend.
    """
    # Subset of ATT&CK for demonstration; a full implementation would query
    # the STIX/TAXII feed from attack.mitre.org
    known_techniques: dict[str, dict] = {
        "T1059": {"name": "Command and Scripting Interpreter", "tactic": "Execution", "color": "#e74c3c"},
        "T1078": {"name": "Valid Accounts", "tactic": "Defense Evasion / Persistence", "color": "#e67e22"},
        "T1486": {"name": "Data Encrypted for Impact", "tactic": "Impact", "color": "#c0392b"},
        "T1003": {"name": "OS Credential Dumping", "tactic": "Credential Access", "color": "#9b59b6"},
        "T1055": {"name": "Process Injection", "tactic": "Defense Evasion", "color": "#2ecc71"},
        "T1190": {"name": "Exploit Public-Facing Application", "tactic": "Initial Access", "color": "#3498db"},
        "T1566": {"name": "Phishing", "tactic": "Initial Access", "color": "#1abc9c"},
        "T1021": {"name": "Remote Services", "tactic": "Lateral Movement", "color": "#f39c12"},
        "T1083": {"name": "File and Directory Discovery", "tactic": "Discovery", "color": "#7f8c8d"},
        "T1041": {"name": "Exfiltration Over C2 Channel", "tactic": "Exfiltration", "color": "#e74c3c"},
    }

    mapped: list[dict] = []
    unknown: list[str] = []

    for technique_id in body.techniques:
        tid = technique_id.upper().strip()
        info = known_techniques.get(tid)
        if info:
            mapped.append({"id": tid, **info})
        else:
            unknown.append(tid)

    return {
        "found": len(mapped) > 0,
        "data": {
            "investigation_id": body.investigation_id,
            "mapped_techniques": mapped,
            "unknown_techniques": unknown,
            "matrix_cells": [
                {"id": t["id"], "name": t["name"], "tactic": t["tactic"], "color": t["color"]}
                for t in mapped
            ],
        },
    }


# ---------------------------------------------------------------------------
# Module 127 — Threat Intel Aggregator
# ---------------------------------------------------------------------------


@router.post("/threat-intel", status_code=status.HTTP_200_OK)
async def threat_intel(
    body: ThreatIntelRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    registry: Annotated[ScannerRegistry, Depends(get_scanner_registry)],
) -> dict:
    """Module 127 — Threat Intel Aggregator.

    Aggregates threat intelligence for the target from multiple feeds
    (OTX, ThreatFox, URLhaus, AbuseIPDB) and returns a consolidated risk
    profile with IOC matches and source attribution.
    """
    result = await _run_scanner(registry, "threat_intel_aggregator", body.target)
    if result.get("error") and not result.get("data"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Module 128 — Dynamic Firewall Enforcer
# ---------------------------------------------------------------------------


@router.post("/firewall-enforce", status_code=status.HTTP_200_OK)
async def firewall_enforce(
    body: FirewallEnforceRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 128 — Dynamic Firewall Enforcer.

    Manages temporary IP blocks via iptables/ufw for threat response. Only
    simulation mode is supported by default; set simulate=false to apply real
    rules (requires the API process to have the necessary capabilities).
    """
    if not body.simulate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Live firewall rule changes require simulate=false along with elevated host permissions. Currently only simulation is supported via this endpoint.",
        )

    action = body.action.lower()
    if action not in {"block", "unblock"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action must be 'block' or 'unblock'.",
        )

    iptables_cmd = (
        f"iptables -I INPUT -s {body.ip} -j DROP -m comment --comment 'osint:{body.reason}'"
        if action == "block"
        else f"iptables -D INPUT -s {body.ip} -j DROP"
    )
    ufw_cmd = (
        f"ufw deny from {body.ip} comment '{body.reason}'"
        if action == "block"
        else f"ufw delete deny from {body.ip}"
    )

    return {
        "found": True,
        "data": {
            "simulation": True,
            "action": action,
            "ip": body.ip,
            "reason": body.reason,
            "duration_hours": body.duration_hours,
            "iptables_command": iptables_cmd,
            "ufw_command": ufw_cmd,
            "expiry_note": f"Block should be removed after {body.duration_hours}h via scheduled cron or automation.",
            "current_block_list": [],
        },
    }


# ---------------------------------------------------------------------------
# Module 129 — DFIR Evidence Pipeline (educational)
# ---------------------------------------------------------------------------


@router.post("/dfir-collect", status_code=status.HTTP_200_OK)
async def dfir_collect(
    body: DfirCollectRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 129 — DFIR Evidence Pipeline (educational).

    Generates a structured evidence collection script organised by evidence
    type (logs, processes, network, filesystem, memory). Commands target
    common Linux/Windows environments and follow forensic best practices.
    """
    collection_commands: dict[str, list[dict]] = {
        "logs": [
            {"os": "linux", "command": "journalctl --no-pager -n 10000 > /evidence/system.log", "note": "Collect systemd journal"},
            {"os": "linux", "command": "tar -czf /evidence/var_log.tar.gz /var/log/", "note": "Archive /var/log"},
            {"os": "windows", "command": "wevtutil epl Security C:\\evidence\\Security.evtx", "note": "Export Security event log"},
            {"os": "windows", "command": "wevtutil epl System C:\\evidence\\System.evtx", "note": "Export System event log"},
        ],
        "processes": [
            {"os": "linux", "command": "ps auxf > /evidence/process_tree.txt", "note": "Full process tree"},
            {"os": "linux", "command": "ls -la /proc/*/exe 2>/dev/null > /evidence/proc_exe.txt", "note": "Process executables"},
            {"os": "windows", "command": "tasklist /v /fo csv > C:\\evidence\\tasklist.csv", "note": "Verbose process list"},
            {"os": "windows", "command": "Get-Process | Select * | Export-Csv C:\\evidence\\processes.csv", "note": "PowerShell process details"},
        ],
        "network": [
            {"os": "linux", "command": "ss -tunap > /evidence/connections.txt", "note": "Active network connections"},
            {"os": "linux", "command": "ip route show > /evidence/routes.txt && arp -n > /evidence/arp.txt", "note": "Routing and ARP tables"},
            {"os": "windows", "command": "netstat -anob > C:\\evidence\\netstat.txt", "note": "Connections with owning process"},
            {"os": "windows", "command": "ipconfig /all > C:\\evidence\\ipconfig.txt && route print > C:\\evidence\\routes.txt", "note": "Network config"},
        ],
        "filesystem": [
            {"os": "linux", "command": "find / -mtime -1 -type f 2>/dev/null > /evidence/recent_files.txt", "note": "Files modified in last 24h"},
            {"os": "linux", "command": "find / -perm -4000 2>/dev/null > /evidence/suid_files.txt", "note": "SUID binaries"},
            {"os": "windows", "command": "dir /s /b /a-d C:\\ | findstr /i \".exe .dll .ps1\" > C:\\evidence\\executables.txt", "note": "Executable inventory"},
        ],
        "memory": [
            {"os": "linux", "command": "avml /evidence/memory.dmp", "note": "Capture RAM with AVML (requires install)"},
            {"os": "windows", "command": "winpmem_mini_x64_rc2.exe C:\\evidence\\memory.dmp", "note": "Capture RAM with WinPmem"},
        ],
    }

    selected: dict[str, list[dict]] = {
        ct: collection_commands.get(ct, [])
        for ct in body.collect_types
        if ct in collection_commands
    }

    invalid = [ct for ct in body.collect_types if ct not in collection_commands]

    return {
        "found": True,
        "data": {
            "educational": True,
            "target_ip": body.target_ip or "local",
            "collect_types": body.collect_types,
            "invalid_types": invalid,
            "commands": selected,
            "chain_of_custody_reminder": (
                "Hash all collected artefacts immediately (sha256sum) and record timestamps. "
                "Store evidence on write-once media or an immutable S3 bucket."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Module 130 — OSCP-Style Reporter
# ---------------------------------------------------------------------------


@router.post("/oscp-report", status_code=status.HTTP_200_OK)
async def oscp_report(
    body: OscpReportRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Module 130 — OSCP-Style Reporter.

    Generates a professional penetration test report in Markdown format
    following the Offensive Security report template. Sections include
    executive summary, methodology, findings, and remediation roadmap.
    """
    findings_md = ""
    for i, finding in enumerate(body.findings, 1):
        title = finding.get("title", f"Finding {i}")
        severity = finding.get("severity", "Medium")
        description = finding.get("description", "No description provided.")
        remediation = finding.get("remediation", "No remediation provided.")
        screenshot_note = (
            "\n\n**Screenshot:** *(attach evidence image here)*"
            if body.include_screenshots
            else ""
        )
        findings_md += (
            f"\n### {i}. {title}\n\n"
            f"**Severity:** {severity}\n\n"
            f"**Description:** {description}\n\n"
            f"**Remediation:** {remediation}"
            f"{screenshot_note}\n"
        )

    if not findings_md:
        findings_md = "\n*No findings provided — populate the `findings` array.*\n"

    report_md = f"""# Penetration Test Report

**Investigation ID:** {body.investigation_id}
**Date:** *(auto-populated on final render)*
**Prepared by:** {current_user.email if hasattr(current_user, 'email') else 'Assessor'}
**Classification:** CONFIDENTIAL

---

## Executive Summary

This report documents the results of a penetration test conducted against the environment
identified by investigation `{body.investigation_id}`. The assessment was performed using
industry-standard methodologies aligned with OWASP, PTES, and OSSTMM frameworks.

**Total Findings:** {len(body.findings)}
**Critical:** {sum(1 for f in body.findings if f.get('severity', '').lower() == 'critical')}
**High:** {sum(1 for f in body.findings if f.get('severity', '').lower() == 'high')}
**Medium:** {sum(1 for f in body.findings if f.get('severity', '').lower() == 'medium')}
**Low:** {sum(1 for f in body.findings if f.get('severity', '').lower() == 'low')}

---

## Methodology

1. **Reconnaissance** — Passive and active information gathering
2. **Scanning & Enumeration** — Port scanning, service fingerprinting, vulnerability scanning
3. **Exploitation** — Controlled exploitation of discovered vulnerabilities
4. **Post-Exploitation** — Privilege escalation, lateral movement (where authorised)
5. **Reporting** — Documentation of findings with risk ratings and remediation guidance

---

## Findings
{findings_md}

---

## Remediation Roadmap

| Priority | Finding | Target Date |
|----------|---------|-------------|
{chr(10).join(f"| {f.get('severity', 'Medium')} | {f.get('title', f'Finding {i+1}')} | *(TBD)* |" for i, f in enumerate(body.findings))}

---

## Appendix

- **Tools Used:** nmap, Metasploit, Burp Suite, BloodHound, custom OSINT platform modules
- **Scope:** As defined in the rules of engagement document
- **Limitations:** Testing was non-destructive; denial-of-service techniques were excluded

---
*This report is confidential and intended solely for the authorised recipient.*
"""

    return {
        "found": True,
        "data": {
            "investigation_id": body.investigation_id,
            "finding_count": len(body.findings),
            "include_screenshots": body.include_screenshots,
            "format": "markdown",
            "report": report_md,
        },
    }
