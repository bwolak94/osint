"""PDF parser — extracts plain text from PDF bytes using pypdf.

pypdf is an optional dependency. Import is guarded to produce a clear error
rather than an ImportError at module load time.
"""

from __future__ import annotations

import io


async def parse_pdf(content: bytes) -> str:
    """Extract text from PDF bytes using pypdf.

    Args:
        content: Raw PDF file bytes.

    Returns:
        Extracted plain text with pages separated by newlines.

    Raises:
        ImportError: If pypdf is not installed.
    """
    try:
        import pypdf  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "pypdf is required for PDF parsing: pip install pypdf"
        ) from exc

    reader = pypdf.PdfReader(io.BytesIO(content))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())

    return "\n\n".join(pages)
