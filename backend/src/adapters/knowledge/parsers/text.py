"""Plain text parser — normalises text/bytes for chunking."""

from __future__ import annotations

import unicodedata


def parse_text(content: str | bytes) -> str:
    """Decode and clean plain text for downstream chunking.

    - Decodes bytes to UTF-8 (with replacement for invalid sequences)
    - Normalises Unicode to NFC form
    - Strips leading/trailing whitespace
    - Collapses excessive blank lines to two newlines

    Args:
        content: Raw text as str or bytes.

    Returns:
        Normalised plain text string.
    """
    import re  # noqa: PLC0415 — lightweight, no module-level cost concern

    if isinstance(content, bytes):
        text = content.decode("utf-8", errors="replace")
    else:
        text = content

    # Normalise Unicode
    text = unicodedata.normalize("NFC", text)

    # Collapse carriage returns
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse more than two consecutive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
