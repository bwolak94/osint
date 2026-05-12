#!/usr/bin/env python3
"""
Run all scanner modules visible in the dashboard history.
Authenticates as admin@osint.platform and fires every scan endpoint
with realistic test data. Logs result status for each module.
"""

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = "http://localhost"
EMAIL = "admin@osint.platform"
PASSWORD = "admin"

# ── Test inputs ──────────────────────────────────────────────────────────────
DOMAIN   = "example.com"
IP       = "8.8.8.8"
EMAIL_T  = "test@example.com"
USERNAME = "testuser"
URL_T    = "https://example.com"
MAC      = "00:11:22:33:44:55"
COORDS   = "51.5074,-0.1278"  # London

# Minimal raw email headers for email-headers module
RAW_HEADERS = (
    "Delivered-To: test@example.com\r\n"
    "Received: from mail.example.com (mail.example.com [93.184.216.34])\r\n"
    "        by mx.example.com with ESMTP id abc123\r\n"
    "        for <test@example.com>; Mon, 1 Jan 2024 12:00:00 +0000 (UTC)\r\n"
    "From: sender@example.com\r\n"
    "To: test@example.com\r\n"
    "Subject: Test\r\n"
    "Date: Mon, 1 Jan 2024 12:00:00 +0000\r\n"
    "Message-ID: <unique@example.com>\r\n"
)

# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _request(method: str, path: str, body=None, token: str = "", content_type: str = "application/json") -> tuple[int, dict]:
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": content_type, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            body_err = json.loads(e.read())
        except Exception:
            body_err = {"error": str(e)}
        return e.code, body_err
    except Exception as e:
        return 0, {"error": str(e)}


def login() -> str:
    status, data = _request("POST", "/api/v1/auth/login",
                             {"email": EMAIL, "password": PASSWORD})
    if status != 200 or "access_token" not in data:
        print(f"  ✗ Login failed ({status}): {data}", file=sys.stderr)
        sys.exit(1)
    print(f"  ✓ Logged in as {EMAIL}")
    return data["access_token"]


