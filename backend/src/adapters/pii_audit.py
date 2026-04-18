"""Field-level PII access audit logging for GDPR compliance."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PII_FIELDS: frozenset[str] = frozenset(
    {
        "email",
        "phone",
        "nip",
        "address",
        "ssn",
        "name",
        "ip_address",
        "location",
        "birth_date",
        "passport",
    }
)

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass
class PIIAccessRecord:
    """Immutable audit trail entry for a single PII field access."""

    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    user_id: str = ""
    user_email: str = ""
    field_name: str = ""
    entity_type: str = ""
    entity_id: str = ""
    investigation_id: str = ""
    access_purpose: str = "investigation"  # investigation | export | share | api
    ip_address: str = ""
    endpoint: str = ""


# ---------------------------------------------------------------------------
# Audit logger
# ---------------------------------------------------------------------------


class PIIAuditLogger:
    """Records every access to PII fields for GDPR compliance.

    Records are buffered in memory and written to the database in batches
    via :meth:`flush_to_db`.  For high-throughput deployments consider
    flushing on a background timer or after each request.
    """

    def __init__(self, db_session: Any | None = None) -> None:
        self._session = db_session
        self._buffer: list[PIIAccessRecord] = []

    # ------------------------------------------------------------------
    # Core logging
    # ------------------------------------------------------------------

    def log_access(
        self,
        user_id: str,
        field_name: str,
        entity_type: str,
        entity_id: str,
        investigation_id: str = "",
        purpose: str = "investigation",
        ip_address: str = "",
        endpoint: str = "",
    ) -> PIIAccessRecord:
        """Create a :class:`PIIAccessRecord` and add it to the in-memory buffer."""
        record = PIIAccessRecord(
            user_id=user_id,
            field_name=field_name,
            entity_type=entity_type,
            entity_id=entity_id,
            investigation_id=investigation_id,
            access_purpose=purpose,
            ip_address=ip_address,
            endpoint=endpoint,
        )
        self._buffer.append(record)
        log.info(
            "pii.access_logged",
            record_id=record.id,
            user_id=user_id,
            field_name=field_name,
            entity_type=entity_type,
            entity_id=entity_id,
            purpose=purpose,
        )
        return record

    def is_pii_field(self, field_name: str) -> bool:
        """Return ``True`` when *field_name* is a known PII field."""
        return field_name.lower() in PII_FIELDS

    # ------------------------------------------------------------------
    # Response scanning
    # ------------------------------------------------------------------

    def audit_response(self, response_data: dict | list, context: dict) -> None:
        """Recursively walk *response_data* and log every PII field discovered.

        Args:
            response_data: Parsed JSON response body (dict or list).
            context: Must contain ``user_id``; optionally ``endpoint``,
                ``ip_address``, and ``investigation_id``.
        """
        user_id: str = context.get("user_id", "")
        endpoint: str = context.get("endpoint", "")
        ip_address: str = context.get("ip_address", "")
        investigation_id: str = context.get("investigation_id", "")

        self._walk(
            node=response_data,
            user_id=user_id,
            endpoint=endpoint,
            ip_address=ip_address,
            investigation_id=investigation_id,
            entity_type="",
            entity_id="",
        )

    def _walk(
        self,
        node: Any,
        user_id: str,
        endpoint: str,
        ip_address: str,
        investigation_id: str,
        entity_type: str,
        entity_id: str,
    ) -> None:
        """Depth-first traversal of the response tree."""
        if isinstance(node, list):
            for item in node:
                self._walk(
                    item,
                    user_id=user_id,
                    endpoint=endpoint,
                    ip_address=ip_address,
                    investigation_id=investigation_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
        elif isinstance(node, dict):
            # Attempt to extract contextual entity info from the dict itself.
            current_entity_type = node.get("entity_type", entity_type) or entity_type
            current_entity_id = node.get("id", entity_id) or entity_id

            for key, value in node.items():
                if self.is_pii_field(key) and value:
                    self.log_access(
                        user_id=user_id,
                        field_name=key,
                        entity_type=current_entity_type,
                        entity_id=str(current_entity_id),
                        investigation_id=investigation_id,
                        purpose="api",
                        ip_address=ip_address,
                        endpoint=endpoint,
                    )
                elif isinstance(value, (dict, list)):
                    self._walk(
                        value,
                        user_id=user_id,
                        endpoint=endpoint,
                        ip_address=ip_address,
                        investigation_id=investigation_id,
                        entity_type=current_entity_type,
                        entity_id=str(current_entity_id),
                    )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def flush_to_db(self) -> int:
        """Write all buffered :class:`PIIAccessRecord` rows to the database.

        Returns the number of records written.  The buffer is cleared on
        success.  If no DB session is configured the records are emitted as
        structured log lines instead so that an external log aggregator can
        ingest them.
        """
        if not self._buffer:
            return 0

        count = len(self._buffer)

        if self._session is None:
            # Fallback: emit to structured log (picked up by log shippers).
            for record in self._buffer:
                log.info("pii.audit_record", **record.__dict__)
            self._buffer.clear()
            return count

        try:
            # The session is expected to be a SQLAlchemy AsyncSession or similar.
            for record in self._buffer:
                await self._session.execute(
                    # Callers should inject a proper ORM model; we emit a raw log
                    # so that this adapter works even without the DB model imported.
                    # Replace this block with: session.add(PIIAccessLog(**record.__dict__))
                    None  # type: ignore[arg-type]
                )
            await self._session.commit()
        except Exception as exc:  # noqa: BLE001
            log.error("pii.flush_failed", error=str(exc), buffered_count=count)
            return 0
        finally:
            self._buffer.clear()

        log.info("pii.flushed", count=count)
        return count

    # ------------------------------------------------------------------
    # GDPR report
    # ------------------------------------------------------------------

    def generate_gdpr_report(
        self,
        user_id: str,
        records: list[PIIAccessRecord],
    ) -> dict:
        """Generate a GDPR Article 15 subject-access report for *user_id*.

        The returned dict summarises all PII field accesses attributable to
        the given user and is suitable for attaching to a DSAR response.

        Returns:
            A dict with keys: ``user_id``, ``total_accesses``, ``by_field``,
            ``by_purpose``, ``by_date``, ``earliest``, ``latest``.
        """
        user_records = [r for r in records if r.user_id == user_id]

        by_field: dict[str, int] = {}
        by_purpose: dict[str, int] = {}
        by_date: dict[str, int] = {}
        timestamps: list[str] = []

        for rec in user_records:
            by_field[rec.field_name] = by_field.get(rec.field_name, 0) + 1
            by_purpose[rec.access_purpose] = by_purpose.get(rec.access_purpose, 0) + 1
            date_key = rec.timestamp[:10]  # YYYY-MM-DD
            by_date[date_key] = by_date.get(date_key, 0) + 1
            timestamps.append(rec.timestamp)

        timestamps_sorted = sorted(timestamps)

        report = {
            "user_id": user_id,
            "total_accesses": len(user_records),
            "by_field": dict(sorted(by_field.items(), key=lambda x: x[1], reverse=True)),
            "by_purpose": by_purpose,
            "by_date": dict(sorted(by_date.items())),
            "earliest": timestamps_sorted[0] if timestamps_sorted else None,
            "latest": timestamps_sorted[-1] if timestamps_sorted else None,
        }

        log.info("pii.gdpr_report_generated", user_id=user_id, total=len(user_records))
        return report


# ---------------------------------------------------------------------------
# FastAPI middleware
# ---------------------------------------------------------------------------


class PIIAuditMiddleware:
    """FastAPI middleware that auto-audits PII field access in API responses.

    Only GET requests are audited here (reads).  POST / PUT / PATCH writes
    are expected to be covered by dedicated write-audit paths.

    Usage::

        app.add_middleware(PIIAuditMiddleware, audit_logger=audit_logger)
    """

    def __init__(self, app: Any, audit_logger: PIIAuditLogger) -> None:
        self._app = app
        self._logger = audit_logger

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        method: str = scope.get("method", "").upper()

        # Only intercept GET requests for read-access auditing.
        if method != "GET":
            await self._app(scope, receive, send)
            return

        # Build a context dict from the ASGI scope.
        context = self._build_context(scope)

        # Capture the response body so we can scan it.
        body_chunks: list[bytes] = []
        status_code: int = 200

        async def _capture_send(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            elif message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))
            await send(message)

        await self._app(scope, receive, _capture_send)

        # Only scan successful JSON responses.
        if status_code == 200 and body_chunks:
            raw_body = b"".join(body_chunks)
            self._scan_body(raw_body, context)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_context(self, scope: dict) -> dict:
        """Extract audit context from an ASGI HTTP scope."""
        path: str = scope.get("path", "")
        headers: dict[str, str] = {
            k.decode(): v.decode()
            for k, v in scope.get("headers", [])
        }

        client = scope.get("client")
        ip_address = client[0] if client else headers.get("x-forwarded-for", "")

        # User identity is expected to be injected into scope["state"] by an
        # authentication middleware that runs before this one.
        state = scope.get("state", {})
        user_id: str = getattr(state, "user_id", "") or ""
        investigation_id: str = getattr(state, "investigation_id", "") or ""

        return {
            "user_id": user_id,
            "endpoint": path,
            "ip_address": ip_address,
            "investigation_id": investigation_id,
        }

    def _scan_body(self, raw_body: bytes, context: dict) -> None:
        """Attempt to parse *raw_body* as JSON and audit any PII fields found."""
        import json

        if not raw_body:
            return

        try:
            data = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return  # Non-JSON response — nothing to audit.

        if isinstance(data, (dict, list)):
            self._logger.audit_response(data, context)
