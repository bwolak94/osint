"""Chain of Evidence — tamper-evident audit log for OSINT investigations.

Inspired by Hunchly's approach to evidence preservation, this module ensures:
  1. Content integrity — every raw response is SHA-256 hashed.
  2. Chain integrity  — each entry hashes the previous one (blockchain-style).
  3. Archival         — raw response bytes are stored in MinIO for reproduction.
  4. Verification     — verify_chain() detects any post-hoc tampering.

Each EvidenceEntry records:
  - content_hash:    SHA-256 of the raw HTTP response body
  - previous_hash:   SHA-256 of the preceding entry (chain link)
  - entry_hash:      SHA-256 of the entire entry (excluding itself)
  - raw_response_ref: MinIO object key for the archived raw bytes

The chain can be exported as a JSON array and loaded into a separate
verifier process that re-checks all hashes without access to MinIO.

Usage::

    logger = EvidenceLogger(minio_client=minio_instance)

    entry = await logger.log_scan(
        investigation_id=uuid4(),
        scanner_name="shodan",
        input_value="8.8.8.8",
        input_type="ip_address",
        raw_response=resp.content,  # raw bytes from httpx response
        summary={"ports": [80, 443], "vulns": []},
    )

    is_valid, violations = logger.verify_chain()
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from uuid import UUID, uuid4

import structlog

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Evidence entry
# ---------------------------------------------------------------------------


@dataclass
class EvidenceEntry:
    """One tamper-evident node in the evidence chain.

    Fields are intentionally ordered so that ``asdict()`` produces a canonical
    JSON representation for hashing — do NOT reorder them.
    """

    id: str                        = field(default_factory=lambda: str(uuid4()))
    timestamp: str                 = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    investigation_id: str          = ""
    scanner_name: str              = ""
    input_value: str               = ""
    input_type: str                = ""
    status: str                    = "success"  # success | failed | rate_limited
    error: str                     = ""
    # Integrity fields
    content_hash: str              = ""   # SHA-256 of raw response bytes
    previous_hash: str             = ""   # SHA-256 of previous entry's entry_hash
    entry_hash: str                = ""   # SHA-256 of this entry (set last, after all other fields)
    # Storage reference
    raw_response_ref: str          = ""   # MinIO key: "evidence/<inv_id>/<scanner>/<content_hash>.bin"
    # Human-readable summary (key findings only — not hashed separately)
    summary: dict[str, Any]        = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Evidence logger
# ---------------------------------------------------------------------------


class EvidenceLogger:
    """Records OSINT scan results as a hash-chained evidence log.

    Thread/coroutine safety: this class is NOT coroutine-safe by default.
    In production, wrap access with an asyncio.Lock if multiple coroutines
    call log_scan() concurrently on the same instance.
    """

    BUCKET = "osint-evidence"
    GENESIS_HASH = "0" * 64  # SHA-256 of the empty chain

    def __init__(self, minio_client: Any | None = None) -> None:
        """
        Args:
            minio_client: A ``minio.Minio`` instance. If None, archival is
                          skipped but all other functionality works normally.
        """
        self._minio = minio_client
        self._chain: list[EvidenceEntry] = []
        self._last_hash: str = self.GENESIS_HASH

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    async def log_scan(
        self,
        investigation_id: UUID,
        scanner_name: str,
        input_value: str,
        input_type: str,
        raw_response: bytes | dict[str, Any] | str,
        summary: dict[str, Any],
        status: str = "success",
        error: str = "",
    ) -> EvidenceEntry:
        """Record one scan result in the chain.

        Args:
            investigation_id: UUID of the owning investigation.
            scanner_name:     Name of the scanner (e.g. "shodan").
            input_value:      The query value (e.g. "8.8.8.8").
            input_type:       Entity type string (e.g. "ip_address").
            raw_response:     Raw HTTP response body (bytes), parsed dict, or string.
                              All forms are serialised to bytes before hashing.
            summary:          Key findings dictionary stored alongside the entry.
            status:           "success", "failed", or "rate_limited".
            error:            Error message if status is not "success".

        Returns:
            The completed and fully-hashed EvidenceEntry.
        """
        raw_bytes = self._normalise_response(raw_response)
        content_hash = hashlib.sha256(raw_bytes).hexdigest()

        # Archive raw bytes to MinIO (best-effort)
        archive_key = await self._archive(
            investigation_id=str(investigation_id),
            scanner_name=scanner_name,
            content_hash=content_hash,
            raw_bytes=raw_bytes,
        )

        entry = EvidenceEntry(
            investigation_id=str(investigation_id),
            scanner_name=scanner_name,
            input_value=input_value,
            input_type=input_type,
            status=status,
            error=error,
            content_hash=content_hash,
            previous_hash=self._last_hash,
            raw_response_ref=archive_key,
            summary=summary,
        )

        # Compute entry_hash over the serialised entry (entry_hash field is empty at this point)
        entry_dict = asdict(entry)
        del entry_dict["entry_hash"]  # Exclude self-reference from hash input
        canonical_json = json.dumps(entry_dict, sort_keys=True, default=str, ensure_ascii=False)
        entry.entry_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        self._chain.append(entry)
        self._last_hash = entry.entry_hash

        log.info(
            "Evidence logged",
            investigation_id=str(investigation_id),
            scanner=scanner_name,
            input=input_value,
            content_hash=content_hash[:16] + "...",
            entry_hash=entry.entry_hash[:16] + "...",
            chain_length=len(self._chain),
            archived=bool(archive_key),
        )
        return entry

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_chain(self) -> tuple[bool, list[str]]:
        """Verify the cryptographic integrity of the full evidence chain.

        Checks:
        1. Each entry's previous_hash matches the preceding entry's entry_hash.
        2. Each entry's entry_hash matches a freshly computed hash of the entry.

        Returns:
            (is_valid, violations) — is_valid is True iff violations is empty.
        """
        violations: list[str] = []
        expected_prev_hash = self.GENESIS_HASH

        for i, entry in enumerate(self._chain):
            # Check chain linkage
            if entry.previous_hash != expected_prev_hash:
                violations.append(
                    f"Entry[{i}] id={entry.id}: previous_hash mismatch. "
                    f"Expected {expected_prev_hash[:16]}… "
                    f"got {entry.previous_hash[:16]}…"
                )

            # Recompute entry hash
            entry_dict = asdict(entry)
            stored = entry_dict.pop("entry_hash")
            canonical = json.dumps(entry_dict, sort_keys=True, default=str, ensure_ascii=False)
            recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

            if recomputed != stored:
                violations.append(
                    f"Entry[{i}] id={entry.id} scanner={entry.scanner_name}: "
                    f"entry_hash mismatch — stored {stored[:16]}… "
                    f"recomputed {recomputed[:16]}… (possible tampering)"
                )

            expected_prev_hash = entry.entry_hash

        is_valid = len(violations) == 0
        log.info(
            "Chain verification complete",
            valid=is_valid,
            entries=len(self._chain),
            violations=len(violations),
        )
        return is_valid, violations

    # ------------------------------------------------------------------
    # Export / Import
    # ------------------------------------------------------------------

    def export_chain(self) -> list[dict[str, Any]]:
        """Serialise the full chain to a list of dicts suitable for JSON persistence."""
        return [asdict(entry) for entry in self._chain]

    @classmethod
    def import_chain(cls, data: list[dict[str, Any]], minio_client: Any | None = None) -> "EvidenceLogger":
        """Reconstruct an EvidenceLogger from a previously exported chain.

        The imported logger can be used with verify_chain() to validate
        a chain without re-running any scans.
        """
        instance = cls(minio_client=minio_client)
        for entry_dict in data:
            entry = EvidenceEntry(**entry_dict)
            instance._chain.append(entry)
            instance._last_hash = entry.entry_hash
        return instance

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def chain_length(self) -> int:
        return len(self._chain)

    @property
    def tip_hash(self) -> str:
        """Hash of the most recent entry (the chain tip)."""
        return self._last_hash

    @property
    def is_empty(self) -> bool:
        return len(self._chain) == 0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_response(raw: bytes | dict[str, Any] | str) -> bytes:
        """Convert any response type to a canonical byte string for hashing."""
        if isinstance(raw, bytes):
            return raw
        if isinstance(raw, dict):
            return json.dumps(raw, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
        return str(raw).encode("utf-8")

    async def _archive(
        self,
        investigation_id: str,
        scanner_name: str,
        content_hash: str,
        raw_bytes: bytes,
    ) -> str:
        """Store raw bytes in MinIO under a deterministic object key.

        Returns the object key on success, or empty string on failure.
        MinIO's put_object is synchronous, so we run it in a thread executor.
        """
        if self._minio is None:
            return ""

        object_key = f"evidence/{investigation_id}/{scanner_name}/{content_hash}.bin"
        try:
            import asyncio

            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._minio.put_object(
                    self.BUCKET,
                    object_key,
                    BytesIO(raw_bytes),
                    length=len(raw_bytes),
                    content_type="application/octet-stream",
                    metadata={
                        "investigation_id": investigation_id,
                        "scanner": scanner_name,
                        "sha256": content_hash,
                    },
                ),
            )
            log.debug("Evidence archived", key=object_key, bytes=len(raw_bytes))
            return object_key
        except Exception as exc:
            log.error("MinIO archive failed", key=object_key, error=str(exc))
            return ""
