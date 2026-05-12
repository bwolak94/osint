"""Password Hash Analyzer scanner — identify hash algorithms and compute K^L brute-force complexity.

Module 42 in the Credential Intelligence domain. Analyzes a hash string to identify its
algorithm by pattern matching, then computes the C = K^L formula for various charsets and
lengths to illustrate why password length dominates security.
"""

from __future__ import annotations

import re
from typing import Any

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

# Pattern-based hash recognition
_HASH_PATTERNS: list[tuple[str, str, str, str]] = [
    # (regex, algorithm, security_rating, note)
    (r"^[0-9a-fA-F]{32}$",  "MD5",    "Broken",   "MD5 is cryptographically broken; collision attacks exist since 2004. GPU: ~100 billion hashes/sec."),
    (r"^[0-9a-fA-F]{40}$",  "SHA-1",  "Broken",   "SHA-1 is deprecated for security use; SHAttered collision published 2017. Still faster than bcrypt."),
    (r"^[0-9a-fA-F]{64}$",  "SHA-256","Moderate", "SHA-256 is fast — unsuitable for passwords. Use only for data integrity, not credential hashing."),
    (r"^[0-9a-fA-F]{128}$", "SHA-512","Moderate", "SHA-512 is fast like SHA-256. GPU throughput: ~4 billion/sec. Not a password hash function."),
    (r"^\$2[aby]\$\d{2}\$", "bcrypt", "Strong",   "bcrypt uses a cost factor to slow attacks. 4× RTX 4090: ~200k hashes/sec at cost=12."),
    (r"^\$argon2",          "Argon2", "Very Strong","Argon2 is the Password Hashing Competition winner (2015). Resistant to GPU/ASIC attacks."),
    (r"^\$6\$",             "SHA-512crypt", "Strong", "Linux /etc/shadow SHA-512 with salt and 5000 rounds. Better than plain SHA-512."),
    (r"^\$5\$",             "SHA-256crypt", "Moderate", "Linux /etc/shadow SHA-256 with salt and 5000 rounds."),
    (r"^pbkdf2_sha",        "PBKDF2", "Strong",   "PBKDF2 with configurable iterations. Django/NIST recommended; weaker than bcrypt at high GPU parallelism."),
    (r"^[0-9a-fA-F]{56}$",  "SHA-224","Moderate", "SHA-224 truncated variant. Fast and unsuitable for password storage."),
    (r"^[0-9a-fA-F]{96}$",  "SHA-384","Moderate", "SHA-384 truncated variant. Fast and unsuitable for password storage."),
]

# Charset definitions: (key, description, size, example_chars)
_CHARSETS: list[tuple[str, str, int]] = [
    ("digits_only",     "Digits only (0-9)",                   10),
    ("lowercase",       "Lowercase letters (a-z)",             26),
    ("alpha",           "Letters (a-zA-Z)",                    52),
    ("alphanumeric",    "Alphanumeric (a-zA-Z0-9)",            62),
    ("printable_ascii", "Printable ASCII (all symbols)",       95),
]

# SHA-256 crack speed (4× RTX 4090): ~100 billion hashes/sec
_SHA256_SPEED = 100_000_000_000


def _format_combinations(n: float) -> str:
    """Format a large number in scientific-like notation."""
    if n < 1e6:
        return f"{int(n):,}"
    exp = 0
    m = n
    while m >= 10:
        m /= 10
        exp += 1
    return f"{m:.1f}×10^{exp}"


def _format_crack_time(seconds: float) -> str:
    """Convert seconds to a human-readable time estimate."""
    if seconds < 1:
        return "< 1 second"
    if seconds < 60:
        return f"{int(seconds)} seconds"
    if seconds < 3600:
        return f"{int(seconds / 60)} minutes"
    if seconds < 86400:
        return f"{int(seconds / 3600)} hours"
    if seconds < 86400 * 365:
        days = int(seconds / 86400)
        return f"{days} days"
    years = seconds / (86400 * 365)
    if years < 1_000:
        return f"{int(years)} years"
    if years < 1e12:
        exp = 0
        m = years
        while m >= 10:
            m /= 10
            exp += 1
        return f"{m:.1f}×10^{exp} years"
    return "Effectively uncrackable"


def _build_complexity_table() -> list[dict[str, Any]]:
    """Build the full K^L complexity table for all charsets and common lengths."""
    rows: list[dict[str, Any]] = []
    for length in [6, 8, 10, 12, 16, 20]:
        for charset_key, charset_desc, k in _CHARSETS:
            combinations = float(k ** length)
            crack_seconds = combinations / _SHA256_SPEED
            rows.append({
                "length": length,
                "charset": charset_key,
                "charset_description": charset_desc,
                "charset_size": k,
                "combinations": _format_combinations(combinations),
                "crack_time_sha256_4gpu": _format_crack_time(crack_seconds),
            })
    return rows


class PasswordHashAnalyzerScanner(BaseOsintScanner):
    """Identify a password hash algorithm and compute K^L brute-force complexity metrics.

    Accepts any string as DOMAIN input (acting as a generic string carrier).
    Detects algorithm via regex, rates security, and generates a complexity table
    for the educational C = K^L visualization in the frontend.
    """

    scanner_name = "password_hash_analyzer"
    # Use DOMAIN as a generic string input type; the value is the hash to analyze
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 0  # No caching — deterministic result

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        hash_str = input_value.strip()

        algorithm: str | None = None
        security_rating: str = "Unknown"
        educational_note: str = "Hash format not recognized. Check the input value."

        for pattern, algo, rating, note in _HASH_PATTERNS:
            if re.match(pattern, hash_str):
                algorithm = algo
                security_rating = rating
                educational_note = note
                break

        if algorithm is None:
            return {
                "found": False,
                "hash": hash_str,
                "hash_length": len(hash_str),
                "reason": "Unrecognized hash format",
            }

        return {
            "found": True,
            "hash": hash_str[:16] + "…",  # Truncate in response for readability
            "hash_length": len(hash_str),
            "algorithm": algorithm,
            "security_rating": security_rating,
            "educational_note": educational_note,
            "complexity_table": _build_complexity_table(),
        }
