"""Text chunker — splits text into overlapping word-based chunks.

Configuration via environment variables:
  CHUNK_SIZE    — words per chunk (default 512)
  CHUNK_OVERLAP — words of overlap between consecutive chunks (default 64)

Phase 3 upgrade path: swap word splitting for tiktoken token counting.
"""

from __future__ import annotations

import os

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "64"))


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict[str, object]]:
    """Split text into overlapping word-based chunks.

    Args:
        text:       Input text to split.
        chunk_size: Maximum words per chunk.
        overlap:    Number of words shared between consecutive chunks.

    Returns:
        List of dicts, each with keys:
          ``text``        — the chunk text string
          ``chunk_index`` — 0-based position in the sequence

    Notes:
        - Empty or whitespace-only input returns an empty list.
        - If the text is shorter than chunk_size, a single chunk is returned.
        - overlap must be smaller than chunk_size to make forward progress.
    """
    if not text or not text.strip():
        return []

    # Guard against degenerate overlap configuration
    effective_overlap = min(overlap, max(chunk_size - 1, 0))
    step = chunk_size - effective_overlap
    if step <= 0:
        step = 1

    words = text.split()
    if not words:
        return []

    chunks: list[dict[str, object]] = []
    chunk_index = 0
    i = 0

    while i < len(words):
        chunk_words = words[i : i + chunk_size]
        chunks.append(
            {
                "text": " ".join(chunk_words),
                "chunk_index": chunk_index,
            }
        )
        chunk_index += 1
        i += step

    return chunks
