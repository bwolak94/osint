"""Traffic Light Protocol (TLP) enforcement service for OSINT data sharing."""

from enum import StrEnum

import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# TLP Level definition
# ---------------------------------------------------------------------------


class TLPLevel(StrEnum):
    WHITE = "white"  # Unrestricted sharing
    GREEN = "green"  # Community sharing, not public
    AMBER = "amber"  # Limited to organization
    RED = "red"  # Not for disclosure, source only


# Ordered from least to most restrictive — index position encodes severity.
TLP_HIERARCHY: list[TLPLevel] = [
    TLPLevel.WHITE,
    TLPLevel.GREEN,
    TLPLevel.AMBER,
    TLPLevel.RED,
]

_TLP_INDEX: dict[TLPLevel, int] = {level: idx for idx, level in enumerate(TLP_HIERARCHY)}

_TLP_COLORS: dict[TLPLevel, str] = {
    TLPLevel.WHITE: "#ffffff",
    TLPLevel.GREEN: "#33ff00",
    TLPLevel.AMBER: "#ffc000",
    TLPLevel.RED: "#ff0033",
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TLPService:
    """Enforce Traffic Light Protocol rules across sharing, export, and display."""

    # ------------------------------------------------------------------
    # Core permission checks
    # ------------------------------------------------------------------

    def can_share(self, entity_tlp: TLPLevel, requester_clearance: TLPLevel) -> bool:
        """Return True when the requester's clearance is at least as high as the entity TLP.

        A requester with RED clearance can access any level; WHITE clearance can
        only access WHITE-tagged entities.
        """
        allowed = _TLP_INDEX[requester_clearance] >= _TLP_INDEX[entity_tlp]
        log.debug(
            "tlp.can_share",
            entity_tlp=entity_tlp,
            requester_clearance=requester_clearance,
            allowed=allowed,
        )
        return allowed

    def effective_tlp(self, tlp_list: list[TLPLevel]) -> TLPLevel:
        """Return the most restrictive TLP level from *tlp_list*.

        If the list is empty, defaults to TLPLevel.RED (safest assumption).
        """
        if not tlp_list:
            log.warning("tlp.effective_tlp called with empty list — defaulting to RED")
            return TLPLevel.RED

        return max(tlp_list, key=lambda lvl: _TLP_INDEX[lvl])

    # ------------------------------------------------------------------
    # Export / filtering helpers
    # ------------------------------------------------------------------

    def filter_for_export(
        self,
        entities: list[dict],
        max_tlp: TLPLevel,
    ) -> list[dict]:
        """Return only those entities whose TLP level does not exceed *max_tlp*.

        Entities without a ``tlp_level`` key are treated as TLPLevel.WHITE
        (most permissive) to avoid accidentally blocking unlabelled data.
        """
        max_index = _TLP_INDEX[max_tlp]
        result: list[dict] = []

        for entity in entities:
            raw = entity.get("tlp_level", TLPLevel.WHITE)
            try:
                level = TLPLevel(raw) if not isinstance(raw, TLPLevel) else raw
            except ValueError:
                log.warning("tlp.filter_for_export unknown level", raw=raw)
                level = TLPLevel.RED  # treat unknown as most restrictive

            if _TLP_INDEX[level] <= max_index:
                result.append(entity)
            else:
                log.debug(
                    "tlp.filter_for_export excluded entity",
                    entity_id=entity.get("id"),
                    entity_tlp=level,
                    max_tlp=max_tlp,
                )

        return result

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def tlp_color(self, level: TLPLevel) -> str:
        """Return the hex colour code for a TLP level's UI badge."""
        color = _TLP_COLORS.get(level)
        if color is None:
            raise ValueError(f"Unknown TLP level: {level!r}")
        return color

    # ------------------------------------------------------------------
    # Redaction
    # ------------------------------------------------------------------

    def redact_for_tlp(self, text: str, max_tlp: TLPLevel, entity_tlp: TLPLevel) -> str:
        """Redact *text* when *entity_tlp* exceeds the allowed *max_tlp*.

        The replacement marker includes the actual classification so that
        recipients understand why the content was withheld.
        """
        if _TLP_INDEX[entity_tlp] > _TLP_INDEX[max_tlp]:
            redacted = f"[REDACTED - TLP:{entity_tlp.upper()}]"
            log.debug(
                "tlp.redact_for_tlp applied",
                entity_tlp=entity_tlp,
                max_tlp=max_tlp,
            )
            return redacted
        return text

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_level(self, level: str) -> TLPLevel:
        """Parse a raw string into a :class:`TLPLevel`.

        Raises:
            ValueError: When *level* is not a recognised TLP designation.
        """
        normalised = level.strip().lower()
        try:
            parsed = TLPLevel(normalised)
        except ValueError:
            valid = ", ".join(TLP_HIERARCHY)
            raise ValueError(
                f"Invalid TLP level {level!r}. Must be one of: {valid}"
            ) from None

        log.debug("tlp.validate_level", raw=level, parsed=parsed)
        return parsed
