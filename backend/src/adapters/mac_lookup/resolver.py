"""MAC address vendor resolver using macvendors.com API and local OUI heuristics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class MacInfo:
    mac_address: str
    oui_prefix: str | None = None
    manufacturer: str | None = None
    manufacturer_country: str | None = None
    device_type: str | None = None
    is_private: bool | None = None
    is_multicast: bool | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:\-.]?){5}[0-9A-Fa-f]{2}$")


def _normalize_mac(mac: str) -> str:
    """Normalize MAC to XX:XX:XX:XX:XX:XX uppercase format."""
    clean = re.sub(r"[^0-9A-Fa-f]", "", mac).upper()
    return ":".join(clean[i : i + 2] for i in range(0, 12, 2))


def _oui_from_mac(mac_normalized: str) -> str:
    """Extract OUI prefix (first 3 octets)."""
    return mac_normalized[:8]


def _is_private_mac(mac_normalized: str) -> bool:
    """Check locally administered bit (second least significant bit of first octet)."""
    first_octet = int(mac_normalized[:2], 16)
    return bool(first_octet & 0x02)


def _is_multicast_mac(mac_normalized: str) -> bool:
    """Check multicast bit (least significant bit of first octet)."""
    first_octet = int(mac_normalized[:2], 16)
    return bool(first_octet & 0x01)


class MacLookupResolver:
    """Resolve MAC address vendor information via macvendors.com API."""

    _API_URL = "https://api.macvendors.com/{mac}"
    _TIMEOUT = 10.0

    async def resolve(self, mac: str) -> MacInfo:
        """Resolve MAC vendor info. Returns partial data on API failure."""
        if not _MAC_RE.match(mac.strip()):
            return MacInfo(
                mac_address=mac,
                raw_data={"error": "Invalid MAC address format"},
            )

        normalized = _normalize_mac(mac)
        oui = _oui_from_mac(normalized)
        is_private = _is_private_mac(normalized)
        is_multicast = _is_multicast_mac(normalized)

        manufacturer: str | None = None
        raw_data: dict[str, Any] = {
            "normalized": normalized,
            "oui": oui,
            "is_private": is_private,
            "is_multicast": is_multicast,
        }

        if not is_private:
            try:
                async with httpx.AsyncClient(timeout=self._TIMEOUT) as client:
                    resp = await client.get(
                        self._API_URL.format(mac=normalized.replace(":", "")),
                        headers={"User-Agent": "OSINT-Platform/1.0"},
                    )
                    if resp.status_code == 200:
                        manufacturer = resp.text.strip()
                        raw_data["api_response"] = manufacturer
                    elif resp.status_code == 404:
                        raw_data["api_response"] = "Unknown vendor"
                    else:
                        raw_data["api_error"] = f"HTTP {resp.status_code}"
            except Exception as exc:
                raw_data["api_error"] = str(exc)

        # Infer device type from common OUI prefixes
        device_type = self._infer_device_type(manufacturer)

        return MacInfo(
            mac_address=normalized,
            oui_prefix=oui,
            manufacturer=manufacturer,
            manufacturer_country=None,  # macvendors.com basic API doesn't return country
            device_type=device_type,
            is_private=is_private,
            is_multicast=is_multicast,
            raw_data=raw_data,
        )

    @staticmethod
    def _infer_device_type(manufacturer: str | None) -> str | None:
        if not manufacturer:
            return None
        m = manufacturer.lower()
        if any(k in m for k in ("apple", "samsung", "huawei", "xiaomi", "oneplus", "google pixel")):
            return "Mobile Device"
        if any(k in m for k in ("cisco", "juniper", "arista", "extreme")):
            return "Network Equipment"
        if any(k in m for k in ("tp-link", "netgear", "asus", "linksys", "ubiquiti", "mikrotik")):
            return "Router / AP"
        if any(k in m for k in ("intel", "realtek", "broadcom", "qualcomm")):
            return "PC / Laptop NIC"
        if any(k in m for k in ("raspberry", "espressif", "arduino")):
            return "IoT / Embedded"
        if any(k in m for k in ("vmware", "virtualbox", "parallels", "hyper-v", "microsoft")):
            return "Virtual Machine"
        return "Unknown"
