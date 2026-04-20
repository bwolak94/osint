"""Phone number scanner — validates and extracts metadata from phone numbers."""

from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Mapping from PhoneNumberType enum values to human-readable labels
_LINE_TYPE_MAP = {
    0: "fixed_line",
    1: "mobile",
    2: "fixed_line_or_mobile",
    3: "toll_free",
    4: "premium_rate",
    5: "shared_cost",
    6: "voip",
    7: "personal_number",
    8: "pager",
    9: "uan",
    10: "voicemail",
    -1: "unknown",
}


class PhoneScanner(BaseOsintScanner):
    """Parses phone numbers using the phonenumbers library (pure Python, no API key needed).

    Extracts country, carrier, line type, and validation status.
    """

    scanner_name = "phone_lookup"
    supported_input_types = frozenset({ScanInputType.PHONE})
    cache_ttl = 604800  # 7 days — phone metadata rarely changes

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            import phonenumbers
            from phonenumbers import carrier as pn_carrier
            from phonenumbers import geocoder as pn_geocoder
            from phonenumbers import timezone as pn_timezone
        except ImportError:
            log.warning("phonenumbers library not installed, returning stub result")
            return {
                "phone": input_value,
                "found": False,
                "error": "phonenumbers library is not installed. Run: pip install phonenumbers",
                "extracted_identifiers": [],
                "_stub": True,
            }

        try:
            # Parse the number (assume international format, fall back to US if no country code)
            parsed = phonenumbers.parse(input_value, None)
        except phonenumbers.NumberParseException:
            try:
                # Retry with a default region
                parsed = phonenumbers.parse(input_value, "US")
            except phonenumbers.NumberParseException as e:
                return {
                    "phone": input_value,
                    "found": False,
                    "valid": False,
                    "error": f"Could not parse phone number: {e}",
                    "extracted_identifiers": [],
                }

        is_valid = phonenumbers.is_valid_number(parsed)
        is_possible = phonenumbers.is_possible_number(parsed)

        # Extract metadata
        country_code = parsed.country_code
        national_number = str(parsed.national_number)
        region_code = phonenumbers.region_code_for_number(parsed) or ""
        carrier_name = pn_carrier.name_for_number(parsed, "en") or ""
        location = pn_geocoder.description_for_number(parsed, "en") or ""
        timezones = list(pn_timezone.time_zones_for_number(parsed))

        # Determine line type
        number_type = phonenumbers.number_type(parsed)
        line_type = _LINE_TYPE_MAP.get(number_type, "unknown")

        # Format the number in standard formats
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        international = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)

        identifiers: list[str] = []
        if carrier_name:
            identifiers.append(f"carrier:{carrier_name}")
        if region_code:
            identifiers.append(f"country:{region_code}")

        return {
            "phone": input_value,
            "found": True,
            "valid": is_valid,
            "possible": is_possible,
            "country_code": country_code,
            "national_number": national_number,
            "region_code": region_code,
            "carrier": carrier_name,
            "location": location,
            "line_type": line_type,
            "timezones": timezones,
            "e164": e164,
            "international": international,
            "extracted_identifiers": identifiers,
        }
