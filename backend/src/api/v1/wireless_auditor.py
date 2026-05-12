"""Wireless Auditor API — WiFi security analysis and deauthentication testing.

Wraps system-level 802.11 operations (interface management, AP scanning, client
discovery, deauth packet injection) behind a structured REST API.

All active operations (monitor mode, deauth) require:
  - Linux host
  - Root / CAP_NET_ADMIN + CAP_NET_RAW
  - WiFi adapter supporting monitor mode
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/wireless-auditor",
    tags=["wireless-auditor"],
    dependencies=[Depends(get_current_user)],
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class WifiInterface(BaseModel):
    name: str
    mac: str | None = None
    mode: str | None = None
    state: str | None = None
    supports_monitor: bool = False


class AccessPoint(BaseModel):
    bssid: str
    ssid: str
    channel: int | None = None
    frequency: str | None = None
    signal_dbm: int | None = None
    encryption: str | None = None


class WifiClient(BaseModel):
    mac: str
    signal_dbm: int | None = None
    bssid: str | None = None


class ScanResult(BaseModel):
    interface: str
    access_points: list[AccessPoint]
    scan_time: str
    note: str | None = None


class ClientScanResult(BaseModel):
    interface: str
    gateway_bssid: str
    clients: list[WifiClient]
    scan_time: str


class DeauthRequest(BaseModel):
    interface: str = Field(..., description="WiFi interface in monitor mode")
    gateway_mac: str = Field(..., description="Target AP BSSID")
    target_mac: str = Field(
        default="ff:ff:ff:ff:ff:ff",
        description="Client MAC; ff:ff:ff:ff:ff:ff = broadcast all",
    )
    count: int = Field(default=100, ge=1, le=10000)
    reason_code: int = Field(default=7, ge=1, le=23)


class DeauthResult(BaseModel):
    success: bool
    interface: str
    gateway_mac: str
    target_mac: str
    packets_sent: int
    message: str


class InterfaceModeRequest(BaseModel):
    interface: str
    mode: str = Field(..., pattern="^(monitor|managed)$")


class HardwareStatus(BaseModel):
    platform: str
    is_linux: bool
    has_root: bool
    available_interfaces: list[WifiInterface]
    hardware_ready: bool
    requirements_met: list[str]
    requirements_missing: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def _validate_mac(mac: str) -> bool:
    return bool(_MAC_RE.match(mac))


def _is_root() -> bool:
    try:
        import os
        return os.geteuid() == 0
    except AttributeError:
        return False


def _is_linux() -> bool:
    return sys.platform.startswith("linux")


def _run(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except Exception as exc:
        return -1, "", str(exc)


async def _run_async(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _run(cmd, timeout))


def _parse_iwconfig(output: str, iface: str) -> WifiInterface:
    mode = "unknown"
    mac = None
    mode_m = re.search(r"Mode:(\S+)", output)
    if mode_m:
        mode = mode_m.group(1).lower()
    mac_m = re.search(r"Access Point:\s*([0-9A-Fa-f:]{17})", output)
    if mac_m:
        mac = mac_m.group(1)
    return WifiInterface(
        name=iface,
        mac=mac,
        mode=mode,
        state="up",
        supports_monitor=(mode == "monitor"),
    )


def _list_wifi_interfaces() -> list[WifiInterface]:
    rc, out, _ = _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"])
    interfaces: list[WifiInterface] = []
    if rc != 0:
        rc2, out2, _ = _run(["ip", "-o", "link", "show"])
        for line in out2.splitlines():
            m = re.match(r"\d+:\s+(\w+):", line)
            if m and m.group(1) != "lo":
                interfaces.append(WifiInterface(name=m.group(1)))
        return interfaces
    for line in out.strip().splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[1] in ("wifi", "802-11-wireless"):
            rc3, iw_out, _ = _run(["iwconfig", parts[0]])
            iface = _parse_iwconfig(iw_out, parts[0]) if rc3 == 0 else WifiInterface(name=parts[0])
            interfaces.append(iface)
    return interfaces


def _parse_iwlist_scan(output: str) -> list[AccessPoint]:
    aps: list[AccessPoint] = []
    current: dict[str, Any] = {}
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("Cell"):
            if current and "bssid" in current:
                aps.append(AccessPoint(**current))
            current = {}
            m = re.search(r"Address:\s*([0-9A-Fa-f:]{17})", line)
            if m:
                current["bssid"] = m.group(1).upper()
                current["ssid"] = "<hidden>"
        elif "ESSID:" in line:
            m = re.search(r'ESSID:"(.*?)"', line)
            current["ssid"] = m.group(1) if m else "<hidden>"
        elif "Channel:" in line:
            m = re.search(r"Channel:(\d+)", line)
            if m:
                current["channel"] = int(m.group(1))
        elif "Frequency:" in line:
            m = re.search(r"Frequency:([\d.]+\s*\w+)", line)
            if m:
                current["frequency"] = m.group(1)
        elif "Signal level=" in line:
            m = re.search(r"Signal level=(-?\d+)\s*dBm", line)
            if m:
                current["signal_dbm"] = int(m.group(1))
        elif "IE: WPA" in line or "IE: IEEE 802.11i" in line:
            current["encryption"] = "WPA2" if "WPA2" in line or "802.11i" in line else "WPA"
        elif "Encryption key:on" in line and "encryption" not in current:
            current["encryption"] = "WEP"
        elif "Encryption key:off" in line and "encryption" not in current:
            current["encryption"] = "Open"
    if current and "bssid" in current:
        aps.append(AccessPoint(**current))
    return aps


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=HardwareStatus)
async def get_hardware_status() -> HardwareStatus:
    """Check WiFi hardware availability and capabilities."""
    is_linux = _is_linux()
    has_root = _is_root()
    interfaces = _list_wifi_interfaces() if is_linux else []

    met: list[str] = []
    missing: list[str] = []

    if is_linux:
        met.append("Linux OS")
    else:
        missing.append(f"Linux OS required (current: {sys.platform})")

    if has_root:
        met.append("Root / CAP_NET_ADMIN privileges")
    else:
        missing.append("Root privileges — run container with --privileged or --cap-add=NET_ADMIN,NET_RAW")

    if interfaces:
        met.append(f"WiFi interfaces detected: {', '.join(i.name for i in interfaces)}")
    else:
        missing.append("No WiFi adapter detected — connect a monitor-mode capable adapter")

    rc_iw, _, _ = _run(["which", "iwconfig"])
    if rc_iw == 0:
        met.append("iwconfig available")
    else:
        missing.append("iwconfig not installed (apt install wireless-tools)")

    hardware_ready = is_linux and has_root and bool(interfaces) and rc_iw == 0

    return HardwareStatus(
        platform=sys.platform,
        is_linux=is_linux,
        has_root=has_root,
        available_interfaces=interfaces,
        hardware_ready=hardware_ready,
        requirements_met=met,
        requirements_missing=missing,
    )


@router.get("/interfaces", response_model=list[WifiInterface])
async def list_interfaces() -> list[WifiInterface]:
    """List all WiFi network interfaces."""
    if not _is_linux():
        return []
    return _list_wifi_interfaces()


@router.post("/interfaces/mode")
async def set_interface_mode(req: InterfaceModeRequest) -> dict[str, Any]:
    """Set a WiFi interface to monitor or managed mode."""
    if not _is_linux():
        raise HTTPException(status_code=400, detail="Linux required for interface mode switching")
    if not _is_root():
        raise HTTPException(status_code=403, detail="Root privileges required")

    cmds = [
        ["systemctl", "stop", "NetworkManager"],
        ["ifconfig", req.interface, "down"],
        ["iwconfig", req.interface, "mode", req.mode],
        ["ifconfig", req.interface, "up"],
        ["systemctl", "start", "NetworkManager"],
    ]
    for cmd in cmds:
        rc, _, err = await _run_async(cmd)
        if rc != 0:
            await _run_async(["systemctl", "start", "NetworkManager"])
            raise HTTPException(status_code=500, detail=f"Command failed: {' '.join(cmd)} — {err}")

    return {"success": True, "interface": req.interface, "mode": req.mode}


@router.post("/scan/networks", response_model=ScanResult)
async def scan_networks(interface: str) -> ScanResult:
    """Scan for nearby WiFi access points."""
    if not _is_linux():
        raise HTTPException(status_code=400, detail="Linux required for active WiFi scanning")
    if not _is_root():
        raise HTTPException(status_code=403, detail="Root privileges required")

    rc, out, err = await _run_async(["iwlist", interface, "scan"], timeout=30)
    if rc != 0:
        # Fallback: nmcli
        rc2, out2, _ = await _run_async(
            ["nmcli", "-f", "BSSID,SSID,CHAN,FREQ,SIGNAL,SECURITY", "device", "wifi", "list"],
            timeout=15,
        )
        if rc2 == 0:
            aps: list[AccessPoint] = []
            for line in out2.strip().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        aps.append(AccessPoint(
                            bssid=parts[0],
                            ssid=parts[1] if len(parts) == 5 else " ".join(parts[1:len(parts) - 4]),
                            channel=int(parts[-4]) if parts[-4].isdigit() else None,
                            signal_dbm=int(parts[-2]) if parts[-2].lstrip("-").isdigit() else None,
                            encryption=parts[-1] if parts[-1] != "--" else "Open",
                        ))
                    except Exception:
                        pass
            return ScanResult(
                interface=interface,
                access_points=aps,
                scan_time=datetime.now(timezone.utc).isoformat(),
                note="Scanned via nmcli (iwlist unavailable)",
            )
        raise HTTPException(status_code=500, detail=f"Scan failed: {err}")

    aps = _parse_iwlist_scan(out)
    return ScanResult(
        interface=interface,
        access_points=aps,
        scan_time=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/scan/clients", response_model=ClientScanResult)
async def scan_clients(interface: str, gateway_bssid: str, duration_s: int = 10) -> ClientScanResult:
    """Discover clients connected to a specific access point."""
    if not _is_linux():
        raise HTTPException(status_code=400, detail="Linux required")
    if not _is_root():
        raise HTTPException(status_code=403, detail="Root privileges required")
    if not _validate_mac(gateway_bssid):
        raise HTTPException(status_code=422, detail="Invalid gateway_bssid MAC format")

    duration_s = min(max(duration_s, 5), 30)
    rc, out, err = await _run_async(
        ["tcpdump", "-i", interface, "-e", "-n", "-c", "500",
         f"wlan addr3 {gateway_bssid.lower()}", "--immediate-mode"],
        timeout=duration_s + 5,
    )

    clients: dict[str, WifiClient] = {}
    sa_re = re.compile(r"SA:([0-9a-f:]{17})")
    for line in out.splitlines():
        m = sa_re.search(line.lower())
        if m:
            mac = m.group(1).upper()
            if mac.upper() != gateway_bssid.upper() and mac not in clients:
                clients[mac] = WifiClient(mac=mac, bssid=gateway_bssid)

    return ClientScanResult(
        interface=interface,
        gateway_bssid=gateway_bssid,
        clients=list(clients.values()),
        scan_time=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/deauth", response_model=DeauthResult)
async def deauth_test(req: DeauthRequest) -> DeauthResult:
    """Send 802.11 deauthentication frames for authorized WiFi security testing.

    WARNING: Only use against networks you own or have explicit written permission to test.
    Unauthorized deauthentication is illegal in most jurisdictions.
    """
    if not _is_linux():
        raise HTTPException(status_code=400, detail="Linux required for packet injection")
    if not _is_root():
        raise HTTPException(status_code=403, detail="Root / CAP_NET_RAW required")
    if not _validate_mac(req.gateway_mac):
        raise HTTPException(status_code=422, detail="Invalid gateway_mac")
    if req.target_mac != "ff:ff:ff:ff:ff:ff" and not _validate_mac(req.target_mac):
        raise HTTPException(status_code=422, detail="Invalid target_mac")

    script = (
        "from scapy.all import RadioTap,Dot11,Dot11Deauth,sendp\n"
        f"dot11=Dot11(addr1='{req.target_mac}',addr2='{req.gateway_mac}',addr3='{req.gateway_mac}')\n"
        f"frame=RadioTap()/dot11/Dot11Deauth(reason={req.reason_code})\n"
        f"sendp(frame,iface='{req.interface}',count={req.count},inter=0.05,verbose=0)\n"
        "print('DONE')\n"
    )
    rc, out, err = await _run_async(
        ["python3", "-c", script],
        timeout=int(req.count * 0.06) + 15,
    )

    if "ModuleNotFoundError" in err or "ImportError" in err:
        raise HTTPException(
            status_code=501,
            detail="scapy not installed — add it to the worker image: pip install scapy",
        )
    if rc != 0:
        raise HTTPException(status_code=500, detail=f"Deauth failed: {err.strip() or out.strip()}")

    return DeauthResult(
        success=True,
        interface=req.interface,
        gateway_mac=req.gateway_mac,
        target_mac=req.target_mac,
        packets_sent=req.count,
        message=f"Sent {req.count} deauth frames to {req.target_mac} via AP {req.gateway_mac}",
    )
