"""YAML serializer / deserializer for AttackChain scenarios.

Converts AttackChainModel instances to human-readable YAML and back,
enabling export, import, and the prebuilt scenario marketplace.
"""

from __future__ import annotations

import uuid
from typing import Any

import yaml

from src.adapters.db.pentest_models import AttackChainModel


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def chain_to_yaml(chain: AttackChainModel) -> str:
    """Return a YAML string representing the attack chain."""
    data: dict[str, Any] = {
        "id": str(chain.id),
        "objective_en": chain.objective_en,
        "objective_pl": chain.objective_pl,
        "overall_likelihood": chain.overall_likelihood,
        "overall_impact": chain.overall_impact,
        "generated_by": chain.generated_by,
        "steps": chain.steps or [],
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# Deserialization
# ---------------------------------------------------------------------------


def yaml_to_chain_fields(yaml_str: str) -> dict[str, Any]:
    """Parse YAML and return a dict of AttackChainModel field values.

    Raises:
        ValueError: if the YAML is invalid or missing required keys.
    """
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping object.")

    steps = data.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError("'steps' must be a list.")

    return {
        "objective_en": data.get("objective_en"),
        "objective_pl": data.get("objective_pl"),
        "overall_likelihood": data.get("overall_likelihood"),
        "overall_impact": data.get("overall_impact"),
        "generated_by": data.get("generated_by", "yaml-import"),
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# Prebuilt scenario library (marketplace)
# ---------------------------------------------------------------------------

PREBUILT_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "mkt-web-owasp-top10",
        "name": "Web App — OWASP Top 10",
        "category": "web",
        "difficulty": "medium",
        "description": "Full OWASP Top 10 coverage: injection, broken auth, XSS, IDOR, misconfiguration.",
        "avg_duration_min": 45,
        "mitre_tactics": ["Initial Access", "Execution", "Exfiltration"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1592", "technique_name": "Gather Victim Host Information", "tools": ["httpx", "subfinder"], "preconditions": [], "detection_hints": []},
            {"step": 2, "tactic": "Initial Access", "technique_id": "T1190", "technique_name": "Exploit Public-Facing Application", "tools": ["nuclei", "zap"], "preconditions": ["web app reachable"], "detection_hints": ["WAF alerts"]},
            {"step": 3, "tactic": "Execution", "technique_id": "T1059.007", "technique_name": "Command and Scripting: JavaScript", "tools": ["zap"], "preconditions": ["XSS surface identified"], "detection_hints": ["CSP violations"]},
            {"step": 4, "tactic": "Exfiltration", "technique_id": "T1041", "technique_name": "Exfiltration Over C2 Channel", "tools": ["sqlmap"], "preconditions": ["SQLi parameter found"], "detection_hints": ["unusual DB queries"]},
        ],
    },
    {
        "id": "mkt-network-internal",
        "name": "Internal Network Pivot",
        "category": "network",
        "difficulty": "hard",
        "description": "Post-initial-access lateral movement through internal network segments.",
        "avg_duration_min": 90,
        "mitre_tactics": ["Discovery", "Lateral Movement", "Credential Access"],
        "steps": [
            {"step": 1, "tactic": "Discovery", "technique_id": "T1046", "technique_name": "Network Service Discovery", "tools": ["nmap"], "preconditions": ["internal network access"], "detection_hints": ["IDS port scan alerts"]},
            {"step": 2, "tactic": "Credential Access", "technique_id": "T1110.003", "technique_name": "Password Spraying", "tools": ["spray"], "preconditions": ["user list obtained"], "detection_hints": ["multiple failed logins"]},
            {"step": 3, "tactic": "Lateral Movement", "technique_id": "T1021.002", "technique_name": "SMB/Windows Admin Shares", "tools": ["nmap"], "preconditions": ["valid credentials"], "detection_hints": ["SMB auth events"]},
        ],
    },
    {
        "id": "mkt-ad-kerberoast",
        "name": "Active Directory — Kerberoasting",
        "category": "ad",
        "difficulty": "hard",
        "description": "Enumerate SPNs, request Kerberos tickets, crack service account passwords.",
        "avg_duration_min": 60,
        "mitre_tactics": ["Credential Access", "Privilege Escalation"],
        "steps": [
            {"step": 1, "tactic": "Discovery", "technique_id": "T1087.002", "technique_name": "Account Discovery: Domain Account", "tools": ["nmap"], "preconditions": ["domain user access"], "detection_hints": ["LDAP query logs"]},
            {"step": 2, "tactic": "Credential Access", "technique_id": "T1558.003", "technique_name": "Steal or Forge Kerberos Tickets: Kerberoasting", "tools": ["kerberoast"], "preconditions": ["SPN accounts identified"], "detection_hints": ["TGS request spikes"]},
            {"step": 3, "tactic": "Credential Access", "technique_id": "T1110.002", "technique_name": "Password Cracking", "tools": ["hashcat"], "preconditions": ["TGS tickets captured"], "detection_hints": ["offline — no network detection"]},
        ],
    },
    {
        "id": "mkt-cloud-aws",
        "name": "AWS Cloud Exposure",
        "category": "cloud",
        "difficulty": "medium",
        "description": "Enumerate misconfigured S3 buckets, IAM roles, and exposed metadata endpoints.",
        "avg_duration_min": 30,
        "mitre_tactics": ["Reconnaissance", "Initial Access", "Privilege Escalation"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1580", "technique_name": "Cloud Infrastructure Discovery", "tools": ["httpx", "subfinder"], "preconditions": ["AWS account scope defined"], "detection_hints": ["CloudTrail GetBucketAcl"]},
            {"step": 2, "tactic": "Initial Access", "technique_id": "T1190", "technique_name": "Exploit Public-Facing Application", "tools": ["nuclei"], "preconditions": ["public S3 bucket found"], "detection_hints": ["S3 access logs"]},
            {"step": 3, "tactic": "Privilege Escalation", "technique_id": "T1078.004", "technique_name": "Cloud Accounts", "tools": ["httpx"], "preconditions": ["IAM key in exposed config"], "detection_hints": ["CloudTrail AssumeRole"]},
        ],
    },
    {
        "id": "mkt-api-rest",
        "name": "REST API Security Assessment",
        "category": "api",
        "difficulty": "medium",
        "description": "BOLA, broken function-level auth, mass assignment, and injection via API.",
        "avg_duration_min": 40,
        "mitre_tactics": ["Initial Access", "Exfiltration"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1592.002", "technique_name": "Gather Victim Host Information: Software", "tools": ["httpx", "ffuf"], "preconditions": ["API base URL known"], "detection_hints": ["rate limiting hits"]},
            {"step": 2, "tactic": "Initial Access", "technique_id": "T1190", "technique_name": "Exploit Public-Facing Application", "tools": ["zap", "nuclei"], "preconditions": ["OpenAPI spec or discovered endpoints"], "detection_hints": ["4xx/5xx response spikes"]},
            {"step": 3, "tactic": "Exfiltration", "technique_id": "T1041", "technique_name": "Exfiltration Over C2 Channel", "tools": ["sqlmap"], "preconditions": ["SQL injection surface"], "detection_hints": ["DB slow query logs"]},
        ],
    },
    {
        "id": "mkt-subdomain-takeover",
        "name": "Subdomain Takeover Chain",
        "category": "web",
        "difficulty": "easy",
        "description": "Find dangling DNS entries pointing to deprovisioned cloud resources.",
        "avg_duration_min": 20,
        "mitre_tactics": ["Reconnaissance", "Resource Development"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1596.001", "technique_name": "Search Open Technical Databases: DNS", "tools": ["subfinder"], "preconditions": ["root domain in scope"], "detection_hints": []},
            {"step": 2, "tactic": "Reconnaissance", "technique_id": "T1592.004", "technique_name": "Gather Victim Host Information: Network Topology", "tools": ["httpx"], "preconditions": ["subdomain list"], "detection_hints": []},
            {"step": 3, "tactic": "Resource Development", "technique_id": "T1585.001", "technique_name": "Establish Accounts: Social Media Accounts", "tools": ["nuclei"], "preconditions": ["NXDOMAIN or 404 on cloud provider"], "detection_hints": ["no server-side detection possible"]},
        ],
    },
    {
        "id": "mkt-ssl-tls",
        "name": "SSL/TLS Misconfiguration Scan",
        "category": "network",
        "difficulty": "easy",
        "description": "Detect weak ciphers, expired certs, BEAST, POODLE, Heartbleed.",
        "avg_duration_min": 15,
        "mitre_tactics": ["Initial Access"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1590.005", "technique_name": "Gather Victim Network Information: IP Addresses", "tools": ["subfinder", "httpx"], "preconditions": ["HTTPS service in scope"], "detection_hints": []},
            {"step": 2, "tactic": "Initial Access", "technique_id": "T1557", "technique_name": "Adversary-in-the-Middle", "tools": ["sslyze"], "preconditions": ["TLS endpoint reachable"], "detection_hints": ["unusual TLS negotiation"]},
        ],
    },
    {
        "id": "mkt-dir-enum",
        "name": "Content Discovery & Dir Enumeration",
        "category": "web",
        "difficulty": "easy",
        "description": "Find hidden endpoints, admin panels, backup files, and exposed configs.",
        "avg_duration_min": 25,
        "mitre_tactics": ["Reconnaissance", "Collection"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1595.003", "technique_name": "Active Scanning: Wordlist Scanning", "tools": ["gobuster", "ffuf"], "preconditions": ["web app URL in scope"], "detection_hints": ["WAF 4xx bursts"]},
            {"step": 2, "tactic": "Collection", "technique_id": "T1213", "technique_name": "Data from Information Repositories", "tools": ["nuclei"], "preconditions": ["admin panel or .git found"], "detection_hints": ["access log anomalies"]},
        ],
    },
    {
        "id": "mkt-mobile-api",
        "name": "Mobile App API Backend Audit",
        "category": "mobile",
        "difficulty": "medium",
        "description": "Intercept mobile traffic, test authentication bypass, token leakage.",
        "avg_duration_min": 50,
        "mitre_tactics": ["Initial Access", "Credential Access"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1592.002", "technique_name": "Gather Victim Host Information: Software", "tools": ["subfinder", "httpx"], "preconditions": ["APK / app analyzed"], "detection_hints": []},
            {"step": 2, "tactic": "Initial Access", "technique_id": "T1190", "technique_name": "Exploit Public-Facing Application", "tools": ["zap", "ffuf"], "preconditions": ["backend API endpoints extracted from APK"], "detection_hints": ["auth service anomalies"]},
        ],
    },
    {
        "id": "mkt-full-redteam",
        "name": "Full Red Team Exercise",
        "category": "redteam",
        "difficulty": "expert",
        "description": "Complete chain: recon → initial access → privilege escalation → lateral movement → exfiltration.",
        "avg_duration_min": 180,
        "mitre_tactics": ["Reconnaissance", "Initial Access", "Execution", "Persistence", "Privilege Escalation", "Lateral Movement", "Exfiltration"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1595", "technique_name": "Active Scanning", "tools": ["subfinder", "httpx", "nmap"], "preconditions": [], "detection_hints": ["IDS/IPS network scans"]},
            {"step": 2, "tactic": "Initial Access", "technique_id": "T1190", "technique_name": "Exploit Public-Facing Application", "tools": ["nuclei", "sqlmap", "zap"], "preconditions": ["attack surface mapped"], "detection_hints": ["WAF alerts, SIEM events"]},
            {"step": 3, "tactic": "Privilege Escalation", "technique_id": "T1078", "technique_name": "Valid Accounts", "tools": ["spray", "kerberoast"], "preconditions": ["initial foothold"], "detection_hints": ["auth failures, SIEM alerts"]},
            {"step": 4, "tactic": "Lateral Movement", "technique_id": "T1021", "technique_name": "Remote Services", "tools": ["nmap"], "preconditions": ["credentials obtained"], "detection_hints": ["lateral movement alerts"]},
            {"step": 5, "tactic": "Exfiltration", "technique_id": "T1041", "technique_name": "Exfiltration Over C2 Channel", "tools": ["sqlmap"], "preconditions": ["data identified"], "detection_hints": ["DLP, egress monitoring"]},
        ],
    },
    # ---------- BATCH 2 (11-20) ----------
    {
        "id": "mkt-iot-firmware",
        "name": "IoT Firmware Analysis",
        "category": "iot",
        "difficulty": "hard",
        "description": "Extract firmware, find hardcoded creds, identify vulnerable services on embedded devices.",
        "avg_duration_min": 70,
        "mitre_tactics": ["Reconnaissance", "Initial Access", "Credential Access"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1592", "technique_name": "Gather Victim Host Information", "tools": ["nmap", "httpx"], "preconditions": ["device IP in scope"], "detection_hints": ["SNMP/telnet access logs"]},
            {"step": 2, "tactic": "Credential Access", "technique_id": "T1552.001", "technique_name": "Credentials In Files", "tools": ["nuclei"], "preconditions": ["firmware image extracted"], "detection_hints": []},
            {"step": 3, "tactic": "Initial Access", "technique_id": "T1078.001", "technique_name": "Default Accounts", "tools": ["hydra"], "preconditions": ["hardcoded creds identified"], "detection_hints": ["SSH/telnet auth logs"]},
        ],
    },
    {
        "id": "mkt-phishing-sim",
        "name": "Phishing Campaign Simulation",
        "category": "phishing",
        "difficulty": "medium",
        "description": "Spear-phishing with credential harvesting page and payload delivery.",
        "avg_duration_min": 55,
        "mitre_tactics": ["Reconnaissance", "Resource Development", "Initial Access"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1589.002", "technique_name": "Gather Victim Identity Information: Email Addresses", "tools": ["subfinder", "httpx"], "preconditions": ["target org identified"], "detection_hints": []},
            {"step": 2, "tactic": "Resource Development", "technique_id": "T1583.001", "technique_name": "Acquire Infrastructure: Domains", "tools": ["nuclei"], "preconditions": ["domain list ready"], "detection_hints": ["DMARC/SPF checks"]},
            {"step": 3, "tactic": "Initial Access", "technique_id": "T1566.001", "technique_name": "Phishing: Spearphishing Attachment", "tools": ["zap"], "preconditions": ["phishing kit prepared"], "detection_hints": ["email gateway alerts"]},
        ],
    },
    {
        "id": "mkt-supply-chain",
        "name": "Software Supply Chain Assessment",
        "category": "supply_chain",
        "difficulty": "hard",
        "description": "Audit third-party dependencies, typosquatting, malicious packages in CI/CD.",
        "avg_duration_min": 80,
        "mitre_tactics": ["Resource Development", "Initial Access", "Execution"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1593", "technique_name": "Search Open Websites/Domains", "tools": ["subfinder"], "preconditions": ["package manifests accessible"], "detection_hints": []},
            {"step": 2, "tactic": "Resource Development", "technique_id": "T1608.006", "technique_name": "Stage Capabilities: SEO Poisoning", "tools": ["nuclei"], "preconditions": ["dependency list"], "detection_hints": ["npm/pip audit logs"]},
            {"step": 3, "tactic": "Execution", "technique_id": "T1059.004", "technique_name": "Unix Shell", "tools": ["nmap"], "preconditions": ["malicious package installed"], "detection_hints": ["SIEM process creation"]},
        ],
    },
    {
        "id": "mkt-cloud-azure",
        "name": "Azure Cloud Security Review",
        "category": "cloud",
        "difficulty": "medium",
        "description": "Enumerate Azure AD, storage blobs, and misconfigured role assignments.",
        "avg_duration_min": 50,
        "mitre_tactics": ["Reconnaissance", "Credential Access", "Privilege Escalation"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1580", "technique_name": "Cloud Infrastructure Discovery", "tools": ["subfinder", "httpx"], "preconditions": ["Azure tenant in scope"], "detection_hints": ["Azure Monitor logs"]},
            {"step": 2, "tactic": "Credential Access", "technique_id": "T1552.008", "technique_name": "Chat Messages", "tools": ["nuclei"], "preconditions": ["Teams/SharePoint accessible"], "detection_hints": ["DLP policy alerts"]},
            {"step": 3, "tactic": "Privilege Escalation", "technique_id": "T1078.004", "technique_name": "Cloud Accounts", "tools": ["httpx"], "preconditions": ["service principal found"], "detection_hints": ["Azure AD sign-in logs"]},
        ],
    },
    {
        "id": "mkt-cloud-gcp",
        "name": "GCP Cloud Misconfiguration Scan",
        "category": "cloud",
        "difficulty": "medium",
        "description": "Find open GCS buckets, over-permissive IAM, and metadata service abuse.",
        "avg_duration_min": 35,
        "mitre_tactics": ["Reconnaissance", "Initial Access", "Privilege Escalation"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1580", "technique_name": "Cloud Infrastructure Discovery", "tools": ["httpx"], "preconditions": ["GCP project in scope"], "detection_hints": ["Cloud Audit logs"]},
            {"step": 2, "tactic": "Initial Access", "technique_id": "T1190", "technique_name": "Exploit Public-Facing Application", "tools": ["nuclei"], "preconditions": ["GCS bucket list"], "detection_hints": ["GCS access logs"]},
            {"step": 3, "tactic": "Privilege Escalation", "technique_id": "T1078.004", "technique_name": "Cloud Accounts", "tools": ["httpx"], "preconditions": ["metadata endpoint reachable"], "detection_hints": ["GCP Activity logs"]},
        ],
    },
    {
        "id": "mkt-ad-asreproast",
        "name": "Active Directory — AS-REP Roasting",
        "category": "ad",
        "difficulty": "hard",
        "description": "Find accounts with Kerberos pre-auth disabled and crack AS-REP hashes.",
        "avg_duration_min": 45,
        "mitre_tactics": ["Discovery", "Credential Access"],
        "steps": [
            {"step": 1, "tactic": "Discovery", "technique_id": "T1087.002", "technique_name": "Account Discovery: Domain Account", "tools": ["nmap"], "preconditions": ["domain network access"], "detection_hints": ["LDAP query logs"]},
            {"step": 2, "tactic": "Credential Access", "technique_id": "T1558.004", "technique_name": "AS-REP Roasting", "tools": ["asreproast"], "preconditions": ["pre-auth disabled accounts found"], "detection_hints": ["Kerberos AS-REQ without PA-ENC-TIMESTAMP"]},
            {"step": 3, "tactic": "Credential Access", "technique_id": "T1110.002", "technique_name": "Password Cracking", "tools": ["hashcat"], "preconditions": ["AS-REP hashes captured"], "detection_hints": ["offline — no network detection"]},
        ],
    },
    {
        "id": "mkt-ad-dcSync",
        "name": "Active Directory — DCSync Attack",
        "category": "ad",
        "difficulty": "expert",
        "description": "Replicate domain credentials using DS-Replication-Get-Changes rights.",
        "avg_duration_min": 30,
        "mitre_tactics": ["Credential Access", "Impact"],
        "steps": [
            {"step": 1, "tactic": "Discovery", "technique_id": "T1069.002", "technique_name": "Permission Groups Discovery: Domain Groups", "tools": ["nmap"], "preconditions": ["domain admin or replication rights"], "detection_hints": ["AD event 4662 — Directory Service Access"]},
            {"step": 2, "tactic": "Credential Access", "technique_id": "T1003.006", "technique_name": "OS Credential Dumping: DCSync", "tools": ["responder"], "preconditions": ["replication privileges confirmed"], "detection_hints": ["SIEM: DS-Replication-Get-Changes alerts"]},
        ],
    },
    {
        "id": "mkt-wifi-pentest",
        "name": "Wireless Network Penetration Test",
        "category": "network",
        "difficulty": "medium",
        "description": "Capture WPA2 handshakes, crack PSK, identify rogue APs and evil-twin scenarios.",
        "avg_duration_min": 60,
        "mitre_tactics": ["Reconnaissance", "Initial Access", "Credential Access"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1040", "technique_name": "Network Sniffing", "tools": ["nmap"], "preconditions": ["wireless adapter in monitor mode"], "detection_hints": ["WIDS alerts"]},
            {"step": 2, "tactic": "Credential Access", "technique_id": "T1110", "technique_name": "Brute Force", "tools": ["hashcat"], "preconditions": ["WPA2 handshake captured"], "detection_hints": ["offline — no network detection"]},
            {"step": 3, "tactic": "Initial Access", "technique_id": "T1078", "technique_name": "Valid Accounts", "tools": ["httpx"], "preconditions": ["PSK cracked"], "detection_hints": ["DHCP lease logs"]},
        ],
    },
    {
        "id": "mkt-docker-escape",
        "name": "Container Escape Assessment",
        "category": "cloud",
        "difficulty": "expert",
        "description": "Test container breakout vectors: privileged mode, mounted sockets, kernel exploits.",
        "avg_duration_min": 75,
        "mitre_tactics": ["Privilege Escalation", "Defense Evasion", "Lateral Movement"],
        "steps": [
            {"step": 1, "tactic": "Discovery", "technique_id": "T1613", "technique_name": "Container and Resource Discovery", "tools": ["nmap", "nuclei"], "preconditions": ["container shell access"], "detection_hints": ["Falco runtime rules"]},
            {"step": 2, "tactic": "Privilege Escalation", "technique_id": "T1611", "technique_name": "Escape to Host", "tools": ["nmap"], "preconditions": ["privileged container or docker.sock mounted"], "detection_hints": ["Falco: privileged container spawn"]},
            {"step": 3, "tactic": "Lateral Movement", "technique_id": "T1021.001", "technique_name": "Remote Desktop Protocol", "tools": ["spray"], "preconditions": ["host shell obtained"], "detection_hints": ["Host-level EDR alerts"]},
        ],
    },
    {
        "id": "mkt-graphql-api",
        "name": "GraphQL API Security Audit",
        "category": "api",
        "difficulty": "medium",
        "description": "Introspection abuse, batching attacks, field-level auth bypass, and injection via GraphQL.",
        "avg_duration_min": 40,
        "mitre_tactics": ["Reconnaissance", "Initial Access", "Exfiltration"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1592.002", "technique_name": "Gather Victim Host Information: Software", "tools": ["httpx", "ffuf"], "preconditions": ["GraphQL endpoint found"], "detection_hints": ["introspection rate limits"]},
            {"step": 2, "tactic": "Initial Access", "technique_id": "T1190", "technique_name": "Exploit Public-Facing Application", "tools": ["zap", "nuclei"], "preconditions": ["schema obtained via introspection"], "detection_hints": ["query depth/complexity alerts"]},
            {"step": 3, "tactic": "Exfiltration", "technique_id": "T1041", "technique_name": "Exfiltration Over C2 Channel", "tools": ["sqlmap"], "preconditions": ["IDOR or missing auth on mutation"], "detection_hints": ["large response sizes, anomaly detection"]},
        ],
    },
    # ---------- BATCH 3 (21-30) ----------
    {
        "id": "mkt-thick-client",
        "name": "Thick Client Application Test",
        "category": "web",
        "difficulty": "hard",
        "description": "Memory analysis, traffic interception, and local storage review for desktop apps.",
        "avg_duration_min": 90,
        "mitre_tactics": ["Discovery", "Credential Access", "Collection"],
        "steps": [
            {"step": 1, "tactic": "Discovery", "technique_id": "T1005", "technique_name": "Data from Local System", "tools": ["nmap"], "preconditions": ["application installed"], "detection_hints": ["EDR memory read events"]},
            {"step": 2, "tactic": "Credential Access", "technique_id": "T1552.001", "technique_name": "Credentials In Files", "tools": ["nuclei"], "preconditions": ["config/log files accessible"], "detection_hints": ["file access audit logs"]},
            {"step": 3, "tactic": "Collection", "technique_id": "T1602", "technique_name": "Data from Configuration Repository", "tools": ["httpx"], "preconditions": ["backend API endpoints discovered"], "detection_hints": ["API gateway logs"]},
        ],
    },
    {
        "id": "mkt-oauth-misconfig",
        "name": "OAuth 2.0 Misconfiguration Audit",
        "category": "api",
        "difficulty": "medium",
        "description": "Test for open redirectors, implicit flow abuse, token leakage, and PKCE bypass.",
        "avg_duration_min": 35,
        "mitre_tactics": ["Initial Access", "Credential Access"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1592", "technique_name": "Gather Victim Host Information", "tools": ["httpx", "subfinder"], "preconditions": ["authorization server URL known"], "detection_hints": []},
            {"step": 2, "tactic": "Initial Access", "technique_id": "T1078", "technique_name": "Valid Accounts", "tools": ["zap", "ffuf"], "preconditions": ["redirect_uri whitelist bypass found"], "detection_hints": ["auth server logs"]},
            {"step": 3, "tactic": "Credential Access", "technique_id": "T1539", "technique_name": "Steal Web Session Cookie", "tools": ["nuclei"], "preconditions": ["token leakage via referrer/fragment"], "detection_hints": ["SIEM anomalous token use"]},
        ],
    },
    {
        "id": "mkt-nosql-injection",
        "name": "NoSQL Injection Assessment",
        "category": "web",
        "difficulty": "medium",
        "description": "MongoDB, CouchDB, and Elasticsearch operator injection and auth bypass.",
        "avg_duration_min": 30,
        "mitre_tactics": ["Initial Access", "Exfiltration"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1595.002", "technique_name": "Active Scanning: Vulnerability Scanning", "tools": ["httpx", "nuclei"], "preconditions": ["web app with NoSQL backend"], "detection_hints": []},
            {"step": 2, "tactic": "Initial Access", "technique_id": "T1190", "technique_name": "Exploit Public-Facing Application", "tools": ["zap", "sqlmap"], "preconditions": ["NoSQL injection surface identified"], "detection_hints": ["MongoDB slow query logs"]},
        ],
    },
    {
        "id": "mkt-kubernetes-audit",
        "name": "Kubernetes Cluster Security Audit",
        "category": "cloud",
        "difficulty": "expert",
        "description": "RBAC misconfigs, exposed API server, etcd without auth, pod security policies.",
        "avg_duration_min": 120,
        "mitre_tactics": ["Discovery", "Privilege Escalation", "Lateral Movement", "Collection"],
        "steps": [
            {"step": 1, "tactic": "Discovery", "technique_id": "T1613", "technique_name": "Container and Resource Discovery", "tools": ["nmap", "httpx"], "preconditions": ["cluster API endpoint reachable"], "detection_hints": ["Kubernetes audit logs"]},
            {"step": 2, "tactic": "Privilege Escalation", "technique_id": "T1078.004", "technique_name": "Cloud Accounts", "tools": ["nuclei"], "preconditions": ["service account token found"], "detection_hints": ["RBAC policy violations"]},
            {"step": 3, "tactic": "Lateral Movement", "technique_id": "T1021", "technique_name": "Remote Services", "tools": ["nmap"], "preconditions": ["cluster-admin access"], "detection_hints": ["Pod exec events"]},
            {"step": 4, "tactic": "Collection", "technique_id": "T1552.007", "technique_name": "Container API", "tools": ["httpx"], "preconditions": ["etcd accessible"], "detection_hints": ["etcd access logs"]},
        ],
    },
    {
        "id": "mkt-race-condition",
        "name": "Race Condition & Business Logic Flaws",
        "category": "web",
        "difficulty": "hard",
        "description": "TOCTOU, concurrent request abuse, negative balance, and coupon reuse.",
        "avg_duration_min": 45,
        "mitre_tactics": ["Initial Access", "Impact"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1595.002", "technique_name": "Vulnerability Scanning", "tools": ["httpx", "ffuf"], "preconditions": ["web app in scope"], "detection_hints": []},
            {"step": 2, "tactic": "Initial Access", "technique_id": "T1190", "technique_name": "Exploit Public-Facing Application", "tools": ["zap"], "preconditions": ["concurrent endpoint identified"], "detection_hints": ["DB transaction logs, audit trail"]},
            {"step": 3, "tactic": "Impact", "technique_id": "T1565", "technique_name": "Data Manipulation", "tools": ["sqlmap"], "preconditions": ["race window confirmed"], "detection_hints": ["anomaly detection on business metrics"]},
        ],
    },
    {
        "id": "mkt-sap-erp",
        "name": "SAP ERP Security Assessment",
        "category": "web",
        "difficulty": "expert",
        "description": "RFC enumeration, ICM misconfiguration, and SAP router bypass.",
        "avg_duration_min": 100,
        "mitre_tactics": ["Reconnaissance", "Initial Access", "Privilege Escalation"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1046", "technique_name": "Network Service Discovery", "tools": ["nmap"], "preconditions": ["SAP system IP in scope"], "detection_hints": ["SAP security audit log"]},
            {"step": 2, "tactic": "Initial Access", "technique_id": "T1190", "technique_name": "Exploit Public-Facing Application", "tools": ["nuclei", "httpx"], "preconditions": ["ICM or SAP router exposed"], "detection_hints": ["SM20 audit trail"]},
            {"step": 3, "tactic": "Privilege Escalation", "technique_id": "T1078", "technique_name": "Valid Accounts", "tools": ["spray"], "preconditions": ["SAP login accessible"], "detection_hints": ["failed logon alerts"]},
        ],
    },
    {
        "id": "mkt-citrix-breakout",
        "name": "Citrix / VDI Breakout",
        "category": "network",
        "difficulty": "hard",
        "description": "Escape kiosk mode, bypass application whitelisting, pivot from virtual desktop.",
        "avg_duration_min": 65,
        "mitre_tactics": ["Execution", "Privilege Escalation", "Defense Evasion"],
        "steps": [
            {"step": 1, "tactic": "Execution", "technique_id": "T1059.001", "technique_name": "PowerShell", "tools": ["nmap"], "preconditions": ["Citrix session access"], "detection_hints": ["PowerShell script block logging"]},
            {"step": 2, "tactic": "Defense Evasion", "technique_id": "T1218", "technique_name": "System Binary Proxy Execution", "tools": ["nuclei"], "preconditions": ["AppLocker/SRP bypass found"], "detection_hints": ["process creation events"]},
            {"step": 3, "tactic": "Privilege Escalation", "technique_id": "T1548.002", "technique_name": "Abuse Elevation Control Mechanism: Bypass UAC", "tools": ["spray"], "preconditions": ["local admin rights obtained"], "detection_hints": ["UAC bypass events in SIEM"]},
        ],
    },
    {
        "id": "mkt-email-security",
        "name": "Email Security Posture Review",
        "category": "phishing",
        "difficulty": "easy",
        "description": "SPF/DKIM/DMARC validation, email spoofing tests, and open relay checks.",
        "avg_duration_min": 20,
        "mitre_tactics": ["Reconnaissance", "Resource Development"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1589.002", "technique_name": "Email Addresses", "tools": ["subfinder", "httpx"], "preconditions": ["domain in scope"], "detection_hints": []},
            {"step": 2, "tactic": "Resource Development", "technique_id": "T1583.001", "technique_name": "Acquire Infrastructure: Domains", "tools": ["nuclei"], "preconditions": ["SPF/DKIM/DMARC records pulled"], "detection_hints": ["mail gateway logs"]},
        ],
    },
    {
        "id": "mkt-ssrf-chain",
        "name": "SSRF to Internal Service Pivot",
        "category": "web",
        "difficulty": "hard",
        "description": "Find SSRF, pivot to cloud metadata, internal Redis/ElasticSearch, IMDS abuse.",
        "avg_duration_min": 50,
        "mitre_tactics": ["Initial Access", "Discovery", "Lateral Movement"],
        "steps": [
            {"step": 1, "tactic": "Reconnaissance", "technique_id": "T1595.002", "technique_name": "Vulnerability Scanning", "tools": ["httpx", "ffuf", "nuclei"], "preconditions": ["web app in scope"], "detection_hints": []},
            {"step": 2, "tactic": "Initial Access", "technique_id": "T1190", "technique_name": "Exploit Public-Facing Application", "tools": ["zap", "sqlmap"], "preconditions": ["SSRF parameter identified"], "detection_hints": ["outbound request anomalies"]},
            {"step": 3, "tactic": "Discovery", "technique_id": "T1580", "technique_name": "Cloud Infrastructure Discovery", "tools": ["httpx"], "preconditions": ["SSRF points to metadata service"], "detection_hints": ["cloud provider IMDS logs"]},
            {"step": 4, "tactic": "Lateral Movement", "technique_id": "T1021.002", "technique_name": "SMB/Windows Admin Shares", "tools": ["nmap"], "preconditions": ["internal network reached via SSRF"], "detection_hints": ["internal IDS alerts"]},
        ],
    },
    {
        "id": "mkt-zero-trust-bypass",
        "name": "Zero-Trust Architecture Validation",
        "category": "network",
        "difficulty": "expert",
        "description": "Test microsegmentation, identity verification gaps, and lateral movement in ZTA environments.",
        "avg_duration_min": 150,
        "mitre_tactics": ["Discovery", "Lateral Movement", "Credential Access", "Persistence"],
        "steps": [
            {"step": 1, "tactic": "Discovery", "technique_id": "T1046", "technique_name": "Network Service Discovery", "tools": ["nmap"], "preconditions": ["network access granted"], "detection_hints": ["network flow anomalies"]},
            {"step": 2, "tactic": "Credential Access", "technique_id": "T1557.001", "technique_name": "LLMNR/NBT-NS Poisoning and SMB Relay", "tools": ["responder"], "preconditions": ["LLMNR/NBNS not disabled"], "detection_hints": ["LLMNR/NBNS events in SIEM"]},
            {"step": 3, "tactic": "Lateral Movement", "technique_id": "T1021.006", "technique_name": "Windows Remote Management", "tools": ["nmap", "spray"], "preconditions": ["credentials obtained"], "detection_hints": ["WinRM 5985/5986 connection logs"]},
            {"step": 4, "tactic": "Persistence", "technique_id": "T1098", "technique_name": "Account Manipulation", "tools": ["nuclei"], "preconditions": ["privileged access achieved"], "detection_hints": ["AD object modification events"]},
        ],
    },
]
