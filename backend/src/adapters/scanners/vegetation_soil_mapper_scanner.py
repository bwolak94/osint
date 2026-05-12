"""Vegetation & Soil Mapper Scanner — climate, biome, and vegetation context from coordinates.

OPSEC intelligence value:
  - Vegetation zone narrows a photograph's possible location to a latitude band and climate region.
  - Koppen-Geiger classification eliminates large swaths of the globe when matching an image.
  - Soil type provides additional discriminators: red laterite soil → tropics, black chernozem →
    Central Asian steppe, white caliche → arid Southwest US/Mexico.
  - Climate data from Open-Meteo provides quantitative confirmation of analyst vegetation theory.
  - Combined with language/script cues, vegetation classification can often narrow location to
    a single country or coastal vs inland region.

Input entities:  COORDINATES — "lat,lon" decimal string
Output entities:
  - climate_zone        — Koppen-Geiger code and description
  - vegetation_type     — biome label and key indicator flora
  - soil_type_estimate  — dominant soil order for the location
  - biome               — WWF biome name
  - regional_flora_hints — list of indicator plant species
  - koppen_code         — raw Koppen code (e.g., "Cfb")
  - educational_note    — IMINT vegetation analysis methodology
"""

from __future__ import annotations

import math
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_OPEN_METEO_CLIMATE_URL = "https://climate-api.open-meteo.com/v1/climate"
_HEADERS = {"User-Agent": "OSINT-Platform/1.0 contact@example.com"}

_EDUCATIONAL_NOTE = (
    "IMINT vegetation analysis for location narrowing: "
    "1) Canopy type — broadleaf (temperate/tropical) vs needleleaf (boreal/high elevation). "
    "2) Leaf colour — year-round green (tropical/oceanic) vs seasonal yellowing (continental). "
    "3) Grass colour — lush green = high rainfall; straw yellow = dry season savanna; "
    "   grey-green = drought-adapted Mediterranean scrub. "
    "4) Soil colour in eroded areas — red laterite (tropics), black chernozem (steppe), "
    "   white/pale caliche (desert), brown podzol (boreal). "
    "5) Indicator species — coconut palms (humid tropics), date palms (arid Middle East/N. Africa), "
    "   baobab (African savanna), cypress (Mediterranean), birch-dominance (boreal transition). "
    "6) Agricultural patterns — rice paddies (monsoon Asia), olive groves (Mediterranean), "
    "   sunflower fields (Black Sea basin), vineyard terraces (wine regions)."
)

