"""Unit tests for image checker API endpoints.

The router lives at src/api/v1/image_checker/router.py and is tested here by
calling its handler functions directly with mocked dependencies, matching the
convention used throughout the rest of this test suite.

Expected router contract
------------------------
POST   /api/v1/image-checker/
  - Accepts multipart/form-data with a ``file`` field
  - Validates MIME type; rejects non-image content with HTTP 400
  - Validates file size (max 20 MB); rejects oversized uploads with HTTP 413
  - Calls ImageMetadataExtractor.extract(file_bytes, filename)
  - Persists an ImageCheckModel row via the DB session
  - Returns 201 with ImageCheckResponse

GET    /api/v1/image-checker/
  - Returns paginated list of the current user's checks
  - Supports ``page`` and ``page_size`` query params (defaults 1/20)
  - Returns PaginatedImageCheckResponse

GET    /api/v1/image-checker/{check_id}
  - Returns a single check owned by the current user
  - Returns 404 for unknown id OR a check owned by a different user (no enumeration)

DELETE /api/v1/image-checker/{check_id}
  - Deletes the record; returns 204
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from src.adapters.image_metadata.extractor import ExtractedMetadata, GPSData
from src.core.domain.entities.types import SubscriptionTier, UserRole
from src.core.domain.entities.user import User
from src.core.domain.value_objects.email import Email


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id: uuid.UUID | None = None) -> User:
    """Build a minimal, valid User entity for use in dependency overrides."""
    return User(
        id=user_id or uuid.uuid4(),
        email=Email("analyst@example.com"),
        hashed_password="$2b$12$hashed",
        role=UserRole.ANALYST,
        subscription_tier=SubscriptionTier.PRO,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def _make_jpeg_bytes(width: int = 80, height: int = 80) -> bytes:
    """Return raw JPEG bytes for a small solid-colour image."""
    img = Image.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_png_bytes(width: int = 50, height: int = 50) -> bytes:
    img = Image.new("RGBA", (width, height), color=(0, 128, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _sample_extracted_metadata(
    filename: str = "test.jpg",
    with_gps: bool = False,
) -> ExtractedMetadata:
    """Return a realistic ExtractedMetadata fixture."""
    gps = (
        GPSData(latitude=51.5074, longitude=-0.1278, altitude=20.0)
        if with_gps
        else None
    )
    return ExtractedMetadata(
        filename=filename,
        file_hash="a" * 64,
        file_size=12_345,
        mime_type="image/jpeg",
        width=80,
        height=80,
        format="JPEG",
        camera_make="Canon",
        camera_model="EOS 90D",
        taken_at=datetime(2024, 6, 15, 10, 30, 0),
        gps=gps,
        all_tags={"Make": "Canon", "Model": "EOS 90D"},
    )


def _mock_db_session() -> MagicMock:
    """Return an async-compatible SQLAlchemy session mock."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    return session


def _image_check_model_fixture(
    owner_id: uuid.UUID,
    check_id: uuid.UUID | None = None,
) -> MagicMock:
    """Return a mock ORM row that looks like ImageCheckModel."""
    row = MagicMock()
    row.id = check_id or uuid.uuid4()
    row.owner_id = owner_id
    row.filename = "test.jpg"
    row.file_hash = "a" * 64
    row.file_size = 12_345
    row.mime_type = "image/jpeg"
    row.metadata = {"Make": "Canon"}
    row.gps_data = None
    row.camera_make = "Canon"
    row.camera_model = "EOS 90D"
    row.taken_at = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    row.created_at = datetime.now(timezone.utc)
    return row


# ---------------------------------------------------------------------------
# POST /api/v1/image-checker/  — upload and extract
# ---------------------------------------------------------------------------


