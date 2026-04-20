"""Document metadata extractor supporting PDF, DOCX, XLSX, PPTX formats."""

from __future__ import annotations

import hashlib
import io
import mimetypes
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ExtractedDocMetadata:
    filename: str
    file_hash: str
    file_size: int
    mime_type: str
    doc_format: str | None = None
    author: str | None = None
    creator_tool: str | None = None
    company: str | None = None
    last_modified_by: str | None = None
    created_at_doc: datetime | None = None
    modified_at_doc: datetime | None = None
    revision_count: int | None = None
    has_macros: bool = False
    has_hidden_content: bool = False
    has_tracked_changes: bool = False
    gps_lat: float | None = None
    gps_lon: float | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    embedded_files: list[str] = field(default_factory=list)


class DocumentMetadataExtractor:
    """Extract metadata from office documents and PDFs."""

    _MAGIC_MAP: list[tuple[bytes, str, str]] = [
        (b"%PDF", "application/pdf", "pdf"),
        (b"PK\x03\x04", "application/zip", "zip"),  # OOXML formats are ZIP
    ]

    def extract(self, file_bytes: bytes, filename: str) -> ExtractedDocMetadata:
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)
        mime_type, doc_format = self._detect_format(file_bytes, filename)

        base = ExtractedDocMetadata(
            filename=filename,
            file_hash=file_hash,
            file_size=file_size,
            mime_type=mime_type,
            doc_format=doc_format,
        )

        if doc_format == "pdf":
            return self._extract_pdf(file_bytes, base)
        if doc_format == "docx":
            return self._extract_docx(file_bytes, base)
        if doc_format == "xlsx":
            return self._extract_xlsx(file_bytes, base)
        if doc_format == "pptx":
            return self._extract_pptx(file_bytes, base)
        return base

    # ------------------------------------------------------------------
    # Format detection
    # ------------------------------------------------------------------

    def _detect_format(self, data: bytes, filename: str) -> tuple[str, str | None]:
        if data[:4] == b"%PDF":
            return "application/pdf", "pdf"

        if data[:4] == b"PK\x03\x04":
            lower = filename.lower()
            if lower.endswith(".docx"):
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
            if lower.endswith(".xlsx"):
                return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
            if lower.endswith(".pptx"):
                return "application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx"
            if lower.endswith(".odt"):
                return "application/vnd.oasis.opendocument.text", "odt"
            return "application/zip", "zip"

        # OLE2 compound doc (legacy .doc/.xls/.ppt)
        if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            lower = filename.lower()
            if lower.endswith(".doc"):
                return "application/msword", "doc"
            if lower.endswith(".xls"):
                return "application/vnd.ms-excel", "xls"
            if lower.endswith(".ppt"):
                return "application/vnd.ms-powerpoint", "ppt"
            return "application/octet-stream", "ole"

        guessed, _ = mimetypes.guess_type(filename)
        return guessed or "application/octet-stream", None

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------

    def _extract_pdf(self, data: bytes, base: ExtractedDocMetadata) -> ExtractedDocMetadata:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            meta = reader.metadata or {}

            def _get(key: str) -> str | None:
                v = meta.get(key)
                return str(v).strip() or None if v else None

            base.author = _get("/Author")
            base.creator_tool = _get("/Creator") or _get("/Producer")
            base.company = _get("/Subject")
            base.raw_metadata = {k.lstrip("/"): str(v) for k, v in meta.items()}

            for key in ("/CreationDate", "/ModDate"):
                raw = meta.get(key)
                if raw:
                    dt = self._parse_pdf_date(str(raw))
                    if key == "/CreationDate":
                        base.created_at_doc = dt
                    else:
                        base.modified_at_doc = dt

            base.has_hidden_content = any(
                "/JavaScript" in str(page.get("/AA", "")) for page in reader.pages
            )

        except Exception:
            pass
        return base

    @staticmethod
    def _parse_pdf_date(raw: str) -> datetime | None:
        """Parse PDF date format D:YYYYMMDDHHmmSS."""
        raw = raw.strip()
        if raw.startswith("D:"):
            raw = raw[2:]
        for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d"):
            try:
                return datetime.strptime(raw[:len(fmt.replace("%", "XX").replace("X", ""))], fmt).replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue
        return None

    # ------------------------------------------------------------------
    # DOCX
    # ------------------------------------------------------------------

    def _extract_docx(self, data: bytes, base: ExtractedDocMetadata) -> ExtractedDocMetadata:
        try:
            from docx import Document
            from docx.opc.constants import RELATIONSHIP_TYPE as RT

            doc = Document(io.BytesIO(data))
            props = doc.core_properties

            base.author = props.author or None
            base.last_modified_by = props.last_modified_by or None
            base.company = props.category or None
            base.created_at_doc = props.created
            base.modified_at_doc = props.modified
            base.revision_count = props.revision
            base.has_tracked_changes = bool(
                doc.element.body.xml.find("w:ins") != -1 or doc.element.body.xml.find("w:del") != -1
            )

            base.raw_metadata = {
                "author": base.author,
                "last_modified_by": base.last_modified_by,
                "created": str(base.created_at_doc),
                "modified": str(base.modified_at_doc),
                "revision": base.revision_count,
                "title": props.title,
                "subject": props.subject,
                "keywords": props.keywords,
                "description": props.description,
                "content_status": props.content_status,
                "identifier": props.identifier,
                "language": props.language,
                "version": props.version,
            }

            # Check for embedded files/macros
            try:
                from zipfile import ZipFile
                with ZipFile(io.BytesIO(data)) as z:
                    names = z.namelist()
                    base.has_macros = any("vba" in n.lower() or "macro" in n.lower() for n in names)
                    base.embedded_files = [n for n in names if not n.endswith("/")]
            except Exception:
                pass

        except Exception:
            pass
        return base

    # ------------------------------------------------------------------
    # XLSX
    # ------------------------------------------------------------------

    def _extract_xlsx(self, data: bytes, base: ExtractedDocMetadata) -> ExtractedDocMetadata:
        try:
            import openpyxl

            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            props = wb.properties

            base.author = props.creator or None
            base.last_modified_by = props.lastModifiedBy or None
            base.created_at_doc = props.created
            base.modified_at_doc = props.modified
            base.revision_count = int(props.revision) if props.revision else None

            base.raw_metadata = {
                "creator": base.author,
                "last_modified_by": base.last_modified_by,
                "created": str(base.created_at_doc),
                "modified": str(base.modified_at_doc),
                "revision": base.revision_count,
                "title": props.title,
                "subject": props.subject,
                "keywords": props.keywords,
                "description": props.description,
                "category": props.category,
                "company": props.company,
                "content_status": props.contentStatus,
            }
            base.company = props.company or None

            try:
                from zipfile import ZipFile
                with ZipFile(io.BytesIO(data)) as z:
                    names = z.namelist()
                    base.has_macros = any("vba" in n.lower() for n in names)
                    base.embedded_files = [n for n in names if not n.endswith("/")]
            except Exception:
                pass

        except Exception:
            pass
        return base

    # ------------------------------------------------------------------
    # PPTX
    # ------------------------------------------------------------------

    def _extract_pptx(self, data: bytes, base: ExtractedDocMetadata) -> ExtractedDocMetadata:
        try:
            from pptx import Presentation

            prs = Presentation(io.BytesIO(data))
            props = prs.core_properties

            base.author = props.author or None
            base.last_modified_by = props.last_modified_by or None
            base.created_at_doc = props.created
            base.modified_at_doc = props.modified
            base.revision_count = props.revision

            base.raw_metadata = {
                "author": base.author,
                "last_modified_by": base.last_modified_by,
                "created": str(base.created_at_doc),
                "modified": str(base.modified_at_doc),
                "revision": base.revision_count,
                "title": props.title,
                "subject": props.subject,
                "keywords": props.keywords,
                "description": props.description,
            }

            try:
                from zipfile import ZipFile
                with ZipFile(io.BytesIO(data)) as z:
                    names = z.namelist()
                    base.has_macros = any("vba" in n.lower() for n in names)
                    base.embedded_files = [n for n in names if not n.endswith("/")]
            except Exception:
                pass

        except Exception:
            pass
        return base
