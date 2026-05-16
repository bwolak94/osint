"""Evidence Preservation — screenshot capture and HTML archival to MinIO + Wayback Machine."""

from __future__ import annotations

import hashlib
import io
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter(prefix="/preservation", tags=["evidence"])


class PreserveRequest(BaseModel):
    url: str
    investigation_id: str | None = None
    label: str | None = None
    mode: str = "archive"  # "archive" | "screenshot" | "both"
    full_page: bool = True


class PreserveResponse(BaseModel):
    evidence_id: str
    url: str
    label: str | None
    mode: str
    content_hash: str | None
    storage_path: str | None
    wayback_url: str | None
    captured_at: str
    investigation_id: str | None
    status: str
    error: str | None = None


async def _store_in_minio(
    data: bytes,
    object_name: str,
    content_type: str,
    metadata: dict[str, str],
) -> str | None:
    """Store bytes in MinIO and return the object path."""
    try:
        from src.config import get_app_settings
        settings = get_app_settings()
        from minio import Minio

        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        client.put_object(
            bucket_name=settings.minio_bucket,
            object_name=object_name,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
            metadata=metadata,
        )
        return f"minio://{settings.minio_bucket}/{object_name}"
    except Exception as exc:
        log.debug("MinIO storage failed", error=str(exc))
        return None


@router.post("", response_model=PreserveResponse)
async def preserve_url(
    request: PreserveRequest,
    current_user: Any = Depends(get_current_user),
) -> PreserveResponse:
    """Preserve a URL as screenshot and/or HTML archive stored in MinIO."""
    import httpx

    evidence_id = str(uuid.uuid4())
    captured_at = datetime.now(timezone.utc).isoformat()
    content_hash: str | None = None
    storage_path: str | None = None
    wayback_url: str | None = None
    error: str | None = None

    base_meta = {
        "evidence-id": evidence_id,
        "source-url": request.url[:200],
        "investigation-id": request.investigation_id or "",
        "captured-at": captured_at,
    }

    # --- Screenshot mode ---
    if request.mode in ("screenshot", "both"):
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
                )
                page = await browser.new_page(
                    viewport={"width": 1280, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                )
                await page.goto(request.url, wait_until="networkidle", timeout=20000)
                png_bytes = await page.screenshot(full_page=request.full_page, type="png")
                await browser.close()

            content_hash = hashlib.sha256(png_bytes).hexdigest()
            obj = f"preservation/{evidence_id}/screenshot.png"
            storage_path = await _store_in_minio(png_bytes, obj, "image/png", base_meta)
            log.info("Screenshot captured", evidence_id=evidence_id, size=len(png_bytes))
        except Exception as exc:
            error = f"Screenshot error: {exc}"
            log.debug("Screenshot failed", evidence_id=evidence_id, error=str(exc))

    # --- Archive (HTML) mode ---
    if request.mode in ("archive", "both"):
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            try:
                resp = await client.get(
                    request.url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; EvidenceArchiver/1.0)"},
                )
                html_bytes = resp.content
                if not content_hash:
                    content_hash = hashlib.sha256(html_bytes).hexdigest()
                obj = f"preservation/{evidence_id}/page.html"
                path = await _store_in_minio(
                    html_bytes, obj, "text/html",
                    {**base_meta, "content-hash": content_hash}
                )
                if path and not storage_path:
                    storage_path = path
                log.info("HTML archived", evidence_id=evidence_id, size=len(html_bytes))
            except Exception as exc:
                err_msg = f"Archive error: {exc}"
                error = f"{error} | {err_msg}" if error else err_msg

            # Submit to Wayback Machine (best-effort, non-blocking)
            try:
                wb = await client.get(
                    f"https://web.archive.org/save/{request.url}",
                    timeout=10,
                )
                if wb.status_code in (200, 302):
                    wayback_url = f"https://web.archive.org/web/*/{request.url}"
            except Exception:
                pass

    final_status = "ok" if (content_hash and not error) else ("partial" if content_hash else "failed")

    return PreserveResponse(
        evidence_id=evidence_id,
        url=request.url,
        label=request.label,
        mode=request.mode,
        content_hash=content_hash,
        storage_path=storage_path,
        wayback_url=wayback_url,
        captured_at=captured_at,
        investigation_id=request.investigation_id,
        status=final_status,
        error=error,
    )


@router.get("/list")
async def list_preserved(
    investigation_id: str | None = None,
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """List preserved evidence items from MinIO."""
    try:
        from src.config import get_app_settings
        settings = get_app_settings()
        from minio import Minio

        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        prefix = "preservation/"
        objects = list(client.list_objects(settings.minio_bucket, prefix=prefix, recursive=False))
        items = [
            {
                "evidence_id": obj.object_name.split("/")[1] if "/" in (obj.object_name or "") else obj.object_name,
                "object_prefix": obj.object_name,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
            }
            for obj in objects[:100]
        ]
    except Exception as exc:
        log.debug("MinIO list failed", error=str(exc))
        items = []

    return {"items": items, "total": len(items)}
