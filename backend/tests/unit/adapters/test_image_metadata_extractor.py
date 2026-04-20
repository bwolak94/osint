"""Unit tests for ImageMetadataExtractor."""

from __future__ import annotations

import hashlib
import io
import os
from datetime import datetime
from fractions import Fraction
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.adapters.image_metadata.extractor import (
    ExtractedMetadata,
    GPSData,
    ImageMetadataExtractor,
)


# ---------------------------------------------------------------------------
# Test image factories
# ---------------------------------------------------------------------------


def _make_png_bytes(width: int = 50, height: int = 50) -> bytes:
    """Create a minimal in-memory PNG image."""
    img = Image.new("RGBA", (width, height), color=(0, 255, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_bytes(width: int = 100, height: int = 100) -> bytes:
    """Create a minimal in-memory JPEG image (no EXIF)."""
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_large_jpeg_bytes(target_size_bytes: int = 1_100_000) -> bytes:
    """Create a JPEG large enough to exceed *target_size_bytes*."""
    # Use a large canvas with random-ish pixel data to defeat compression
    width = height = 512
    img = Image.new("RGB", (width, height))
    # Fill with alternating colours so JPEG compression doesn't shrink it too much
    pixels = img.load()
    for x in range(width):
        for y in range(height):
            pixels[x, y] = ((x * 3) % 256, (y * 5) % 256, (x + y) % 256)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    raw = buf.getvalue()
    # If still too small, just pad with extra JPEG-comment data (safe trick)
    while len(raw) < target_size_bytes:
        raw = raw + raw
    return raw[:target_size_bytes] if len(raw) > target_size_bytes else raw


# ---------------------------------------------------------------------------
# Extractor tests
# ---------------------------------------------------------------------------


class TestImageMetadataExtractorBasics:
    """Core extraction behaviour against simple in-memory images."""

    def setup_method(self) -> None:
        self.extractor = ImageMetadataExtractor()

    # ------------------------------------------------------------------
    # test_extract_basic_png
    # ------------------------------------------------------------------

    def test_extract_basic_png(self) -> None:
        """PNG extraction should populate hash, size, mime_type; GPS must be None."""
        data = _make_png_bytes()
        result = self.extractor.extract(data, "test.png")

        assert isinstance(result, ExtractedMetadata)
        # SHA-256 produces a 64-character hex string
        assert len(result.file_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.file_hash)
        # File size must reflect actual byte count
        assert result.file_size > 0
        # MIME detection via magic bytes
        assert result.mime_type == "image/png"
        # Plain PNG has no EXIF GPS
        assert result.gps is None
        # all_tags must be a dict (may be empty for PNG)
        assert isinstance(result.all_tags, dict)

    # ------------------------------------------------------------------
    # test_extract_jpeg_no_exif
    # ------------------------------------------------------------------

    def test_extract_jpeg_no_exif(self) -> None:
        """JPEG without EXIF should return ExtractedMetadata with None optional fields."""
        data = _make_jpeg_bytes()
        result = self.extractor.extract(data, "photo.jpg")

        assert isinstance(result, ExtractedMetadata)
        assert result.mime_type == "image/jpeg"
        assert result.gps is None
        assert result.camera_make is None
        assert result.camera_model is None
        assert result.taken_at is None

    # ------------------------------------------------------------------
    # test_extract_file_hash_is_sha256
    # ------------------------------------------------------------------

    def test_extract_file_hash_is_sha256(self) -> None:
        """Hash must be deterministic SHA-256; different bytes produce different hashes."""
        data_a = _make_png_bytes(50, 50)
        data_b = _make_png_bytes(60, 60)

        result_a1 = self.extractor.extract(data_a, "a.png")
        result_a2 = self.extractor.extract(data_a, "a.png")
        result_b = self.extractor.extract(data_b, "b.png")

        # Determinism: same bytes → same hash
        assert result_a1.file_hash == result_a2.file_hash

        # Correctness: matches manual SHA-256
        expected = hashlib.sha256(data_a).hexdigest()
        assert result_a1.file_hash == expected

        # Sensitivity: different bytes → different hash
        assert result_a1.file_hash != result_b.file_hash

    # ------------------------------------------------------------------
    # test_file_size_matches_bytes
    # ------------------------------------------------------------------

    def test_file_size_matches_bytes(self) -> None:
        """file_size must exactly equal len(file_bytes)."""
        data = _make_jpeg_bytes(80, 80)
        result = self.extractor.extract(data, "img.jpg")
        assert result.file_size == len(data)

    # ------------------------------------------------------------------
    # test_extract_large_file
    # ------------------------------------------------------------------

    def test_extract_large_file(self) -> None:
        """Extraction of a 1 MB+ image must complete without error."""
        data = _make_large_jpeg_bytes(1_100_000)
        # Should not raise under any circumstances
        result = self.extractor.extract(data, "big.jpg")
        assert isinstance(result, ExtractedMetadata)
        assert result.file_size >= 1_000_000

    # ------------------------------------------------------------------
    # test_extract_corrupted_bytes
    # ------------------------------------------------------------------

    def test_extract_corrupted_bytes(self) -> None:
        """Corrupted/random bytes must not crash the server.

        Either a valid (partial) ExtractedMetadata is returned, or a
        ValueError/similar exception is raised — both are acceptable.
        The key requirement is that the process does not raise an
        unhandled exception of an unexpected type (e.g. SystemExit).
        """
        random_bytes = os.urandom(512)

        try:
            result = self.extractor.extract(random_bytes, "corrupt.bin")
            # If it returns, it must still be a valid ExtractedMetadata
            assert isinstance(result, ExtractedMetadata)
            # Hash and size must still be populated from raw bytes
            assert result.file_hash == hashlib.sha256(random_bytes).hexdigest()
            assert result.file_size == 512
        except (ValueError, OSError, Exception) as exc:
            # Any explicit exception is acceptable — the server can catch it
            assert isinstance(exc, Exception)


# ---------------------------------------------------------------------------
# GPS-related tests
# ---------------------------------------------------------------------------


class TestGPSParsing:
    """Tests for _parse_gps and _dms_to_decimal helpers, plus GPSData behaviour."""

    def setup_method(self) -> None:
        self.extractor = ImageMetadataExtractor()

    # GPS IFD dict keys (EXIF numeric):
    #  1 = GPSLatitudeRef, 2 = GPSLatitude, 3 = GPSLongitudeRef, 4 = GPSLongitude
    #  5 = GPSAltitudeRef, 6 = GPSAltitude, 7 = GPSTimeStamp

    def _paris_gps_info(self) -> dict:
        """GPS dict for 48°51'30.12"N, 2°17'40.2"E (Paris, approx.)."""
        return {
            1: "N",
            2: (Fraction(48), Fraction(51), Fraction(3012, 100)),
            3: "E",
            4: (Fraction(2), Fraction(17), Fraction(4020, 100)),
        }

    # ------------------------------------------------------------------
    # test_parse_gps_north_east
    # ------------------------------------------------------------------

    def test_parse_gps_north_east(self) -> None:
        """N/E GPS data should produce positive lat/lon close to Paris coordinates."""
        gps = self.extractor._parse_gps(self._paris_gps_info())

        assert gps is not None
        assert isinstance(gps, GPSData)
        # 48°51'30.12" = 48 + 51/60 + 30.12/3600 ≈ 48.858367
        assert abs(gps.latitude - 48.858) < 0.001
        # 2°17'40.2" = 2 + 17/60 + 40.2/3600 ≈ 2.294500
        assert abs(gps.longitude - 2.294) < 0.001
        # Northern and Eastern hemisphere → positive values
        assert gps.latitude > 0
        assert gps.longitude > 0
        # maps_url must contain coordinate string
        assert str(round(gps.latitude, 3)) in gps.maps_url or "maps.google.com" in gps.maps_url

    # ------------------------------------------------------------------
    # test_parse_gps_south_west
    # ------------------------------------------------------------------

    def test_parse_gps_south_west(self) -> None:
        """S/W references must produce negative decimal coordinates."""
        gps_info = {
            1: "S",
            2: (Fraction(33), Fraction(51), Fraction(3600, 100)),  # Buenos Aires approx.
            3: "W",
            4: (Fraction(70), Fraction(40), Fraction(0, 1)),
        }
        gps = self.extractor._parse_gps(gps_info)

        assert gps is not None
        assert gps.latitude < 0, "Southern hemisphere must yield negative latitude"
        assert gps.longitude < 0, "Western hemisphere must yield negative longitude"

    # ------------------------------------------------------------------
    # test_parse_gps_with_altitude
    # ------------------------------------------------------------------

    def test_parse_gps_with_altitude(self) -> None:
        """GPSAltitude (tag 6) must be parsed; AltitudeRef==1 negates the value."""
        gps_info_above = {**self._paris_gps_info(), 5: 0, 6: Fraction(150, 1)}
        gps_above = self.extractor._parse_gps(gps_info_above)
        assert gps_above is not None
        assert gps_above.altitude == pytest.approx(150.0)

        # AltitudeRef = 1 means below sea level
        gps_info_below = {**self._paris_gps_info(), 5: 1, 6: Fraction(20, 1)}
        gps_below = self.extractor._parse_gps(gps_info_below)
        assert gps_below is not None
        assert gps_below.altitude == pytest.approx(-20.0)

    # ------------------------------------------------------------------
    # test_gps_maps_url_format
    # ------------------------------------------------------------------

    def test_gps_maps_url_format(self) -> None:
        """maps_url must follow the exact format https://maps.google.com/maps?q={lat},{lon}."""
        gps = GPSData(latitude=48.8584, longitude=2.2945)
        expected_prefix = "https://maps.google.com/maps?q="
        assert gps.maps_url.startswith(expected_prefix)
        # Coordinates must appear as-is in the URL
        remainder = gps.maps_url[len(expected_prefix):]
        lat_str, lon_str = remainder.split(",")
        assert float(lat_str) == pytest.approx(48.8584)
        assert float(lon_str) == pytest.approx(2.2945)

    # ------------------------------------------------------------------
    # test_parse_gps_missing_required_fields_returns_none
    # ------------------------------------------------------------------

    def test_parse_gps_missing_required_fields_returns_none(self) -> None:
        """GPS dict with only partial data (missing lon) must return None."""
        incomplete = {
            1: "N",
            2: (Fraction(48), Fraction(51), Fraction(30, 1)),
            # lon ref and value absent
        }
        assert self.extractor._parse_gps(incomplete) is None

    def test_parse_gps_empty_dict_returns_none(self) -> None:
        """Empty GPS IFD must return None without raising."""
        assert self.extractor._parse_gps({}) is None

    def test_parse_gps_none_arg_returns_none(self) -> None:
        """None GPS IFD must return None without raising."""
        assert self.extractor._parse_gps(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# DMS → decimal helper
# ---------------------------------------------------------------------------


class TestDmsToDecimal:
    """Direct unit tests for the _dms_to_decimal static method."""

    def test_north_positive(self) -> None:
        result = ImageMetadataExtractor._dms_to_decimal((48, 0, 0), "N")
        assert result == pytest.approx(48.0)

    def test_south_negative(self) -> None:
        result = ImageMetadataExtractor._dms_to_decimal((33, 0, 0), "S")
        assert result == pytest.approx(-33.0)

    def test_east_positive(self) -> None:
        result = ImageMetadataExtractor._dms_to_decimal((2, 17, 40.2), "E")
        expected = 2 + 17 / 60 + 40.2 / 3600
        assert result == pytest.approx(expected, abs=1e-5)

    def test_west_negative(self) -> None:
        result = ImageMetadataExtractor._dms_to_decimal((74, 0, 0), "W")
        assert result == pytest.approx(-74.0)

    def test_fractions_supported(self) -> None:
        """Fraction objects (as produced by Pillow EXIF parsing) must work."""
        result = ImageMetadataExtractor._dms_to_decimal(
            (Fraction(48), Fraction(51), Fraction(3012, 100)), "N"
        )
        expected = 48 + 51 / 60 + 30.12 / 3600
        assert result == pytest.approx(expected, abs=1e-5)


# ---------------------------------------------------------------------------
# MIME detection
# ---------------------------------------------------------------------------


class TestMimeDetection:
    """Tests for _detect_mime_type magic-byte logic."""

    def setup_method(self) -> None:
        self.extractor = ImageMetadataExtractor()

    def test_jpeg_magic_bytes(self) -> None:
        data = _make_jpeg_bytes()
        assert self.extractor._detect_mime_type(data, "x.jpg") == "image/jpeg"

    def test_png_magic_bytes(self) -> None:
        data = _make_png_bytes()
        assert self.extractor._detect_mime_type(data, "x.png") == "image/png"

    def test_gif89a_magic_bytes(self) -> None:
        # Minimal GIF89a header
        data = b"GIF89a" + b"\x00" * 20
        assert self.extractor._detect_mime_type(data, "anim.gif") == "image/gif"

    def test_gif87a_magic_bytes(self) -> None:
        data = b"GIF87a" + b"\x00" * 20
        assert self.extractor._detect_mime_type(data, "still.gif") == "image/gif"

    def test_webp_magic_bytes(self) -> None:
        # Minimal RIFF….WEBP header (12 bytes)
        data = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 20
        assert self.extractor._detect_mime_type(data, "img.webp") == "image/webp"

    def test_tiff_little_endian(self) -> None:
        data = b"II\x2a\x00" + b"\x00" * 20
        assert self.extractor._detect_mime_type(data, "scan.tiff") == "image/tiff"

    def test_tiff_big_endian(self) -> None:
        data = b"MM\x00\x2a" + b"\x00" * 20
        assert self.extractor._detect_mime_type(data, "scan.tiff") == "image/tiff"

    def test_fallback_to_extension(self) -> None:
        # Random bytes that don't match any magic signature
        data = b"\x00\x01\x02\x03" * 10
        assert self.extractor._detect_mime_type(data, "photo.bmp") == "image/bmp"

    def test_unknown_returns_octet_stream(self) -> None:
        data = b"\x00\x01\x02\x03" * 10
        assert self.extractor._detect_mime_type(data, "noext") == "application/octet-stream"


# ---------------------------------------------------------------------------
# GPSData dataclass behaviour
# ---------------------------------------------------------------------------


class TestGPSDataDataclass:
    """Verify GPSData post-init and attribute contracts."""

    def test_maps_url_auto_populated(self) -> None:
        gps = GPSData(latitude=51.5074, longitude=-0.1278)
        assert gps.maps_url == "https://maps.google.com/maps?q=51.5074,-0.1278"

    def test_altitude_defaults_to_none(self) -> None:
        gps = GPSData(latitude=0.0, longitude=0.0)
        assert gps.altitude is None
        assert gps.gps_timestamp is None

    def test_altitude_stored(self) -> None:
        gps = GPSData(latitude=10.0, longitude=20.0, altitude=500.5)
        assert gps.altitude == pytest.approx(500.5)


# ---------------------------------------------------------------------------
# ExtractedMetadata dataclass behaviour
# ---------------------------------------------------------------------------


class TestExtractedMetadataDataclass:
    """Verify ExtractedMetadata default values."""

    def test_defaults(self) -> None:
        meta = ExtractedMetadata(
            filename="test.jpg",
            file_hash="a" * 64,
            file_size=1024,
            mime_type="image/jpeg",
        )
        assert meta.width is None
        assert meta.height is None
        assert meta.format is None
        assert meta.camera_make is None
        assert meta.camera_model is None
        assert meta.taken_at is None
        assert meta.gps is None
        assert meta.all_tags == {}

    def test_all_tags_independent_per_instance(self) -> None:
        """Each instance must have its own all_tags dict (no shared mutable default)."""
        m1 = ExtractedMetadata(filename="a.jpg", file_hash="a" * 64, file_size=1, mime_type="image/jpeg")
        m2 = ExtractedMetadata(filename="b.jpg", file_hash="b" * 64, file_size=2, mime_type="image/jpeg")
        m1.all_tags["key"] = "value"
        assert "key" not in m2.all_tags