# Koppen-Geiger classification table (simplified, by latitude and general rules)
# Format: (min_abs_lat, max_abs_lat, default_code, label, biome, soil, flora_hints)
_KOPPEN_TABLE: list[dict[str, Any]] = [
    {
        "min_lat": 0, "max_lat": 5,
        "code": "Af", "label": "Tropical rainforest",
        "biome": "Tropical & Subtropical Moist Broadleaf Forests",
        "soil": "Oxisol / Ultisol — deeply weathered, nutrient-poor red-yellow soils",
        "flora": ["Dipterocarp trees", "Ferns", "Bromeliads", "Lianas", "Orchids", "Mangrove (coastal)"],
        "vegetation": "Dense multi-layer rainforest canopy; year-round green; extremely high biodiversity",
    },
    {
        "min_lat": 5, "max_lat": 15,
        "code": "Aw", "label": "Tropical savanna",
        "biome": "Tropical & Subtropical Grasslands, Savannas & Shrublands",
        "soil": "Alfisol / Vertisol — fertile but seasonally cracking dark clay soils",
        "flora": ["Acacia", "Baobab", "Elephant grass", "Combretum", "Terminalia"],
        "vegetation": "Open grassland with scattered flat-topped trees; distinct wet/dry season; straw-yellow dry season",
    },
    {
        "min_lat": 15, "max_lat": 25,
        "code": "BWh", "label": "Hot desert",
        "biome": "Deserts & Xeric Shrublands",
        "soil": "Aridisol — thin, alkaline, calcareous soils; white caliche crust common",
        "flora": ["Date palm", "Tamarisk", "Acacia tortilis", "Succulents", "Halophytes"],
        "vegetation": "Sparse xerophyte scrub or bare rock/sand; ephemeral green after rainfall only",
    },
    {
        "min_lat": 25, "max_lat": 35,
        "code": "BSh/Csa", "label": "Semi-arid / Mediterranean",
        "biome": "Mediterranean Forests, Woodlands & Scrub",
        "soil": "Mollisol / Inceptisol — moderately fertile; red-brown Mediterranean terra rossa",
        "flora": ["Olive", "Aleppo pine", "Rosemary", "Lavender", "Cypress", "Agave (Americas)"],
        "vegetation": "Drought-adapted sclerophyll shrubs and pines; summer-dry brown grass; green winters",
    },
    {
        "min_lat": 35, "max_lat": 45,
        "code": "Cfb/Cfa", "label": "Oceanic / Humid subtropical",
        "biome": "Temperate Broadleaf & Mixed Forests",
        "soil": "Alfisol / Mollisol — fertile, well-structured; brown forest soils",
        "flora": ["Oak", "Maple", "Beech", "Elm", "Chestnut", "Magnolia (humid subtropical)"],
        "vegetation": "Deciduous broadleaf forest; vivid autumn colours; lush green summer; dormant grey winter",
    },
    {
        "min_lat": 45, "max_lat": 55,
        "code": "Dfb", "label": "Humid continental",
        "biome": "Temperate Broadleaf & Mixed Forests / Grasslands",
        "soil": "Mollisol / Spodosol — deep chernozem in grasslands; podzolic in forests",
        "flora": ["Spruce", "Fir", "Aspen", "Birch", "Scots pine", "Wheat/sunflower in open areas"],
        "vegetation": "Mixed conifer-deciduous; long snowy winters; vivid spring green; agricultural plains common",
    },
    {
        "min_lat": 55, "max_lat": 65,
        "code": "Dfc", "label": "Subarctic / Boreal",
        "biome": "Boreal Forests / Taiga",
        "soil": "Spodosol / Histosol — acidic podzol; extensive peat bogs",
        "flora": ["Black spruce", "Jack pine", "Tamarack", "Cloudberry", "Labrador tea", "Sphagnum moss"],
        "vegetation": "Dense conifer taiga; dark green year-round; permafrost patches; extensive wetlands",
    },
    {
        "min_lat": 65, "max_lat": 75,
        "code": "ET", "label": "Tundra",
        "biome": "Tundra",
        "soil": "Gelisol — permanently frozen permafrost; thin active layer",
        "flora": ["Dwarf birch", "Cotton grass", "Arctic willow", "Crowberry", "Reindeer lichen"],
        "vegetation": "Low shrubs, sedges, mosses, lichens; treeless; summer thaw reveals waterlogged surface",
    },
    {
        "min_lat": 75, "max_lat": 90,
        "code": "EF", "label": "Ice cap",
        "biome": "Rock & Ice",
        "soil": "No soil — bedrock or permanent ice sheet",
        "flora": [],
        "vegetation": "Permanent ice or snow; minimal to no vegetation; polar desert",
    },
]


def _classify_by_latitude(abs_lat: float) -> dict[str, Any]:
    for zone in _KOPPEN_TABLE:
        if zone["min_lat"] <= abs_lat < zone["max_lat"]:
            return zone
    return _KOPPEN_TABLE[-1]  # fallback to ice cap


def _hemisphere_season_note(lat: float) -> str:
    if lat >= 0:
        return "Northern hemisphere: summer Jun-Aug, winter Dec-Feb"
    return "Southern hemisphere: summer Dec-Feb, winter Jun-Aug"


