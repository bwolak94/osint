"""Metagoofil scanner — searches for public documents and extracts metadata."""

import io
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_WINDOWS_USER_RE = re.compile(r"[A-Za-z0-9._]+\\[A-Za-z0-9._]+")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_DOC_URL_RE = re.compile(
    r'href=["\']?(https?://[^\s"\'<>]+\.(?:pdf|doc|docx|xls|xlsx|ppt|pptx))["\']?',
    re.IGNORECASE,
)

_MAX_DOCS = 10
_MAX_DOWNLOAD_BYTES = 1024 * 1024  # 1 MB


class MetagoofilScanner(BaseOsintScanner):
    scanner_name = "metagoofil"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().lower()
        doc_urls = await self._search_document_urls(domain)

        documents_found: list[dict[str, Any]] = []
        all_usernames: list[str] = []
        all_emails: list[str] = []
        all_software: list[str] = []
        all_paths: list[str] = []
        metadata_extracted: list[dict[str, Any]] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for url in doc_urls[:_MAX_DOCS]:
                ext = self._file_ext(url)
                content, size = await self._download_partial(client, url)
                if not content:
                    continue

                doc_meta: dict[str, Any] = {"url": url, "type": ext, "size": size}

                if ext == "pdf":
                    meta = self._extract_pdf_metadata(content, url)
                elif ext in {"doc", "docx"}:
                    meta = self._extract_docx_metadata(content, url)
                else:
                    meta = {"usernames": [], "emails": [], "software": [], "paths": []}

                doc_meta.update(meta)
                documents_found.append(doc_meta)
                metadata_extracted.append({"url": url, **meta})

                all_usernames.extend(meta.get("usernames", []))
                all_emails.extend(meta.get("emails", []))
                all_software.extend(meta.get("software", []))
                all_paths.extend(meta.get("paths", []))

                identifiers.append(f"url:{url}")

        unique_usernames = list(dict.fromkeys(all_usernames))
        unique_emails = list(dict.fromkeys(all_emails))
        unique_software = list(dict.fromkeys(all_software))
        unique_paths = list(dict.fromkeys(all_paths))

        for email in unique_emails:
            identifiers.append(f"email:{email}")
        for username in unique_usernames:
            identifiers.append(f"person:{username}")

        return {
            "domain": domain,
            "documents_found": documents_found,
            "metadata_extracted": metadata_extracted,
            "usernames": unique_usernames,
            "emails": unique_emails,
            "software_versions": unique_software,
            "internal_paths": unique_paths,
            "extracted_identifiers": list(dict.fromkeys(identifiers)),
        }

    async def _search_document_urls(self, domain: str) -> list[str]:
        query = f"site:{domain} filetype:pdf OR filetype:doc OR filetype:xls OR filetype:ppt"
        url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"}
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return []
                matches = _DOC_URL_RE.findall(resp.text)
                seen: dict[str, None] = {}
                for m in matches:
                    parsed = urlparse(m)
                    if parsed.netloc and domain in parsed.netloc:
                        seen[m] = None
                return list(seen.keys())
        except Exception as exc:
            log.warning("Metagoofil DuckDuckGo search failed", domain=domain, error=str(exc))
            return []

    async def _download_partial(self, client: httpx.AsyncClient, url: str) -> tuple[bytes, int]:
        try:
            async with client.stream("GET", url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                if resp.status_code != 200:
                    return b"", 0
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= _MAX_DOWNLOAD_BYTES:
                        break
                return b"".join(chunks), total
        except Exception as exc:
            log.warning("Metagoofil download failed", url=url, error=str(exc))
            return b"", 0

    def _file_ext(self, url: str) -> str:
        path = urlparse(url).path.lower()
        for ext in ("pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt"):
            if path.endswith(f".{ext}"):
                return ext
        return "unknown"

    def _extract_pdf_metadata(self, content: bytes, url: str) -> dict[str, Any]:
        usernames: list[str] = []
        emails: list[str] = []
        software: list[str] = []
        paths: list[str] = []
        raw_meta: dict[str, str] = {}

        try:
            import pypdf  # type: ignore[import-untyped]

            reader = pypdf.PdfReader(io.BytesIO(content))
            meta_obj = reader.metadata or {}
            fields = {"/Author", "/Creator", "/Producer", "/Title", "/Subject"}
            for field in fields:
                value = meta_obj.get(field)
                if value:
                    raw_meta[field] = str(value)
                    win_users = _WINDOWS_USER_RE.findall(str(value))
                    usernames.extend(win_users)
                    found_emails = _EMAIL_RE.findall(str(value))
                    emails.extend(found_emails)
                    if field in {"/Creator", "/Producer"}:
                        software.append(str(value))

            # scan page text for emails/usernames (first page only)
            if reader.pages:
                try:
                    text = reader.pages[0].extract_text() or ""
                    emails.extend(_EMAIL_RE.findall(text))
                    usernames.extend(_WINDOWS_USER_RE.findall(text))
                    path_re = re.compile(r"(?:[A-Za-z]:\\[^\s\"'<>]+|/(?:home|Users|var|opt)/[^\s\"'<>]+)")
                    paths.extend(path_re.findall(text))
                except Exception:
                    pass
        except Exception as exc:
            log.debug("PDF parse error", url=url, error=str(exc))

        return {
            "raw_metadata": raw_meta,
            "usernames": list(dict.fromkeys(usernames)),
            "emails": list(dict.fromkeys(emails)),
            "software": list(dict.fromkeys(software)),
            "paths": list(dict.fromkeys(paths)),
        }

    def _extract_docx_metadata(self, content: bytes, url: str) -> dict[str, Any]:
        usernames: list[str] = []
        emails: list[str] = []
        software: list[str] = []
        paths: list[str] = []
        raw_meta: dict[str, str] = {}

        try:
            import docx  # type: ignore[import-untyped]

            doc = docx.Document(io.BytesIO(content))
            core = doc.core_properties
            for attr in ("author", "last_modified_by", "creator"):
                value = getattr(core, attr, None)
                if value:
                    raw_meta[attr] = str(value)
                    usernames.append(str(value))
                    emails.extend(_EMAIL_RE.findall(str(value)))
        except ImportError:
            log.debug("python-docx not installed, skipping DOCX extraction", url=url)
        except Exception as exc:
            log.debug("DOCX parse error", url=url, error=str(exc))

        return {
            "raw_metadata": raw_meta,
            "usernames": list(dict.fromkeys(usernames)),
            "emails": list(dict.fromkeys(emails)),
            "software": list(dict.fromkeys(software)),
            "paths": list(dict.fromkeys(paths)),
        }