class TestUploadImageCheck:
    """Tests for the upload endpoint."""

    async def test_upload_valid_jpeg_returns_201(self) -> None:
        """Uploading a valid JPEG should persist a record and return 201."""
        from src.api.v1.image_checker.router import upload_image_check

        current_user = _make_user()
        db = _mock_db_session()
        file_bytes = _make_jpeg_bytes()
        metadata = _sample_extracted_metadata("photo.jpg")

        mock_upload_file = MagicMock()
        mock_upload_file.filename = "photo.jpg"
        mock_upload_file.content_type = "image/jpeg"
        mock_upload_file.read = AsyncMock(return_value=file_bytes)

        with patch(
            "src.api.v1.image_checker.router.ImageMetadataExtractor"
        ) as MockExtractor:
            MockExtractor.return_value.extract.return_value = metadata
            result = await upload_image_check(
                file=mock_upload_file,
                current_user=current_user,
                db=db,
            )

        assert result.filename == "photo.jpg"
        assert result.file_hash == "a" * 64
        assert result.file_size == 12_345
        assert result.mime_type == "image/jpeg"
        assert result.camera_make == "Canon"
        assert result.camera_model == "EOS 90D"
        # DB row must have been added
        db.add.assert_called_once()

    async def test_upload_valid_png_returns_201(self) -> None:
        """PNG upload should be accepted and processed."""
        from src.api.v1.image_checker.router import upload_image_check

        current_user = _make_user()
        db = _mock_db_session()
        file_bytes = _make_png_bytes()
        metadata = ExtractedMetadata(
            filename="image.png",
            file_hash="b" * 64,
            file_size=len(file_bytes),
            mime_type="image/png",
            width=50,
            height=50,
            format="PNG",
        )

        mock_upload_file = MagicMock()
        mock_upload_file.filename = "image.png"
        mock_upload_file.content_type = "image/png"
        mock_upload_file.read = AsyncMock(return_value=file_bytes)

        with patch("src.api.v1.image_checker.router.ImageMetadataExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = metadata
            result = await upload_image_check(
                file=mock_upload_file,
                current_user=current_user,
                db=db,
            )

        assert result.mime_type == "image/png"

    async def test_upload_invalid_file_type_returns_400(self) -> None:
        """Non-image content type must be rejected with HTTP 400."""
        from fastapi import HTTPException

        from src.api.v1.image_checker.router import upload_image_check

        current_user = _make_user()
        db = _mock_db_session()

        mock_upload_file = MagicMock()
        mock_upload_file.filename = "document.txt"
        mock_upload_file.content_type = "text/plain"
        mock_upload_file.read = AsyncMock(return_value=b"hello world")

        with pytest.raises(HTTPException) as exc_info:
            await upload_image_check(
                file=mock_upload_file,
                current_user=current_user,
                db=db,
            )

        assert exc_info.value.status_code == 400
        assert "unsupported file type" in exc_info.value.detail.lower()

    async def test_upload_pdf_returns_400(self) -> None:
        """PDF uploads must be rejected with HTTP 400."""
        from fastapi import HTTPException

        from src.api.v1.image_checker.router import upload_image_check

        current_user = _make_user()
        db = _mock_db_session()

        mock_upload_file = MagicMock()
        mock_upload_file.filename = "report.pdf"
        mock_upload_file.content_type = "application/pdf"
        mock_upload_file.read = AsyncMock(return_value=b"%PDF-1.4")

        with pytest.raises(HTTPException) as exc_info:
            await upload_image_check(
                file=mock_upload_file,
                current_user=current_user,
                db=db,
            )

        assert exc_info.value.status_code == 400

    async def test_upload_video_returns_400(self) -> None:
        """Video content type must be rejected."""
        from fastapi import HTTPException

        from src.api.v1.image_checker.router import upload_image_check

        current_user = _make_user()
        db = _mock_db_session()

        mock_upload_file = MagicMock()
        mock_upload_file.filename = "clip.mp4"
        mock_upload_file.content_type = "video/mp4"
        mock_upload_file.read = AsyncMock(return_value=b"\x00\x00\x00\x18ftyp")

        with pytest.raises(HTTPException) as exc_info:
            await upload_image_check(
                file=mock_upload_file,
                current_user=current_user,
                db=db,
            )

        assert exc_info.value.status_code == 400

    async def test_upload_too_large_returns_413(self) -> None:
        """Files exceeding the size limit must be rejected with 413."""
        from fastapi import HTTPException

        from src.api.v1.image_checker.router import upload_image_check

        current_user = _make_user()
        db = _mock_db_session()

        oversized = b"\xff\xd8\xff" + b"\x00" * (21 * 1024 * 1024)  # 21 MB

        mock_upload_file = MagicMock()
        mock_upload_file.filename = "huge.jpg"
        mock_upload_file.content_type = "image/jpeg"
        mock_upload_file.read = AsyncMock(return_value=oversized)

        with pytest.raises(HTTPException) as exc_info:
            await upload_image_check(
                file=mock_upload_file,
                current_user=current_user,
                db=db,
            )

        assert exc_info.value.status_code in (400, 413)

    async def test_upload_image_with_gps_returns_gps_data(self) -> None:
        """When extractor returns GPS data it must appear in the response."""
        from src.api.v1.image_checker.router import upload_image_check

        current_user = _make_user()
        db = _mock_db_session()
        file_bytes = _make_jpeg_bytes()
        metadata = _sample_extracted_metadata("gps.jpg", with_gps=True)

        mock_upload_file = MagicMock()
        mock_upload_file.filename = "gps.jpg"
        mock_upload_file.content_type = "image/jpeg"
        mock_upload_file.read = AsyncMock(return_value=file_bytes)

        with patch("src.api.v1.image_checker.router.ImageMetadataExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = metadata
            result = await upload_image_check(
                file=mock_upload_file,
                current_user=current_user,
                db=db,
            )

        assert result.gps_data is not None
        assert "maps_url" in result.gps_data or hasattr(result.gps_data, "maps_url")

    async def test_upload_sets_owner_id(self) -> None:
        """The persisted record must have owner_id matching the current user."""
        from src.api.v1.image_checker.router import upload_image_check

        user_id = uuid.uuid4()
        current_user = _make_user(user_id)
        db = _mock_db_session()
        file_bytes = _make_jpeg_bytes()
        metadata = _sample_extracted_metadata()

        mock_upload_file = MagicMock()
        mock_upload_file.filename = "test.jpg"
        mock_upload_file.content_type = "image/jpeg"
        mock_upload_file.read = AsyncMock(return_value=file_bytes)

        with patch("src.api.v1.image_checker.router.ImageMetadataExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = metadata
            await upload_image_check(
                file=mock_upload_file,
                current_user=current_user,
                db=db,
            )

        # Verify the model passed to db.add has the right owner
        added_model = db.add.call_args[0][0]
        assert added_model.owner_id == user_id


# ---------------------------------------------------------------------------
# Parametrized MIME type validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mime_type,should_succeed",
    [
        ("image/jpeg", True),
        ("image/png", True),
        ("image/tiff", True),
        ("image/webp", True),
        ("image/gif", True),
        ("image/bmp", True),
        ("text/plain", False),
        ("application/pdf", False),
        ("video/mp4", False),
        ("application/json", False),
        ("application/octet-stream", False),
    ],
)
async def test_upload_mime_type_validation(mime_type: str, should_succeed: bool) -> None:
    """Accepted image MIME types must pass; all others must raise HTTP 400."""
    from fastapi import HTTPException

    from src.api.v1.image_checker.router import upload_image_check

    current_user = _make_user()
    db = _mock_db_session()
    file_bytes = _make_jpeg_bytes()

    mock_upload_file = MagicMock()
    mock_upload_file.filename = "file.bin"
    mock_upload_file.content_type = mime_type
    mock_upload_file.read = AsyncMock(return_value=file_bytes)

    dummy_metadata = ExtractedMetadata(
        filename="file.bin",
        file_hash="c" * 64,
        file_size=len(file_bytes),
        mime_type=mime_type,
    )

    with patch("src.api.v1.image_checker.router.ImageMetadataExtractor") as MockExtractor:
        MockExtractor.return_value.extract.return_value = dummy_metadata
        if should_succeed:
            result = await upload_image_check(
                file=mock_upload_file,
                current_user=current_user,
                db=db,
            )
            assert result is not None
        else:
            with pytest.raises(HTTPException) as exc_info:
                await upload_image_check(
                    file=mock_upload_file,
                    current_user=current_user,
                    db=db,
                )
            assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/v1/image-checker/  — history / paginated list
# ---------------------------------------------------------------------------


class TestGetImageCheckHistory:
    """Tests for the paginated list endpoint."""

    async def test_returns_200_with_paginated_results(self) -> None:
        """Three DB rows must come back as three items with correct pagination metadata."""
        from src.api.v1.image_checker.router import list_image_checks

        current_user = _make_user()
        db = _mock_db_session()

        rows = [_image_check_model_fixture(current_user.id) for _ in range(3)]

        # Simulate two execute calls: one for count, one for rows
        count_result = MagicMock()
        count_result.scalar.return_value = 3
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = rows
        db.execute.side_effect = [count_result, rows_result]

        result = await list_image_checks(
            page=1,
            page_size=20,
            current_user=current_user,
            db=db,
        )

        assert len(result.items) == 3
        assert result.total == 3
        assert result.page == 1
        assert result.page_size == 20
        assert result.total_pages >= 1

    async def test_default_pagination_params(self) -> None:
        """Calling without explicit pagination must default to page=1 / page_size=20."""
        from src.api.v1.image_checker.router import list_image_checks

        current_user = _make_user()
        db = _mock_db_session()

        count_result = MagicMock()
        count_result.scalar.return_value = 0
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []
        db.execute.side_effect = [count_result, rows_result]

        result = await list_image_checks(current_user=current_user, db=db)

        assert result.page == 1
        assert result.page_size == 20
        assert result.items == []
        assert result.total == 0

    async def test_second_page(self) -> None:
        """Requesting page=2 with page_size=2 should set correct pagination fields."""
        from src.api.v1.image_checker.router import list_image_checks

        current_user = _make_user()
        db = _mock_db_session()

        rows = [_image_check_model_fixture(current_user.id) for _ in range(2)]
        count_result = MagicMock()
        count_result.scalar.return_value = 5  # 5 total → 3 pages with size=2
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = rows
        db.execute.side_effect = [count_result, rows_result]

        result = await list_image_checks(
            page=2,
            page_size=2,
            current_user=current_user,
            db=db,
        )

        assert result.page == 2
        assert result.page_size == 2
        assert result.total == 5
        assert result.total_pages == 3

    async def test_empty_history_returns_empty_list(self) -> None:
        """User with no uploads should receive an empty items list."""
        from src.api.v1.image_checker.router import list_image_checks

        current_user = _make_user()
        db = _mock_db_session()

        count_result = MagicMock()
        count_result.scalar.return_value = 0
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []
        db.execute.side_effect = [count_result, rows_result]

        result = await list_image_checks(
            page=1,
            page_size=20,
            current_user=current_user,
            db=db,
        )

        assert result.items == []
        assert result.total == 0
        assert result.total_pages == 0


# ---------------------------------------------------------------------------
# GET /api/v1/image-checker/{check_id}
# ---------------------------------------------------------------------------


class TestGetSingleImageCheck:
    """Tests for fetching a single check record."""

    async def test_get_owned_check_returns_200(self) -> None:
        """Fetching a check owned by the current user should return it."""
        from src.api.v1.image_checker.router import get_image_check

        current_user = _make_user()
        check_id = uuid.uuid4()
        db = _mock_db_session()

        row = _image_check_model_fixture(current_user.id, check_id)
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = row
        db.execute.return_value = query_result

        result = await get_image_check(
            check_id=check_id,
            current_user=current_user,
            db=db,
        )

        assert result.id == check_id or str(result.id) == str(check_id)

    async def test_get_nonexistent_check_returns_404(self) -> None:
        """A check ID that does not exist must raise HTTP 404."""
        from fastapi import HTTPException

        from src.api.v1.image_checker.router import get_image_check

        current_user = _make_user()
        db = _mock_db_session()

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None
        db.execute.return_value = query_result

        with pytest.raises(HTTPException) as exc_info:
            await get_image_check(
                check_id=uuid.uuid4(),
                current_user=current_user,
                db=db,
            )

        assert exc_info.value.status_code == 404

    async def test_get_check_owned_by_different_user_returns_404(self) -> None:
        """A check belonging to another user must return 404 (not 403) to prevent enumeration."""
        from fastapi import HTTPException

        from src.api.v1.image_checker.router import get_image_check

        current_user = _make_user()
        other_user_id = uuid.uuid4()
        check_id = uuid.uuid4()
        db = _mock_db_session()

        # DB query includes owner_id filter → returns None for cross-user lookup
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None
        db.execute.return_value = query_result

        with pytest.raises(HTTPException) as exc_info:
            await get_image_check(
                check_id=check_id,
                current_user=current_user,
                db=db,
            )

        # Must be 404, not 403 — prevents resource enumeration
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/image-checker/{check_id}
# ---------------------------------------------------------------------------


class TestDeleteImageCheck:
    """Tests for the delete endpoint."""

    async def test_delete_owned_check_returns_204(self) -> None:
        """Deleting an owned check must succeed and call session.delete."""
        from src.api.v1.image_checker.router import delete_image_check

        current_user = _make_user()
        check_id = uuid.uuid4()
        db = _mock_db_session()

        row = _image_check_model_fixture(current_user.id, check_id)
        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = row
        db.execute.return_value = query_result

        # Should complete without raising (204 No Content → None return value)
        await delete_image_check(
            check_id=check_id,
            current_user=current_user,
            db=db,
        )

        db.delete.assert_awaited_once_with(row)

    async def test_delete_nonexistent_check_returns_404(self) -> None:
        """Deleting a non-existent check must raise HTTP 404."""
        from fastapi import HTTPException

        from src.api.v1.image_checker.router import delete_image_check

        current_user = _make_user()
        db = _mock_db_session()

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None
        db.execute.return_value = query_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_image_check(
                check_id=uuid.uuid4(),
                current_user=current_user,
                db=db,
            )

        assert exc_info.value.status_code == 404

    async def test_delete_check_owned_by_other_user_returns_404(self) -> None:
        """Deleting a check owned by a different user must return 404."""
        from fastapi import HTTPException

        from src.api.v1.image_checker.router import delete_image_check

        current_user = _make_user()
        db = _mock_db_session()

        query_result = MagicMock()
        query_result.scalar_one_or_none.return_value = None
        db.execute.return_value = query_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_image_check(
                check_id=uuid.uuid4(),
                current_user=current_user,
                db=db,
            )

        assert exc_info.value.status_code == 404
        db.delete.assert_not_awaited()


# ---------------------------------------------------------------------------
# Response schema smoke tests
# ---------------------------------------------------------------------------


class TestResponseSchemas:
    """Verify that response models contain the expected fields."""

    async def test_upload_response_has_required_fields(self) -> None:
        """Upload response must include id, filename, file_hash, file_size, metadata."""
        from src.api.v1.image_checker.router import upload_image_check

        current_user = _make_user()
        db = _mock_db_session()
        file_bytes = _make_jpeg_bytes()
        metadata = _sample_extracted_metadata("check_fields.jpg")

        mock_upload_file = MagicMock()
        mock_upload_file.filename = "check_fields.jpg"
        mock_upload_file.content_type = "image/jpeg"
        mock_upload_file.read = AsyncMock(return_value=file_bytes)

        with patch("src.api.v1.image_checker.router.ImageMetadataExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = metadata
            result = await upload_image_check(
                file=mock_upload_file,
                current_user=current_user,
                db=db,
            )

        # All required fields must be present and non-None
        assert result.id is not None
        assert result.filename is not None
        assert result.file_hash is not None
        assert result.file_size is not None
        assert result.mime_type is not None
        # metadata (all_tags) must be a dict-like structure
        assert result.metadata is not None

    async def test_list_response_has_pagination_fields(self) -> None:
        """List response must expose total, page, page_size, total_pages."""
        from src.api.v1.image_checker.router import list_image_checks

        current_user = _make_user()
        db = _mock_db_session()

        count_result = MagicMock()
        count_result.scalar.return_value = 0
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []
        db.execute.side_effect = [count_result, rows_result]

        result = await list_image_checks(current_user=current_user, db=db)

        assert hasattr(result, "items")
        assert hasattr(result, "total")
        assert hasattr(result, "page")
        assert hasattr(result, "page_size")
        assert hasattr(result, "total_pages")