def run(label: str, method: str, path: str, body, token: str, ok_statuses=(200, 201, 202)) -> None:
    status, resp = _request(method, path, body, token)
    symbol = "✓" if status in ok_statuses else "✗"
    detail = ""
    if status not in ok_statuses:
        detail = f" → {json.dumps(resp)[:120]}"
    print(f"  {symbol} [{status}] {label}{detail}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n=== OSINT Platform — Full Scanner Run ===\n")

    # ── Auth ──────────────────────────────────────────────────────────────────
    print("[ AUTH ]")
    tok = login()

    # ── 1. Image Checker (file upload — skip binary, POST JSON placeholder) ───
    # The image-checker endpoint requires multipart; we POST to the history
    # list endpoint to confirm the table exists, then note upload is manual.
    print("\n[ 1 ] Image Checker")
    run("GET history", "GET", "/api/v1/image-checker/", None, tok)

    # ── 2. Document Metadata ──────────────────────────────────────────────────
    print("\n[ 2 ] Document Metadata Extractor")
    run("GET history", "GET", "/api/v1/doc-metadata/", None, tok)

    # ── 3. Email Headers ──────────────────────────────────────────────────────
    print("\n[ 3 ] Email Headers Analyzer")
    run("analyze headers", "POST", "/api/v1/email-headers/",
        {"raw_headers": RAW_HEADERS}, tok)
    run("GET history", "GET", "/api/v1/email-headers/", None, tok)

    # ── 4. MAC Lookup ─────────────────────────────────────────────────────────
    print("\n[ 4 ] MAC Address Lookup")
    run("lookup 00:11:22:33:44:55", "POST", "/api/v1/mac-lookup/",
        {"mac_address": MAC}, tok)
    run("lookup Apple OUI",         "POST", "/api/v1/mac-lookup/",
        {"mac_address": "00:1A:2B:3C:4D:5E"}, tok)
    run("GET history", "GET", "/api/v1/mac-lookup/", None, tok)

    # ── 5. Domain Permutation ─────────────────────────────────────────────────
    print("\n[ 5 ] Domain Permutation Scanner")
    run("permute example.com", "POST", "/api/v1/domain-permutation/",
        {"domain": DOMAIN}, tok)
    run("GET history", "GET", "/api/v1/domain-permutation/", None, tok)

    # ── 6. Cloud Storage Exposure ─────────────────────────────────────────────
    print("\n[ 6 ] Cloud Storage Exposure")
    run("scan example.com", "POST", "/api/v1/cloud-exposure/",
        {"target": DOMAIN}, tok)
    run("GET history", "GET", "/api/v1/cloud-exposure/", None, tok)

    # ── 7. Stealer Logs ───────────────────────────────────────────────────────
    print("\n[ 7 ] Stealer Logs Intelligence")
    run("query email",  "POST", "/api/v1/stealer-logs/",
        {"query": EMAIL_T, "query_type": "email"}, tok)
    run("query domain", "POST", "/api/v1/stealer-logs/",
        {"query": DOMAIN, "query_type": "domain"}, tok)
    run("GET history",  "GET",  "/api/v1/stealer-logs/", None, tok)

    # ── 8. Supply Chain ───────────────────────────────────────────────────────
    print("\n[ 8 ] Supply Chain Intelligence")
    run("scan domain",    "POST", "/api/v1/supply-chain/",
        {"target": DOMAIN, "target_type": "domain"}, tok)
    run("scan github_user", "POST", "/api/v1/supply-chain/",
        {"target": USERNAME, "target_type": "github_user"}, tok)
    run("GET history",    "GET",  "/api/v1/supply-chain/", None, tok)

    # ── 9. Fediverse ──────────────────────────────────────────────────────────
    print("\n[ 9 ] Fediverse / Mastodon OSINT")
    run("query username", "POST", "/api/v1/fediverse/",
        {"query": USERNAME}, tok)
    run("GET history",    "GET",  "/api/v1/fediverse/", None, tok)

    # ── 10. WiGLE ────────────────────────────────────────────────────────────
    print("\n[ 10 ] WiGLE WiFi Geolocation")
    run("lookup SSID",  "POST", "/api/v1/wigle/",
        {"query": "TestNetwork", "query_type": "ssid"}, tok)
    run("lookup BSSID", "POST", "/api/v1/wigle/",
        {"query": MAC, "query_type": "bssid"}, tok)
    run("GET history",  "GET",  "/api/v1/wigle/", None, tok)

    # ── 11. Tech Recon ────────────────────────────────────────────────────────
    print("\n[ 11 ] Tech Recon Scanner")
    run("scan example.com (all modules)", "POST", "/api/v1/tech-recon/",
        {"target": DOMAIN, "modules": None}, tok)
    run("scan 8.8.8.8",                  "POST", "/api/v1/tech-recon/",
        {"target": IP, "modules": None}, tok)
    run("GET history",                   "GET",  "/api/v1/tech-recon/", None, tok)

    # ── 12. SOCMINT ───────────────────────────────────────────────────────────
    print("\n[ 12 ] SOCMINT (Social Media Intelligence)")
    run("scan username", "POST", "/api/v1/socmint/",
        {"target": USERNAME, "target_type": "username"}, tok)
    run("scan email",    "POST", "/api/v1/socmint/",
        {"target": EMAIL_T, "target_type": "email"}, tok)
    run("GET history",   "GET",  "/api/v1/socmint/", None, tok)

    # ── 13. Credential Intel ──────────────────────────────────────────────────
    print("\n[ 13 ] Credential Intelligence")
    run("scan email",  "POST", "/api/v1/credential-intel/",
        {"target": EMAIL_T, "target_type": "email"}, tok)
    run("scan domain", "POST", "/api/v1/credential-intel/",
        {"target": DOMAIN, "target_type": "domain"}, tok)
    run("GET history", "GET",  "/api/v1/credential-intel/", None, tok)

    # ── 14. IMINT / GEOINT ────────────────────────────────────────────────────
    print("\n[ 14 ] IMINT / GEOINT")
    run("scan coordinates", "POST", "/api/v1/imint/",
        {"target": COORDS, "modules": None}, tok)
    run("scan image URL",   "POST", "/api/v1/imint/",
        {"target": URL_T, "modules": None}, tok)
    run("GET history",      "GET",  "/api/v1/imint/", None, tok)

    # ── 15-34. Pentesting Modules (81-100) ────────────────────────────────────
    print("\n[ 15-34 ] Pentesting Modules (81-100)")

    pent = [
        ("81 XSS Payload Tester",       "POST", "/api/v1/pentesting/xss-test",
         {"target_url": URL_T}),
        ("82 SQLi Vulnerability Lab",    "POST", "/api/v1/pentesting/sqli-test",
         {"target_url": URL_T}),
        ("83 Packet Crafter",            "POST", "/api/v1/pentesting/packet-craft",
         {"target_ip": IP, "protocol": "TCP", "port": 80}),
        ("84 Fuzzing Engine",            "POST", "/api/v1/pentesting/fuzzing",
         {"target_url": URL_T}),
        ("85 Directory Buster",          "POST", "/api/v1/pentesting/directory-bust",
         {"target": DOMAIN}),
        ("86 Shellcode Playground",      "POST", "/api/v1/pentesting/shellcode",
         {"architecture": "x86_64", "operation": "execve"}),
        ("87 Metasploit Bridge",         "POST", "/api/v1/pentesting/metasploit-bridge",
         {"host": IP, "module": "auxiliary/scanner/portscan/tcp"}),
        ("88 ARP Spoofing Lab",          "POST", "/api/v1/pentesting/arp-spoof",
         {"target_ip": IP, "gateway_ip": "192.168.1.1", "simulate": True}),
        ("89 Deauth Tool",               "POST", "/api/v1/pentesting/deauth",
         {"bssid": "AA:BB:CC:DD:EE:FF", "simulate": True}),
        ("90 Reverse Shell Handler",     "POST", "/api/v1/pentesting/reverse-shell",
         {"lhost": "10.0.0.1", "lport": 4444, "shell_type": "bash"}),
        ("91 SSH Brute Force Lab",       "POST", "/api/v1/pentesting/ssh-brute",
         {"target_ip": IP, "username": "root"}),
        ("92 CSRF Simulator",            "POST", "/api/v1/pentesting/csrf-sim",
         {"target_url": URL_T, "method": "POST"}),
        ("93 Buffer Overflow Viz",       "POST", "/api/v1/pentesting/buffer-overflow",
         {"buffer_size": 64, "input_size": 128}),
        ("94 Encryption Sandbox",        "POST", "/api/v1/pentesting/encryption-sandbox",
         {"target": DOMAIN}),
        ("95 Binary String Extractor",   "POST", "/api/v1/pentesting/binary-strings",
         {"url": "https://example.com/file.txt"}),
        ("96 Phishing Campaign Gen",     "POST", "/api/v1/pentesting/phishing-gen",
         {"brand": "TestCorp", "template": "login"}),
        ("97 Keylogger Simulator",       "POST", "/api/v1/pentesting/keylogger-sim",
         {"os_type": "windows"}),
        ("98 Ransomware Simulator",      "POST", "/api/v1/pentesting/ransomware-sim",
         {"simulation_mode": True, "file_count": 3}),
        ("99 IDS Rule Generator",        "POST", "/api/v1/pentesting/ids-rules",
         {"target": IP}),
        ("100 Automated Reporting",      "POST", "/api/v1/pentesting/report",
         {"investigation_id": "00000000-0000-0000-0000-000000000000",
          "format": "html", "include_modules": []}),
    ]
    for label, method, path, body in pent:
        run(label, method, path, body, tok)
        time.sleep(0.2)

    # ── 35-64. Red Team Modules (101-130) ─────────────────────────────────────
    print("\n[ 35-64 ] Red Team Modules (101-130)")

    red = [
        ("101 JWT Security Auditor",     "/api/v1/redteam/jwt-audit",
         {"target_url": URL_T}),
        ("102 AWS IAM Auditor",          "/api/v1/redteam/aws-iam",
         {"target_domain": DOMAIN}),
        ("103 Cloud Storage Hunter",     "/api/v1/redteam/cloud-hunt",
         {"target_domain": DOMAIN, "providers": ["s3", "azure", "gcp"]}),
        ("104 CI/CD Secret Scanner",     "/api/v1/redteam/cicd-scan",
         {"target_url": URL_T}),
        ("105 IaC Policy Linter",        "/api/v1/redteam/iac-lint",
         {"content": 'resource "aws_s3_bucket" "b" { bucket = "my-bucket" }',
          "file_type": "terraform"}),
        ("106 Supply Chain Simulator",   "/api/v1/redteam/supply-chain",
         {"package_name": "osint-internal-utils", "registry": "pypi"}),
        ("107 API Security Scanner",     "/api/v1/redteam/api-scan",
         {"target_url": URL_T}),
        ("108 Registry Persistence Lab", "/api/v1/redteam/registry-persist",
         {"payload": "calc.exe", "simulate": True}),
        ("109 WMI Persistence Engine",   "/api/v1/redteam/wmi-persist",
         {"command": "cmd.exe /c whoami", "trigger": "startup", "simulate": True}),
        ("110 NTLM Relay Automator",     "/api/v1/redteam/ntlm-relay",
         {"target_ip": IP, "simulate": True}),
        ("111 Kerberoasting Toolkit",    "/api/v1/redteam/kerberoast",
         {"domain": DOMAIN}),
        ("112 BloodHound Viz Bridge",    "/api/v1/redteam/bloodhound",
         {"domain": DOMAIN, "query_type": "shortest_path"}),
        ("113 AD Coercion Simulator",    "/api/v1/redteam/ad-coerce",
         {"target": IP, "method": "printerbug", "simulate": True}),
        ("114 AI Prompt Injector",       "/api/v1/redteam/prompt-inject",
         {"endpoint_url": URL_T, "payload_type": "direct"}),
        ("115 Container Escape Auditor", "/api/v1/redteam/container-escape",
         {"target": IP}),
        ("116 Zero Trust Policy Viz",    "/api/v1/redteam/zero-trust",
         {"network_segments": [{"name": "DMZ", "cidr": "10.0.1.0/24"},
                                {"name": "Internal", "cidr": "10.0.2.0/24"}],
          "policies": []}),
        ("117 Payload Evasion Engine",   "/api/v1/redteam/payload-evade",
         {"target_url": URL_T}),
        ("118 Memory Forensics Tool",    "/api/v1/redteam/memory-forensics",
         {"dump_url": "", "process_filter": "lsass"}),
        ("119 C2 Channel Simulator",     "/api/v1/redteam/c2-channel",
         {"c2_type": "dns", "domain": DOMAIN, "simulate": True}),
        ("120 EDR/AV Checker",           "/api/v1/redteam/edr-check",
         {"target_ip": IP}),
        ("121 AD CS Abuse Module",       "/api/v1/redteam/adcs-abuse",
         {"domain": DOMAIN}),
        ("122 GraphQL Depth Auditor",    "/api/v1/redteam/graphql-audit",
         {"target_url": URL_T, "max_depth": 5}),
        ("123 TOCTOU Visualizer",        "/api/v1/redteam/toctou",
         {"scenario": "file_check", "race_window_ms": 50}),
        ("124 APK Static Analyzer",      "/api/v1/redteam/apk-analyze",
         {"apk_url": "https://example.com/app.apk"}),
        ("125 Dangling DNS Scanner",     "/api/v1/redteam/dangling-dns",
         {"domain": DOMAIN}),
        ("126 MITRE ATT&CK Mapper",     "/api/v1/redteam/mitre-map",
         {"techniques": ["T1078", "T1110", "T1566", "T1059", "T1486"]}),
        ("127 Threat Intel Aggregator",  "/api/v1/redteam/threat-intel",
         {"target": IP}),
        ("128 Dynamic Firewall Enforcer","/api/v1/redteam/firewall-enforce",
         {"action": "block", "ip": "1.2.3.4", "reason": "portscan",
          "simulate": True}),
        ("129 DFIR Evidence Pipeline",   "/api/v1/redteam/dfir-collect",
         {"target_ip": IP, "collect_types": ["logs", "processes", "network"]}),
        ("130 OSCP-Style Reporter",      "/api/v1/redteam/oscp-report",
         {"investigation_id": "00000000-0000-0000-0000-000000000000",
          "findings": [{"title": "Test Finding", "severity": "High",
                         "description": "Demo", "poc": "curl -v ...",
                         "remediation": "Patch it"}]}),
    ]
    for label, path, body in red:
        run(label, "POST", path, body, tok)
        time.sleep(0.2)

    print("\n=== Done ===\n")


if __name__ == "__main__":
    main()
