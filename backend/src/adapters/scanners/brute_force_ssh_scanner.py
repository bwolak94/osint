"""Brute Force Lab (SSH) — checks SSH port availability and default credential exposure.

Module 91 in the Infrastructure & Exploitation domain. Checks whether the SSH port
is open on the target IP address and reads the authentication banner. Tests a tiny
set of five well-known default credentials to illustrate how default passwords
are exploited. Educational tool only — not intended for unauthorised access.
"""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_SSH_PORT = 22
_BANNER_TIMEOUT = 5.0
_AUTH_TIMEOUT = 8.0

# Tiny set of universally-known default/weak credentials for educational illustration
_DEFAULT_CREDENTIALS: list[tuple[str, str]] = [
    ("root", "root"),
    ("root", "password"),
    ("admin", "admin"),
    ("admin", "password"),
    ("ubuntu", "ubuntu"),
]


async def _check_ssh_port(host: str, port: int = _SSH_PORT) -> tuple[bool, str]:
    """Return (port_open, banner_text) for the target SSH port."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=_BANNER_TIMEOUT,
        )
        banner = ""
        try:
            data = await asyncio.wait_for(reader.read(512), timeout=_BANNER_TIMEOUT)
            banner = data.decode("utf-8", errors="replace").strip()
        except asyncio.TimeoutError:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        return True, banner
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return False, ""


async def _test_credential(host: str, port: int, username: str, password: str) -> dict[str, Any]:
    """Attempt SSH authentication and return a result record.

    Uses raw socket banner reading + asyncssh if available, otherwise
    falls back to a simulated auth-attempt record without a real connection.
    """
    result: dict[str, Any] = {
        "username": username,
        "password": "***" + password[-1] if len(password) > 1 else "***",  # Obfuscate
        "auth_result": "not_tested",
        "error": None,
    }

    try:
        import asyncssh  # type: ignore[import-untyped]

        conn = await asyncio.wait_for(
            asyncssh.connect(
                host,
                port=port,
                username=username,
                password=password,
                known_hosts=None,
                login_timeout=_AUTH_TIMEOUT,
            ),
            timeout=_AUTH_TIMEOUT,
        )
        conn.close()
        result["auth_result"] = "success"
        log.warning("SSH default credential accepted", host=host, username=username)
    except ImportError:
        # asyncssh not installed — record as simulation only
        result["auth_result"] = "simulation_no_asyncssh"
        result["error"] = "asyncssh not installed; install with: pip install asyncssh"
    except asyncio.TimeoutError:
        result["auth_result"] = "timeout"
    except Exception as exc:
        error_str = str(exc).lower()
        if "permission denied" in error_str or "authentication failed" in error_str:
            result["auth_result"] = "rejected"
        else:
            result["auth_result"] = "error"
            result["error"] = str(exc)

    return result


class BruteForceSSHScanner(BaseOsintScanner):
    """Checks SSH port availability and tests a minimal set of default credentials.

    Demonstrates the risk of default/weak SSH credentials on exposed services.
    Tests only five universally-known pairs. Only targets the IP supplied by the user
    (Module 91). Never use this tool against systems without explicit authorisation.
    """

    scanner_name = "brute_force_ssh"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS})
    cache_ttl = 1800  # 30 minutes

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        host = input_value.strip()

        ssh_open, auth_banner = await _check_ssh_port(host, _SSH_PORT)

        if not ssh_open:
            return {
                "target": host,
                "ssh_port": _SSH_PORT,
                "ssh_port_open": False,
                "auth_banner": "",
                "tested_credentials": [],
                "successful_logins": [],
                "found": False,
                "severity": "None",
                "educational_note": (
                    "SSH port 22 is closed or filtered on this target. "
                    "No credential testing was performed."
                ),
            }

        # Identify server software from banner
        banner_info = {
            "raw": auth_banner,
            "server_software": "",
        }
        if "OpenSSH" in auth_banner:
            banner_info["server_software"] = auth_banner.split("\n")[0].strip()

        # Test credentials sequentially to avoid concurrent auth noise
        credential_results: list[dict[str, Any]] = []
        successful_logins: list[str] = []

        for username, password in _DEFAULT_CREDENTIALS:
            cred_result = await _test_credential(host, _SSH_PORT, username, password)
            credential_results.append(cred_result)
            if cred_result["auth_result"] == "success":
                successful_logins.append(username)

        found = len(successful_logins) > 0
        severity = "Critical" if found else "Medium"

        return {
            "target": host,
            "ssh_port": _SSH_PORT,
            "ssh_port_open": True,
            "auth_banner": banner_info,
            "tested_credentials": credential_results,
            "successful_logins": successful_logins,
            "found": found,
            "severity": severity,
            "educational_note": (
                "Default and weak SSH credentials are one of the most common entry vectors "
                "in network penetration testing. Organisations should enforce key-based "
                "authentication and disable password login. Tested only 5 well-known defaults."
            ),
            "recommendations": [
                "Disable SSH password authentication; use public-key auth only.",
                "Restrict SSH access to specific source IPs via firewall rules.",
                "Change all default credentials immediately on new deployments.",
                "Enable fail2ban or equivalent to limit brute-force attempts.",
                "Monitor /var/log/auth.log for repeated failed authentication attempts.",
            ],
        }
