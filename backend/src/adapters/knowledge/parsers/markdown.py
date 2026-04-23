"""Markdown parser — strips markdown syntax while preserving text structure.

Phase 2: regex-based cleaning without external dependencies.
Phase 3: upgrade to python-markdown or mistune for richer extraction.
"""

from __future__ import annotations

import re


def parse_markdown(content: str) -> str:
    """Strip markdown syntax and return clean prose text.

    Transformations applied (in order):
      1. Remove fenced code blocks (``` … ```)
      2. Remove inline code (`…`)
      3. Convert ATX headings (# …) to plain text
      4. Remove bold/italic markers (* ** _ __)
      5. Convert links [text](url) → text
      6. Convert images ![alt](url) → alt
      7. Remove blockquote markers (> )
      8. Remove horizontal rules (---/***/***)
      9. Remove list markers (- * + and ordered 1.)
     10. Collapse multiple blank lines

    Args:
        content: Raw markdown string.

    Returns:
        Clean plain text suitable for chunking.
    """
    text = content

    # 1. Remove fenced code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"~~~[\s\S]*?~~~", "", text)

    # 2. Remove inline code
    text = re.sub(r"`[^`\n]+`", "", text)

    # 3. ATX headings → plain text (strip leading #s)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # 4. Bold and italic markers
    text = re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_\n]+)_{1,3}", r"\1", text)

    # 5. Links [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # 6. Images ![alt](url) → alt
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)

    # 7. Blockquotes
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)

    # 8. Horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # 9. Unordered and ordered list markers
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.MULTILINE)

    # 10. Collapse multiple blank lines to two
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