class VegetationSoilMapperScanner(BaseOsintScanner):
    """Map climate zone, vegetation type, and soil type from decimal coordinates.

    Input:  ScanInputType.COORDINATES — "lat,lon" string.
    Output: climate_zone, vegetation_type, soil_type_estimate, biome, regional_flora_hints.

    Uses Open-Meteo Climate API for temperature/precipitation confirmation.
    Falls back to hardcoded Koppen-Geiger table if API unavailable.
    """

    scanner_name = "vegetation_soil_mapper"
    supported_input_types = frozenset({ScanInputType.COORDINATES})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        lat, lon = self._parse_coordinates(input_value)
        if lat is None or lon is None:
            return self._error_result(input_value, "Invalid coordinate format. Expected 'lat,lon'.")

        abs_lat = abs(lat)
        zone = _classify_by_latitude(abs_lat)

        # Attempt Open-Meteo climate data for quantitative confirmation
        climate_data = await self._fetch_climate_data(lat, lon)

        # Refine Koppen code using temperature/precipitation if available
        refined_code = self._refine_koppen(zone["code"], climate_data, abs_lat, lon)

        return {
            "input": input_value,
            "found": True,
            "lat": lat,
            "lon": lon,
            "koppen_code": refined_code,
            "climate_zone": zone["label"],
            "vegetation_type": zone["vegetation"],
            "soil_type_estimate": zone["soil"],
            "biome": zone["biome"],
            "regional_flora_hints": zone["flora"],
            "hemisphere_season_note": _hemisphere_season_note(lat),
            "climate_data": climate_data,
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [f"coordinates:{lat},{lon}"],
        }

    # ------------------------------------------------------------------
    # Coordinate parsing
    # ------------------------------------------------------------------

    def _parse_coordinates(self, value: str) -> tuple[float | None, float | None]:
        try:
            parts = value.strip().split(",")
            if len(parts) < 2:
                return None, None
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return None, None
            return lat, lon
        except ValueError:
            return None, None

    # ------------------------------------------------------------------
    # Open-Meteo climate fetch
    # ------------------------------------------------------------------

    async def _fetch_climate_data(self, lat: float, lon: float) -> dict[str, Any]:
        """Fetch current-month temperature and precipitation normals."""
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS) as client:
                params = {
                    "latitude": str(lat),
                    "longitude": str(lon),
                    "current": "temperature_2m,precipitation",
                    "timezone": "auto",
                }
                resp = await client.get(_OPEN_METEO_URL, params=params)
                if resp.status_code != 200:
                    return {}
                data = resp.json()
                current = data.get("current", {})
                return {
                    "current_temperature_c": current.get("temperature_2m"),
                    "current_precipitation_mm": current.get("precipitation"),
                    "timezone": data.get("timezone"),
                    "elevation_m": data.get("elevation"),
                }
        except Exception as exc:
            log.warning("Open-Meteo climate fetch failed", lat=lat, lon=lon, error=str(exc))
            return {}

    # ------------------------------------------------------------------
    # Koppen refinement
    # ------------------------------------------------------------------

    def _refine_koppen(
        self, base_code: str, climate_data: dict[str, Any], abs_lat: float, lon: float
    ) -> str:
        """Apply temperature-based refinement to base Koppen code."""
        temp = climate_data.get("current_temperature_c")
        precip = climate_data.get("current_precipitation_mm")

        if temp is None:
            return base_code

        # Cold refinement: if temp < -3°C, shift to continental D-class
        if temp < -3 and base_code.startswith("C"):
            return base_code.replace("C", "D", 1)

        # Hot refinement: if temp > 18°C and low precip, shift toward desert
        if temp > 18 and precip is not None and precip < 1 and not base_code.startswith("E"):
            return "BWh" if abs_lat < 35 else "BSk"

        return base_code

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _error_result(self, input_value: str, error: str) -> dict[str, Any]:
        return {
            "input": input_value,
            "found": False,
            "error": error,
            "koppen_code": "",
            "climate_zone": "",
            "vegetation_type": "",
            "soil_type_estimate": "",
            "biome": "",
            "regional_flora_hints": [],
            "hemisphere_season_note": "",
            "climate_data": {},
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
