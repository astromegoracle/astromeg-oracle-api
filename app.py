from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import time
from typing import Annotated, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
import swisseph as swe


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("astromeg-oracle")

BASE_DIR = Path(__file__).resolve().parent
EPHE_PATH = BASE_DIR / "ephe"
PLACE_CACHE_FILE = BASE_DIR / "place_cache.json"
EPHE_FILES = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")
USER_AGENT = "astromeg-oracle-api/1.0"
GEOCODE_TIMEOUT_SECONDS = 3
LOOKUP_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 0.25
HOUSE_SYSTEM = "Placidus"
ZODIAC = "Tropical"
OPEN_METEO_API_KEY = os.environ.get("OPEN_METEO_API_KEY", "").strip()
OPEN_METEO_GEOCODE_URL = (
    "https://customer-geocoding-api.open-meteo.com/v1/search"
    if OPEN_METEO_API_KEY
    else "https://geocoding-api.open-meteo.com/v1/search"
)
JULIAN_DAY_UNIX_EPOCH = 2440587.5
SOLAR_RETURN_TOLERANCE_ARCSECONDS = 1.0
SOLAR_RETURN_SOLVE_TOLERANCE_ARCSECONDS = 0.001
SOLAR_RETURN_SEARCH_STEP_DAYS = 0.25
SOLAR_RETURN_MAX_ITERATIONS = 80
TROPICAL_YEAR_DAYS = 365.242189

os.environ["SE_EPHE_PATH"] = str(EPHE_PATH)
swe.set_ephe_path(str(EPHE_PATH))


class ErrorResponse(BaseModel):
    status: str = "error"
    success: bool = False
    message: str
    details: str = ""


class HouseCuspResponse(BaseModel):
    house: int
    sign: str
    degree: float
    absolute_degree: float


class HousesResponse(BaseModel):
    system: str = "Placidus"
    cusps: list[HouseCuspResponse]


class BirthDataResponse(BaseModel):
    year: int
    month: int
    day: int
    hour: int
    minute: int
    birthplace: str
    resolved_place: str
    latitude: float
    longitude: float
    timezone: str
    timezone_offset: float
    zodiac: str = "Tropical"
    house_system: str = "Placidus"


class PlacementResponse(BaseModel):
    body: str
    sign: str
    degree: float
    absolute_degree: float
    house: int


class AspectResponse(BaseModel):
    body_a: str
    body_b: str
    aspect: str
    orb: float


class PlanetsResponse(BaseModel):
    sun: float = Field(alias="Sun")
    moon: float = Field(alias="Moon")
    mercury: float = Field(alias="Mercury")
    venus: float = Field(alias="Venus")
    mars: float = Field(alias="Mars")
    jupiter: float = Field(alias="Jupiter")
    saturn: float = Field(alias="Saturn")
    uranus: float = Field(alias="Uranus")
    neptune: float = Field(alias="Neptune")
    pluto: float = Field(alias="Pluto")
    north_node: float = Field(alias="North Node")
    lilith: float = Field(alias="Lilith")
    chiron: float = Field(alias="Chiron")


class ChartResponse(BaseModel):
    status: str = "success"
    success: bool = True
    message: str = "Chart calculated successfully"
    verified_chart_data: bool = True
    chart: str
    chart_text: str
    result: str
    placements_text: str
    body_count: int
    birth_data: BirthDataResponse
    placements: list[PlacementResponse]
    houses: list[HouseCuspResponse]
    ascendant: float
    midheaven: float
    aspects: list[AspectResponse] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
    engine: str = "Swiss Ephemeris"
    zodiac: str = "Tropical"
    houses: str = "Placidus"
    ephe_path: str
    ephe_files: dict[str, bool]
    cache_entries: int


class TestCaseResult(BaseModel):
    birthplace: str
    status: str
    latitude: float | None = None
    longitude: float | None = None
    timezone: float | None = None
    message: str | None = None


class TestResponse(BaseModel):
    status: str
    total: int
    passed: int
    failed: int
    cases: list[TestCaseResult]


class PlaceResolution(BaseModel):
    query: str
    birthplace_resolved: str
    latitude: float
    longitude: float
    timezone_name: str


class SolarReturnRequest(BaseModel):
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_minute: int
    birthplace: str
    return_year: int
    return_location: str


class ProgressedChartRequest(BaseModel):
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_minute: int
    birthplace: str
    progression_year: int
    progression_month: int
    progression_day: int
    progression_hour: int = 12
    progression_minute: int = 0
    progression_location: Optional[str] = None


CHART_SUCCESS_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": [
        "status",
        "success",
        "message",
        "verified_chart_data",
        "chart",
        "chart_text",
        "result",
        "placements_text",
        "body_count",
        "birth_data",
        "placements",
        "houses",
        "ascendant",
        "ascendant_position",
        "midheaven",
        "midheaven_position",
        "aspects",
    ],
    "properties": {
        "status": {"type": "string"},
        "success": {"type": "boolean"},
        "message": {"type": "string"},
        "verified_chart_data": {"type": "boolean", "description": "True only when Swiss Ephemeris returned verified chart placements."},
        "chart": {"type": "string", "description": "Plain-language verified chart placements. Use this field when answering users."},
        "chart_text": {"type": "string", "description": "Plain-language verified chart placements for GPT Actions compatibility."},
        "result": {"type": "string", "description": "Backward-compatible verified placement summary for previously imported Actions."},
        "placements_text": {"type": "string", "description": "Semicolon-delimited verified placement summary."},
        "body_count": {"type": "integer", "description": "Number of calculated chart bodies returned in placements."},
        "birth_data": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "birthplace": {"type": "string"},
                "resolved_place": {"type": "string"},
                "timezone": {"type": "string"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
            },
        },
        "placements": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "body": {"type": "string"},
                    "sign": {"type": "string"},
                    "degree": {"type": "number"},
                    "position": {"type": "object", "additionalProperties": True},
                    "house": {"type": "integer"},
                },
            },
        },
        "houses": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "house": {"type": "integer"},
                    "sign": {"type": "string"},
                    "degree": {"type": "number"},
                    "position": {"type": "object", "additionalProperties": True},
                },
            },
        },
        "ascendant": {"type": "number"},
        "ascendant_position": {"type": "object", "additionalProperties": True},
        "midheaven": {"type": "number"},
        "midheaven_position": {"type": "object", "additionalProperties": True},
        "aspects": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": True},
        },
    },
}
ERROR_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": ["status", "success", "message", "details"],
    "properties": {
        "status": {"type": "string"},
        "success": {"type": "boolean"},
        "message": {"type": "string"},
        "details": {"type": "string"},
        "http_status": {"type": "integer"},
    },
}
CHART_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": ["status", "success", "message"],
    "properties": {
        **CHART_SUCCESS_SCHEMA["properties"],
        **ERROR_SCHEMA["properties"],
    },
}
SOLAR_RETURN_REQUEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "birth_year",
        "birth_month",
        "birth_day",
        "birth_hour",
        "birth_minute",
        "birthplace",
        "return_year",
        "return_location",
    ],
    "properties": {
        "birth_year": {"type": "integer", "example": 1972},
        "birth_month": {"type": "integer", "example": 7},
        "birth_day": {"type": "integer", "example": 31},
        "birth_hour": {"type": "integer", "example": 22},
        "birth_minute": {"type": "integer", "example": 50},
        "birthplace": {"type": "string", "example": "Quezon City, Philippines"},
        "return_year": {"type": "integer", "example": 2026},
        "return_location": {"type": "string", "example": "Quezon City, Philippines"},
    },
}
SOLAR_RETURN_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": ["status", "success", "message", "verified_solar_return"],
    "properties": {
        "status": {"type": "string"},
        "success": {"type": "boolean"},
        "message": {"type": "string"},
        "verified_solar_return": {"type": "boolean"},
        "natal_sun_longitude": {"type": "number"},
        "return_sun_longitude": {"type": "number"},
        "longitude_delta_arcseconds": {"type": "number"},
        "exact_return_utc": {"type": "string"},
        "exact_return_local": {"type": "string"},
        "return_location": {"type": "string"},
        "return_location_resolved": {"type": "string"},
        "return_location_latitude": {"type": "number"},
        "return_location_longitude": {"type": "number"},
        "return_location_timezone": {"type": "string"},
        "chart": {"type": "object", "additionalProperties": True},
        "birth_data": {"type": "object", "additionalProperties": True},
        "placements": CHART_SUCCESS_SCHEMA["properties"]["placements"],
        "houses": CHART_SUCCESS_SCHEMA["properties"]["houses"],
    },
}
PROGRESSED_CHART_REQUEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "birth_year",
        "birth_month",
        "birth_day",
        "birth_hour",
        "birth_minute",
        "birthplace",
        "progression_year",
        "progression_month",
        "progression_day",
    ],
    "properties": {
        "birth_year": {"type": "integer", "example": 1972},
        "birth_month": {"type": "integer", "example": 7},
        "birth_day": {"type": "integer", "example": 31},
        "birth_hour": {"type": "integer", "example": 22},
        "birth_minute": {"type": "integer", "example": 50},
        "birthplace": {"type": "string", "example": "Quezon City, Philippines"},
        "progression_year": {"type": "integer", "example": 2026},
        "progression_month": {"type": "integer", "example": 8},
        "progression_day": {"type": "integer", "example": 1},
        "progression_hour": {"type": "integer", "example": 12, "default": 12},
        "progression_minute": {"type": "integer", "example": 0, "default": 0},
        "progression_location": {
            "type": "string",
            "example": "Quezon City, Philippines",
            "description": "Optional location for progressed angles. Defaults to birthplace.",
        },
    },
}
PROGRESSED_CHART_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": ["status", "success", "message", "verified_progressed_chart", "placements", "houses"],
    "properties": {
        "status": {"type": "string"},
        "success": {"type": "boolean"},
        "message": {"type": "string"},
        "verified_progressed_chart": {"type": "boolean"},
        "progression_method": {"type": "string"},
        "angles_method": {"type": "string"},
        "birth_data": {"type": "object", "additionalProperties": True},
        "progression_data": {"type": "object", "additionalProperties": True},
        "calculation_location": {"type": "string"},
        "calculation_location_resolved": {"type": "string"},
        "calculation_location_latitude": {"type": "number"},
        "calculation_location_longitude": {"type": "number"},
        "calculation_location_timezone": {"type": "string"},
        "chart": {"type": "object", "additionalProperties": True},
        "placements": CHART_SUCCESS_SCHEMA["properties"]["placements"],
        "houses": CHART_SUCCESS_SCHEMA["properties"]["houses"],
        "aspects": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
    },
}
PROGRESSED_SOLAR_ARC_ANGLES_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": [
        "status",
        "success",
        "message",
        "verified_progressed_chart",
        "method",
        "solar_arc_value",
        "progressed_asc",
        "progressed_mc",
        "progressed_house_cusps",
        "progressed_planets",
    ],
    "properties": {
        "status": {"type": "string"},
        "success": {"type": "boolean"},
        "message": {"type": "string"},
        "verified_progressed_chart": {"type": "boolean"},
        "method": {"type": "string"},
        "progression_method": {"type": "string"},
        "angles_method": {"type": "string"},
        "solar_arc_value": {"type": "object", "additionalProperties": True},
        "natal_sun": {"type": "object", "additionalProperties": True},
        "progressed_sun": {"type": "object", "additionalProperties": True},
        "progressed_asc": {"type": "object", "additionalProperties": True},
        "progressed_mc": {"type": "object", "additionalProperties": True},
        "progressed_house_cusps": CHART_SUCCESS_SCHEMA["properties"]["houses"],
        "progressed_planets": CHART_SUCCESS_SCHEMA["properties"]["placements"],
        "placements": CHART_SUCCESS_SCHEMA["properties"]["placements"],
        "houses": CHART_SUCCESS_SCHEMA["properties"]["houses"],
        "birth_data": {"type": "object", "additionalProperties": True},
        "progression_data": {"type": "object", "additionalProperties": True},
        "target_location": {"type": "string"},
        "target_location_resolved": {"type": "string"},
        "target_location_latitude": {"type": "number"},
        "target_location_longitude": {"type": "number"},
        "target_location_timezone": {"type": "string"},
        "calculation_location": {"type": "string"},
        "calculation_location_resolved": {"type": "string"},
        "calculation_location_latitude": {"type": "number"},
        "calculation_location_longitude": {"type": "number"},
        "calculation_location_timezone": {"type": "string"},
        "chart": {"type": "object", "additionalProperties": True},
        "aspects": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
    },
}


COMMON_PLACE_CACHE: dict[str, PlaceResolution] = {
    "quezon city, philippines": PlaceResolution(
        query="Quezon City, Philippines",
        birthplace_resolved="Quezon City, Eastern Manila District, Metropolitan Manila, Philippines",
        latitude=14.6760,
        longitude=121.0437,
        timezone_name="Asia/Manila",
    ),
    "manila, philippines": PlaceResolution(
        query="Manila, Philippines",
        birthplace_resolved="Manila, Capital District, Metro Manila, Philippines",
        latitude=14.5995,
        longitude=120.9842,
        timezone_name="Asia/Manila",
    ),
    "calabanga, camarines sur, philippines": PlaceResolution(
        query="Calabanga, Camarines Sur, Philippines",
        birthplace_resolved="Calabanga, Camarines Sur, Bicol Region, 4405, Philippines",
        latitude=13.7085450,
        longitude=123.2157561,
        timezone_name="Asia/Manila",
    ),
    "new york, usa": PlaceResolution(
        query="New York, USA",
        birthplace_resolved="New York, United States",
        latitude=40.7128,
        longitude=-74.0060,
        timezone_name="America/New_York",
    ),
    "new york, united states": PlaceResolution(
        query="New York, United States",
        birthplace_resolved="New York, United States",
        latitude=40.7128,
        longitude=-74.0060,
        timezone_name="America/New_York",
    ),
    "london, united kingdom": PlaceResolution(
        query="London, United Kingdom",
        birthplace_resolved="London, Greater London, England, United Kingdom",
        latitude=51.5074,
        longitude=-0.1278,
        timezone_name="Europe/London",
    ),
    "paris, france": PlaceResolution(
        query="Paris, France",
        birthplace_resolved="Paris, Ile-de-France, France",
        latitude=48.8566,
        longitude=2.3522,
        timezone_name="Europe/Paris",
    ),
    "sydney, australia": PlaceResolution(
        query="Sydney, Australia",
        birthplace_resolved="Sydney, New South Wales, Australia",
        latitude=-33.8688,
        longitude=151.2093,
        timezone_name="Australia/Sydney",
    ),
    "dubai, uae": PlaceResolution(
        query="Dubai, UAE",
        birthplace_resolved="Dubai, United Arab Emirates",
        latitude=25.2048,
        longitude=55.2708,
        timezone_name="Asia/Dubai",
    ),
    "dubai, united arab emirates": PlaceResolution(
        query="Dubai, United Arab Emirates",
        birthplace_resolved="Dubai, United Arab Emirates",
        latitude=25.2048,
        longitude=55.2708,
        timezone_name="Asia/Dubai",
    ),
    "tokyo, japan": PlaceResolution(
        query="Tokyo, Japan",
        birthplace_resolved="Tokyo, Japan",
        latitude=35.6762,
        longitude=139.6503,
        timezone_name="Asia/Tokyo",
    ),
}


def load_persistent_place_cache() -> dict[str, PlaceResolution]:
    if not PLACE_CACHE_FILE.is_file():
        return {}

    try:
        raw_cache = json.loads(PLACE_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        logger.warning("place cache load failed path=%s error=%s", PLACE_CACHE_FILE, error)
        return {}

    if not isinstance(raw_cache, dict):
        logger.warning("place cache ignored path=%s reason=not_object", PLACE_CACHE_FILE)
        return {}

    cache: dict[str, PlaceResolution] = {}
    for cache_key, value in raw_cache.items():
        if not isinstance(cache_key, str) or not isinstance(value, dict):
            continue
        try:
            cache[cache_key] = PlaceResolution(**value)
        except (TypeError, ValueError) as error:
            logger.warning("place cache entry ignored key=%s error=%s", cache_key, error)

    logger.info("place cache loaded path=%s entries=%s", PLACE_CACHE_FILE, len(cache))
    return cache


def persist_place_cache() -> None:
    try:
        serializable_cache = {
            cache_key: place.model_dump()
            for cache_key, place in sorted(PLACE_CACHE.items())
        }
        temp_path = PLACE_CACHE_FILE.with_name(f"{PLACE_CACHE_FILE.name}.tmp")
        temp_path.write_text(json.dumps(serializable_cache, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temp_path, PLACE_CACHE_FILE)
        logger.info("place cache saved path=%s entries=%s", PLACE_CACHE_FILE, len(serializable_cache))
    except OSError as error:
        logger.warning("place cache save failed path=%s error=%s", PLACE_CACHE_FILE, error)


SIGNS = (
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
)

PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "North Node": swe.TRUE_NODE,
    "Lilith": swe.MEAN_APOG,
    "Chiron": swe.CHIRON,
}

TEST_BIRTHPLACES = (
    "Quezon City, Philippines",
    "Manila, Philippines",
    "New York, USA",
    "London, United Kingdom",
    "Paris, France",
    "Sydney, Australia",
    "Dubai, UAE",
    "Tokyo, Japan",
)

COUNTRY_CODE_ALIASES = {
    "australia": "AU",
    "canada": "CA",
    "france": "FR",
    "japan": "JP",
    "philippines": "PH",
    "south africa": "ZA",
    "uae": "AE",
    "united arab emirates": "AE",
    "uk": "GB",
    "united kingdom": "GB",
    "us": "US",
    "usa": "US",
    "united states": "US",
}


def normalize_place(value: str) -> str:
    return " ".join(value.casefold().replace(",", " , ").split()).replace(" ,", ",")


def compact_place_key(value: str) -> str:
    return " ".join(value.casefold().replace(",", " ").split())


def cache_keys_for_place(value: str) -> list[str]:
    keys = [normalize_place(value), compact_place_key(value)]
    return list(dict.fromkeys(key for key in keys if key))


def birthplace_search_attempts(birthplace: str) -> list[tuple[str, str]]:
    stripped = birthplace.strip()
    if "," in stripped:
        return [(stripped.split(",", maxsplit=1)[0].strip(), stripped)]

    attempts: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_attempt(search_name: str, selector: str) -> None:
        candidate = (search_name.strip(), selector.strip())
        if candidate[0] and candidate not in seen:
            attempts.append(candidate)
            seen.add(candidate)

    compact = compact_place_key(stripped)
    for country_name in sorted(COUNTRY_CODE_ALIASES, key=len, reverse=True):
        suffix = f" {country_name}"
        if compact.endswith(suffix):
            city = compact[: -len(suffix)].strip()
            if city:
                add_attempt(city, f"{city}, {country_name}")

    words = compact.split()
    for split_index in range(len(words) - 1, 0, -1):
        city = " ".join(words[:split_index])
        qualifier = " ".join(words[split_index:])
        add_attempt(city, f"{city}, {qualifier}")

    add_attempt(stripped, stripped)
    return attempts


def add_place_cache_aliases(cache: dict[str, PlaceResolution]) -> None:
    for cache_key, resolution in list(cache.items()):
        for alias in cache_keys_for_place(cache_key):
            cache.setdefault(alias, resolution)
        for alias in cache_keys_for_place(resolution.query):
            cache.setdefault(alias, resolution)


PLACE_CACHE: dict[str, PlaceResolution] = dict(COMMON_PLACE_CACHE)
PLACE_CACHE.update(load_persistent_place_cache())
add_place_cache_aliases(PLACE_CACHE)


def zodiac_sign(absolute_degree: float) -> str:
    return SIGNS[int((absolute_degree % 360) // 30)]


def zodiac_degree(absolute_degree: float) -> float:
    return absolute_degree % 30


def zodiac_position(absolute_degree: float) -> dict[str, object]:
    normalized = absolute_degree % 360.0
    sign = zodiac_sign(normalized)
    degree_float = zodiac_degree(normalized)
    degree = int(degree_float)
    minute_float = (degree_float - degree) * 60.0
    minute = int(minute_float)
    second = round((minute_float - minute) * 60.0, 2)

    if second >= 60.0:
        second = 0.0
        minute += 1
    if minute >= 60:
        minute = 0
        degree += 1
    if degree >= 30:
        degree = 0
        sign = zodiac_sign(normalized + 30.0)

    return {
        "sign": sign,
        "degree": degree,
        "minute": minute,
        "second": second,
        "decimal_degree": degree_float,
        "absolute_degree": normalized,
        "formatted": f"{sign} {degree}\u00b0{minute:02d}'{second:05.2f}\"",
    }


def arc_position(arc_degrees: float) -> dict[str, object]:
    normalized = arc_degrees % 360.0
    degree = int(normalized)
    minute_float = (normalized - degree) * 60.0
    minute = int(minute_float)
    second = round((minute_float - minute) * 60.0, 2)

    if second >= 60.0:
        second = 0.0
        minute += 1
    if minute >= 60:
        minute = 0
        degree += 1

    return {
        "degree": degree,
        "minute": minute,
        "second": second,
        "decimal_degrees": normalized,
        "formatted": f"{degree}\u00b0{minute:02d}'{second:05.2f}\"",
    }


def directed_house_cusps(cusp_values: list[float], solar_arc: float) -> list[HouseCuspResponse]:
    return [
        HouseCuspResponse(
            house=index,
            sign=zodiac_sign(cusp + solar_arc),
            degree=zodiac_degree(cusp + solar_arc),
            absolute_degree=(cusp + solar_arc) % 360.0,
        )
        for index, cusp in enumerate(cusp_values, start=1)
    ]


def placement_payload(placement: PlacementResponse) -> dict:
    return {
        "body": placement.body,
        "sign": placement.sign,
        "degree": round(placement.degree, 2),
        "position": zodiac_position(placement.absolute_degree),
        "absolute_degree": placement.absolute_degree % 360.0,
        "house": placement.house,
    }


def house_payload(house: HouseCuspResponse) -> dict:
    return {
        "house": house.house,
        "sign": house.sign,
        "degree": round(house.degree, 2),
        "position": zodiac_position(house.absolute_degree),
        "absolute_degree": house.absolute_degree % 360.0,
    }


def signed_longitude_delta(longitude: float, target_longitude: float) -> float:
    return ((longitude - target_longitude + 180.0) % 360.0) - 180.0


def sun_longitude_at_jd(jd: float) -> float:
    try:
        position, _flags = swe.calc_ut(jd, swe.SUN)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not calculate Sun longitude: {error}") from error
    return float(position[0] % 360.0)


def julian_day_to_utc_datetime(jd: float) -> datetime:
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(days=jd - JULIAN_DAY_UNIX_EPOCH)


def datetime_to_julian_day_utc(value: datetime) -> float:
    utc_value = value.astimezone(timezone.utc)
    hour = (
        utc_value.hour
        + (utc_value.minute / 60.0)
        + (utc_value.second / 3600.0)
        + (utc_value.microsecond / 3_600_000_000.0)
    )
    return swe.julday(utc_value.year, utc_value.month, utc_value.day, hour)


def local_datetime_to_utc(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    timezone_name: str,
    label: str,
) -> datetime:
    try:
        local_value = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(timezone_name))
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise HTTPException(status_code=400, detail=f"Invalid {label} datetime or timezone: {error}") from error
    return local_value.astimezone(timezone.utc)


def secondary_progressed_utc(
    birth_utc: datetime,
    target_utc: datetime,
) -> tuple[datetime, float, float]:
    elapsed_days = (target_utc - birth_utc).total_seconds() / 86400.0
    if elapsed_days < 0:
        raise HTTPException(status_code=400, detail="Progression date must be after the birth date.")

    age_years = elapsed_days / TROPICAL_YEAR_DAYS
    progressed_days_after_birth = age_years
    progressed_utc = birth_utc + timedelta(days=progressed_days_after_birth)
    return progressed_utc, progressed_days_after_birth, age_years


def return_search_center_utc(return_year: int, birth_month: int, birth_day: int) -> datetime:
    try:
        return datetime(return_year, birth_month, birth_day, tzinfo=timezone.utc)
    except ValueError as error:
        if birth_month == 2 and birth_day == 29:
            return datetime(return_year, 2, 28, tzinfo=timezone.utc)
        raise HTTPException(status_code=400, detail=f"Invalid return date window: {error}") from error


def bisection_solar_return_jd(low_jd: float, high_jd: float, natal_sun_longitude: float) -> float:
    low_delta = signed_longitude_delta(sun_longitude_at_jd(low_jd), natal_sun_longitude)
    high_delta = signed_longitude_delta(sun_longitude_at_jd(high_jd), natal_sun_longitude)
    solve_tolerance = SOLAR_RETURN_SOLVE_TOLERANCE_ARCSECONDS / 3600.0

    if abs(low_delta) <= solve_tolerance:
        return low_jd
    if abs(high_delta) <= solve_tolerance:
        return high_jd
    if low_delta > 0 or high_delta < 0:
        raise HTTPException(status_code=500, detail="Solar return bracket does not contain a forward Sun crossing.")

    for _ in range(SOLAR_RETURN_MAX_ITERATIONS):
        mid_jd = (low_jd + high_jd) / 2.0
        mid_delta = signed_longitude_delta(sun_longitude_at_jd(mid_jd), natal_sun_longitude)
        if abs(mid_delta) <= solve_tolerance:
            return mid_jd
        if mid_delta < 0:
            low_jd = mid_jd
        else:
            high_jd = mid_jd

    return (low_jd + high_jd) / 2.0


def find_exact_solar_return_jd(natal_sun_longitude: float, return_year: int, birth_month: int, birth_day: int) -> float:
    center = return_search_center_utc(return_year, birth_month, birth_day)
    search_windows = (
        (center - timedelta(days=5), center + timedelta(days=5)),
        (datetime(return_year, 1, 1, tzinfo=timezone.utc), datetime(return_year + 1, 1, 1, tzinfo=timezone.utc)),
    )

    for start_dt, end_dt in search_windows:
        start_jd = datetime_to_julian_day_utc(start_dt)
        end_jd = datetime_to_julian_day_utc(end_dt)
        previous_jd = start_jd
        previous_delta = signed_longitude_delta(sun_longitude_at_jd(previous_jd), natal_sun_longitude)

        jd = start_jd + SOLAR_RETURN_SEARCH_STEP_DAYS
        while jd <= end_jd:
            delta = signed_longitude_delta(sun_longitude_at_jd(jd), natal_sun_longitude)
            if previous_delta <= 0 <= delta and abs(delta - previous_delta) < 5.0:
                return bisection_solar_return_jd(previous_jd, jd, natal_sun_longitude)
            previous_jd = jd
            previous_delta = delta
            jd += SOLAR_RETURN_SEARCH_STEP_DAYS

    raise HTTPException(status_code=500, detail="Could not find exact solar return crossing for return year.")


def house_for_degree(absolute_degree: float, cusps: list[float]) -> int:
    point = absolute_degree % 360
    for index, start in enumerate(cusps):
        end = cusps[(index + 1) % 12]
        adjusted_end = end
        adjusted_point = point
        if adjusted_end <= start:
            adjusted_end += 360
        if adjusted_point < start:
            adjusted_point += 360
        if start <= adjusted_point < adjusted_end:
            return index + 1
    return 12


def fetch_json(url: str, timeout: int, log_url: str | None = None) -> object:
    request = UrlRequest(url, headers={"User-Agent": USER_AGENT})
    last_error = None

    for attempt in range(LOOKUP_ATTEMPTS):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            logger.warning("lookup failed attempt=%s url=%s error=%s", attempt + 1, log_url or url, error)
            if attempt < LOOKUP_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_SECONDS)

    raise HTTPException(status_code=502, detail=f"External lookup unavailable: {last_error}")


def location_match_text(match: dict) -> str:
    return normalize_place(
        " ".join(str(match.get(field, "")) for field in ("name", "admin1", "admin2", "admin3", "admin4", "country", "country_code"))
    )


def location_label(match: dict, fallback: str) -> str:
    labels = []
    for field in ("name", "admin1", "country"):
        value = str(match.get(field, "")).strip()
        if value and value not in labels:
            labels.append(value)
    return ", ".join(labels) or fallback


def select_location_match(birthplace: str, matches: list[dict]) -> dict:
    parts = [part.strip() for part in birthplace.split(",") if part.strip()]
    qualifiers = [normalize_place(part) for part in parts[1:]]
    candidates = matches

    if qualifiers:
        country_code = COUNTRY_CODE_ALIASES.get(qualifiers[-1])
        country_candidates = [
            match
            for match in matches
            if (
                country_code and str(match.get("country_code", "")).upper() == country_code
            ) or normalize_place(str(match.get("country", ""))) == qualifiers[-1]
        ]
        if country_candidates:
            candidates = country_candidates
        elif country_code:
            raise HTTPException(status_code=400, detail=f"Could not resolve birthplace in specified country: {birthplace}")

    def score(match: dict) -> tuple[int, int]:
        searchable = location_match_text(match)
        qualifier_score = sum(1 for qualifier in qualifiers if qualifier in searchable)
        return qualifier_score, int(match.get("population", 0) or 0)

    return max(candidates, key=score)


def geocode_birthplace(birthplace: str) -> PlaceResolution:
    try:
        last_error = f"Could not geocode birthplace: {birthplace}"
        for location_name, selection_birthplace in birthplace_search_attempts(birthplace):
            parameters = {"name": location_name, "count": 10, "language": "en", "format": "json"}
            if OPEN_METEO_API_KEY:
                parameters["apikey"] = OPEN_METEO_API_KEY
            query = urlencode(parameters)

            logger.info(
                "geocode start query=%s search_name=%s selector=%s provider=open-meteo endpoint=%s",
                birthplace,
                location_name,
                selection_birthplace,
                OPEN_METEO_GEOCODE_URL,
            )
            geocode_data = fetch_json(
                f"{OPEN_METEO_GEOCODE_URL}?{query}",
                GEOCODE_TIMEOUT_SECONDS,
                log_url=OPEN_METEO_GEOCODE_URL,
            )
            matches = geocode_data.get("results") if isinstance(geocode_data, dict) else None
            match_count = len(matches) if isinstance(matches, list) else 0
            logger.info(
                "geocode response query=%s search_name=%s provider=open-meteo matches=%s",
                birthplace,
                location_name,
                match_count,
            )

            if not isinstance(matches, list) or not matches:
                continue

            valid_matches = [candidate for candidate in matches if isinstance(candidate, dict)]
            if not valid_matches:
                raise HTTPException(status_code=502, detail="Malformed geocoder response: no valid location records.")

            try:
                match = select_location_match(selection_birthplace, valid_matches)
            except HTTPException as error:
                last_error = str(error.detail)
                continue

            resolution = PlaceResolution(
                query=birthplace,
                birthplace_resolved=location_label(match, birthplace),
                latitude=float(match["latitude"]),
                longitude=float(match["longitude"]),
                timezone_name=str(match["timezone"]),
            )
            logger.info(
                "geocode success query=%s resolved=%s latitude=%s longitude=%s timezone=%s",
                birthplace,
                resolution.birthplace_resolved,
                resolution.latitude,
                resolution.longitude,
                resolution.timezone_name,
            )
            return resolution

        raise HTTPException(status_code=400, detail=last_error)
    except HTTPException:
        logger.warning("geocode failed query=%s", birthplace)
        raise
    except (KeyError, TypeError, ValueError) as error:
        logger.warning("geocode malformed query=%s error=%s", birthplace, error)
        raise HTTPException(status_code=502, detail=f"Malformed geocoder response: {error}") from error
    except Exception as error:
        logger.exception("geocode unexpected failure query=%s", birthplace)
        raise HTTPException(status_code=502, detail=f"Geocoding failed unexpectedly: {error}") from error


def resolve_birthplace(birthplace: str) -> PlaceResolution:
    cache_keys = cache_keys_for_place(birthplace)
    for cache_key in cache_keys:
        cached = PLACE_CACHE.get(cache_key)
        if cached:
            logger.info("birthplace cache hit query=%s key=%s resolved=%s", birthplace, cache_key, cached.birthplace_resolved)
            return cached

    logger.info("birthplace cache miss query=%s", birthplace)
    resolution = geocode_birthplace(birthplace)
    for cache_key in cache_keys_for_place(birthplace):
        PLACE_CACHE[cache_key] = resolution
    for cache_key in cache_keys_for_place(resolution.query):
        PLACE_CACHE[cache_key] = resolution
    persist_place_cache()
    return resolution


def timezone_offset_hours(year: int, month: int, day: int, hour: int, minute: int, timezone_name: str) -> float:
    try:
        birth_datetime = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(timezone_name))
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise HTTPException(status_code=400, detail=f"Invalid birth datetime or timezone: {error}") from error

    utc_offset = birth_datetime.utcoffset()
    if utc_offset is None:
        raise HTTPException(status_code=400, detail=f"Could not determine UTC offset for timezone: {timezone_name}")

    return utc_offset.total_seconds() / 3600


def calculate_julian_day(year: int, month: int, day: int, hour: int, minute: int, timezone: float) -> float:
    try:
        datetime(year, month, day, hour, minute)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    utc_hour = hour - timezone + (minute / 60)
    return swe.julday(year, month, day, utc_hour)


def calculate_planets(jd: float) -> PlanetsResponse:
    results = {}
    for name, planet in PLANETS.items():
        try:
            position, _flags = swe.calc_ut(jd, planet)
            results[name] = position[0]
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"Could not calculate {name}: {error}") from error

    return PlanetsResponse(**results)


def calculate_houses(jd: float, latitude: float, longitude: float) -> tuple[list[HouseCuspResponse], list[float], float, float]:
    try:
        cusps, ascmc = swe.houses(jd, latitude, longitude, b'P')
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not calculate Placidus houses: {error}") from error

    cusp_values = list(cusps)
    house_cusps = [
        HouseCuspResponse(
            house=index,
            sign=zodiac_sign(cusp),
            degree=zodiac_degree(cusp),
            absolute_degree=cusp,
        )
        for index, cusp in enumerate(cusp_values, start=1)
    ]
    return house_cusps, cusp_values, ascmc[0], ascmc[1]


def placement_summary(placements: list[PlacementResponse]) -> str:
    formatted = "; ".join(
        f"{placement.body}: {placement.sign} {placement.degree:.2f} degrees, house {placement.house}"
        for placement in placements
    )
    return f"SUCCESS | Chart calculated successfully | body_count={len(placements)} | {formatted}"


def chart_summary(placements: list[PlacementResponse]) -> str:
    formatted = "\n".join(
        f"{placement.body}: {placement.sign} {placement.degree:.2f} degrees, house {placement.house}"
        for placement in placements
    )
    return f"VERIFIED_ASTROMEG_CHART_DATA\n{formatted}"


def build_chart_response_from_jd(
    jd: float,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    timezone_name: str,
    resolved_place: str,
    birthplace: str,
) -> ChartResponse:
    planets = calculate_planets(jd)
    houses, cusp_values, ascendant, midheaven = calculate_houses(jd, latitude, longitude)
    planet_values = planets.model_dump(by_alias=True)
    placements = [
        PlacementResponse(
            body=body,
            sign=zodiac_sign(absolute_degree),
            degree=zodiac_degree(absolute_degree),
            absolute_degree=absolute_degree,
            house=house_for_degree(absolute_degree, cusp_values),
        )
        for body, absolute_degree in planet_values.items()
    ]
    birth_data = BirthDataResponse(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        birthplace=birthplace,
        resolved_place=resolved_place,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone_name,
        timezone_offset=timezone_offset,
        zodiac=ZODIAC,
        house_system=HOUSE_SYSTEM,
    )
    chart_text = chart_summary(placements)
    placements_text = placement_summary(placements)
    return ChartResponse(
        status="success",
        success=True,
        message="Chart calculated successfully",
        verified_chart_data=True,
        chart=chart_text,
        chart_text=chart_text,
        result=placements_text,
        placements_text=placements_text,
        body_count=len(placements),
        birth_data=birth_data,
        placements=placements,
        houses=houses,
        ascendant=ascendant,
        midheaven=midheaven,
        aspects=[],
    )


def build_chart_response(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    latitude: float,
    longitude: float,
    timezone_offset: float,
    timezone_name: str,
    resolved_place: str,
    birthplace: str,
) -> ChartResponse:
    jd = calculate_julian_day(year, month, day, hour, minute, timezone_offset)
    return build_chart_response_from_jd(
        jd=jd,
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        latitude=latitude,
        longitude=longitude,
        timezone_offset=timezone_offset,
        timezone_name=timezone_name,
        resolved_place=resolved_place,
        birthplace=birthplace,
    )


def action_chart_payload(chart: ChartResponse) -> dict:
    return {
        "status": "success",
        "success": True,
        "message": "Chart calculated successfully",
        "verified_chart_data": True,
        "chart": chart.chart,
        "chart_text": chart.chart_text,
        "result": chart.result,
        "placements_text": chart.placements_text,
        "body_count": chart.body_count,
        "birth_data": {
            "year": chart.birth_data.year,
            "month": chart.birth_data.month,
            "day": chart.birth_data.day,
            "hour": chart.birth_data.hour,
            "minute": chart.birth_data.minute,
            "birthplace": chart.birth_data.birthplace,
            "resolved_place": chart.birth_data.resolved_place,
            "latitude": chart.birth_data.latitude,
            "longitude": chart.birth_data.longitude,
            "timezone": chart.birth_data.timezone,
            "timezone_offset": chart.birth_data.timezone_offset,
            "zodiac": chart.birth_data.zodiac,
            "house_system": chart.birth_data.house_system,
        },
        "placements": [
            {
                "body": placement.body,
                "sign": placement.sign,
                "degree": round(placement.degree, 2),
                "position": zodiac_position(placement.absolute_degree),
                "house": placement.house,
            }
            for placement in chart.placements
        ],
        "houses": [
            {
                "house": house.house,
                "sign": house.sign,
                "degree": round(house.degree, 2),
                "position": zodiac_position(house.absolute_degree),
            }
            for house in chart.houses
        ],
        "ascendant": round(chart.ascendant % 360, 2),
        "ascendant_position": zodiac_position(chart.ascendant),
        "midheaven": round(chart.midheaven % 360, 2),
        "midheaven_position": zodiac_position(chart.midheaven),
        "aspects": [],
    }


def solar_return_payload(
    request: SolarReturnRequest,
    natal_place: PlaceResolution,
    return_place: PlaceResolution,
    exact_return_jd: float,
    natal_sun_longitude: float,
    return_sun_longitude: float,
    return_chart: ChartResponse,
) -> dict:
    exact_return_utc = julian_day_to_utc_datetime(exact_return_jd)
    exact_return_local = exact_return_utc.astimezone(ZoneInfo(return_place.timezone_name))
    longitude_delta_arcseconds = abs(signed_longitude_delta(return_sun_longitude, natal_sun_longitude)) * 3600.0
    verified_solar_return = longitude_delta_arcseconds <= SOLAR_RETURN_TOLERANCE_ARCSECONDS
    chart_payload = action_chart_payload(return_chart)

    if not verified_solar_return:
        return {
            "status": "error",
            "success": False,
            "verified_solar_return": False,
            "message": "Exact solar return could not be verified within 1 arcsecond.",
            "natal_sun_longitude": natal_sun_longitude,
            "return_sun_longitude": return_sun_longitude,
            "longitude_delta_arcseconds": longitude_delta_arcseconds,
        }

    return {
        "status": "success",
        "success": True,
        "message": "Exact solar return calculated successfully",
        "verified_solar_return": True,
        "natal_sun_longitude": natal_sun_longitude,
        "return_sun_longitude": return_sun_longitude,
        "longitude_delta_arcseconds": longitude_delta_arcseconds,
        "exact_return_utc": exact_return_utc.isoformat().replace("+00:00", "Z"),
        "exact_return_local": exact_return_local.isoformat(),
        "birthplace": request.birthplace,
        "birthplace_resolved": natal_place.birthplace_resolved,
        "return_location": request.return_location,
        "return_location_resolved": return_place.birthplace_resolved,
        "return_location_latitude": return_place.latitude,
        "return_location_longitude": return_place.longitude,
        "return_location_timezone": return_place.timezone_name,
        "chart": {
            "summary": return_chart.chart,
            "chart_text": return_chart.chart_text,
            "placements_text": return_chart.placements_text,
            "body_count": return_chart.body_count,
            "ascendant": chart_payload["ascendant"],
            "ascendant_position": chart_payload["ascendant_position"],
            "midheaven": chart_payload["midheaven"],
            "midheaven_position": chart_payload["midheaven_position"],
            "timezone": return_place.timezone_name,
        },
        "birth_data": chart_payload["birth_data"],
        "placements": chart_payload["placements"],
        "houses": chart_payload["houses"],
        "aspects": chart_payload["aspects"],
    }


def progressed_chart_payload(
    request: ProgressedChartRequest,
    natal_place: PlaceResolution,
    calculation_place: PlaceResolution,
    birth_utc: datetime,
    target_utc: datetime,
    target_local: datetime,
    progressed_utc: datetime,
    progressed_days_after_birth: float,
    age_years: float,
    progressed_chart: ChartResponse,
) -> dict:
    progressed_local = progressed_utc.astimezone(ZoneInfo(calculation_place.timezone_name))
    chart_payload = action_chart_payload(progressed_chart)

    return {
        "status": "success",
        "success": True,
        "message": "Secondary progressed chart calculated successfully",
        "verified_progressed_chart": True,
        "progression_method": "Secondary progressions: one day after birth equals one year of life.",
        "angles_method": "Progressed Placidus angles calculated at the progressed Julian day using the calculation location.",
        "birth_data": {
            "year": request.birth_year,
            "month": request.birth_month,
            "day": request.birth_day,
            "hour": request.birth_hour,
            "minute": request.birth_minute,
            "birthplace": request.birthplace,
            "resolved_place": natal_place.birthplace_resolved,
            "latitude": natal_place.latitude,
            "longitude": natal_place.longitude,
            "timezone": natal_place.timezone_name,
            "birth_utc": birth_utc.isoformat().replace("+00:00", "Z"),
            "zodiac": ZODIAC,
            "house_system": HOUSE_SYSTEM,
        },
        "progression_data": {
            "target_year": request.progression_year,
            "target_month": request.progression_month,
            "target_day": request.progression_day,
            "target_hour": request.progression_hour,
            "target_minute": request.progression_minute,
            "target_local": target_local.isoformat(),
            "target_utc": target_utc.isoformat().replace("+00:00", "Z"),
            "age_years": age_years,
            "progressed_days_after_birth": progressed_days_after_birth,
            "progressed_utc": progressed_utc.isoformat().replace("+00:00", "Z"),
            "progressed_local": progressed_local.isoformat(),
        },
        "calculation_location": request.progression_location or request.birthplace,
        "calculation_location_resolved": calculation_place.birthplace_resolved,
        "calculation_location_latitude": calculation_place.latitude,
        "calculation_location_longitude": calculation_place.longitude,
        "calculation_location_timezone": calculation_place.timezone_name,
        "chart": {
            "summary": progressed_chart.chart,
            "chart_text": progressed_chart.chart_text,
            "placements_text": progressed_chart.placements_text,
            "body_count": progressed_chart.body_count,
            "ascendant": chart_payload["ascendant"],
            "ascendant_position": chart_payload["ascendant_position"],
            "midheaven": chart_payload["midheaven"],
            "midheaven_position": chart_payload["midheaven_position"],
            "timezone": calculation_place.timezone_name,
        },
        "placements": chart_payload["placements"],
        "houses": chart_payload["houses"],
        "aspects": chart_payload["aspects"],
    }


def progressed_solar_arc_angles_payload(
    request: ProgressedChartRequest,
    natal_place: PlaceResolution,
    target_place: PlaceResolution,
    birth_utc: datetime,
    target_utc: datetime,
    target_local: datetime,
    progressed_utc: datetime,
    progressed_days_after_birth: float,
    age_years: float,
    natal_sun_longitude: float,
    progressed_sun_longitude: float,
    natal_ascendant: float,
    natal_midheaven: float,
    directed_cusps: list[HouseCuspResponse],
    progressed_planets: list[PlacementResponse],
) -> dict:
    solar_arc = (progressed_sun_longitude - natal_sun_longitude) % 360.0
    progressed_ascendant = (natal_ascendant + solar_arc) % 360.0
    progressed_midheaven = (natal_midheaven + solar_arc) % 360.0
    progressed_local = progressed_utc.astimezone(ZoneInfo(target_place.timezone_name))
    progressed_planets_payload = [placement_payload(placement) for placement in progressed_planets]
    directed_cusps_payload = [house_payload(cusp) for cusp in directed_cusps]
    chart_text = chart_summary(progressed_planets)
    placements_text = placement_summary(progressed_planets)

    return {
        "status": "success",
        "success": True,
        "message": "Secondary progressed chart with Solar Arc in Longitude angles calculated successfully",
        "verified_progressed_chart": True,
        "method": "Secondary Progressions + Solar Arc in Longitude Angles",
        "progression_method": "Secondary progressions: one day after birth equals one year of life.",
        "angles_method": "Solar Arc in Longitude applied to natal ASC, MC, and Placidus house cusps.",
        "solar_arc_value": {
            **arc_position(solar_arc),
            "decimal_degrees": solar_arc,
        },
        "natal_sun": zodiac_position(natal_sun_longitude),
        "progressed_sun": zodiac_position(progressed_sun_longitude),
        "progressed_asc": zodiac_position(progressed_ascendant),
        "progressed_mc": zodiac_position(progressed_midheaven),
        "progressed_house_cusps": directed_cusps_payload,
        "progressed_planets": progressed_planets_payload,
        "birth_data": {
            "year": request.birth_year,
            "month": request.birth_month,
            "day": request.birth_day,
            "hour": request.birth_hour,
            "minute": request.birth_minute,
            "birthplace": request.birthplace,
            "resolved_place": natal_place.birthplace_resolved,
            "latitude": natal_place.latitude,
            "longitude": natal_place.longitude,
            "timezone": natal_place.timezone_name,
            "birth_utc": birth_utc.isoformat().replace("+00:00", "Z"),
            "zodiac": ZODIAC,
            "house_system": HOUSE_SYSTEM,
        },
        "progression_data": {
            "target_year": request.progression_year,
            "target_month": request.progression_month,
            "target_day": request.progression_day,
            "target_hour": request.progression_hour,
            "target_minute": request.progression_minute,
            "target_local": target_local.isoformat(),
            "target_utc": target_utc.isoformat().replace("+00:00", "Z"),
            "age_years": age_years,
            "progressed_days_after_birth": progressed_days_after_birth,
            "progressed_utc": progressed_utc.isoformat().replace("+00:00", "Z"),
            "progressed_local": progressed_local.isoformat(),
        },
        "target_location": request.progression_location or request.birthplace,
        "target_location_resolved": target_place.birthplace_resolved,
        "target_location_latitude": target_place.latitude,
        "target_location_longitude": target_place.longitude,
        "target_location_timezone": target_place.timezone_name,
        "calculation_location": request.birthplace,
        "calculation_location_resolved": natal_place.birthplace_resolved,
        "calculation_location_latitude": natal_place.latitude,
        "calculation_location_longitude": natal_place.longitude,
        "calculation_location_timezone": natal_place.timezone_name,
        "chart": {
            "summary": chart_text,
            "chart_text": chart_text,
            "placements_text": placements_text,
            "body_count": len(progressed_planets),
            "solar_arc_value": arc_position(solar_arc),
            "ascendant": round(progressed_ascendant, 2),
            "ascendant_position": zodiac_position(progressed_ascendant),
            "midheaven": round(progressed_midheaven, 2),
            "midheaven_position": zodiac_position(progressed_midheaven),
            "timezone": natal_place.timezone_name,
        },
        "placements": progressed_planets_payload,
        "houses": directed_cusps_payload,
        "aspects": [],
    }


app = FastAPI(
    title="Astromeg Oracle Swiss Ephemeris API",
    version="1.0.0",
    servers=[{"url": "https://astromeg-oracle-api.onrender.com"}],
    openapi_version="3.1.0",
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=(
            "Action schema for calculating tropical Placidus natal charts with Swiss Ephemeris. "
            "Use /chart only after collecting birth date, birth time, and birthplace. "
            "Every chart request must include the required birthplace query parameter."
        ),
        routes=app.routes,
        openapi_version="3.1.0",
        servers=[{"url": "https://astromeg-oracle-api.onrender.com"}],
    )

    chart_operation = schema["paths"]["/chart"]["get"]
    chart_operation["operationId"] = "calculate_chart"
    chart_operation["summary"] = "Calculate natal chart"
    chart_operation["description"] = (
        "Calculate a tropical natal chart with Placidus houses using Swiss Ephemeris only. "
        "Birthplace is geocoded internally and timezone is resolved automatically. "
        "Always send birthplace exactly as provided by the user; do not call this operation without it."
    )
    chart_operation["parameters"] = [
        {
            "name": "year",
            "in": "query",
            "required": True,
            "schema": {"type": "integer", "example": 1972},
            "description": "Birth year, for example 1972.",
        },
        {
            "name": "month",
            "in": "query",
            "required": True,
            "schema": {"type": "integer", "example": 7},
            "description": "Birth month from 1 to 12.",
        },
        {
            "name": "day",
            "in": "query",
            "required": True,
            "schema": {"type": "integer", "example": 31},
            "description": "Birth day of month.",
        },
        {
            "name": "hour",
            "in": "query",
            "required": True,
            "schema": {"type": "integer", "example": 22},
            "description": "Birth hour in 24-hour local time.",
        },
        {
            "name": "minute",
            "in": "query",
            "required": True,
            "schema": {"type": "integer", "example": 50},
            "description": "Birth minute in local time.",
        },
        {
            "name": "birthplace",
            "in": "query",
            "required": True,
            "schema": {"type": "string", "example": "Quezon City, Philippines"},
            "description": "Required birthplace to resolve, for example Quezon City, Philippines. Never omit this parameter.",
        },
    ]
    chart_operation["responses"] = {
        "200": {
            "description": "Chart calculated successfully, or a readable application-level error was returned.",
            "content": {"application/json": {"schema": CHART_RESPONSE_SCHEMA}},
        },
        "default": {
            "description": "Chart request could not be calculated.",
            "content": {"application/json": {"schema": ERROR_SCHEMA}},
        },
    }
    solar_operation = {
        "summary": "Calculate exact solar return",
        "description": (
            "Calculate an exact Solar Return by solving the precise moment in return_year when the "
            "transiting Sun longitude equals the natal Sun longitude. Do not use /chart for Solar Returns."
        ),
        "operationId": "calculate_solar_return",
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": SOLAR_RETURN_REQUEST_SCHEMA}},
        },
        "responses": {
            "200": {
                "description": "Exact Solar Return result or readable application-level error.",
                "content": {"application/json": {"schema": SOLAR_RETURN_RESPONSE_SCHEMA}},
            },
            "default": {
                "description": "Solar Return request could not be calculated.",
                "content": {"application/json": {"schema": ERROR_SCHEMA}},
            },
        },
    }
    progressed_operation = {
        "summary": "Calculate secondary progressed chart",
        "description": (
            "Calculate a secondary progressed chart using Swiss Ephemeris. "
            "Progressed planets are calculated by the day-for-a-year method, and progressed "
            "Placidus angles are calculated at the progressed Julian day."
        ),
        "operationId": "calculate_progressed_chart",
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": PROGRESSED_CHART_REQUEST_SCHEMA}},
        },
        "responses": {
            "200": {
                "description": "Secondary progressed chart result or readable application-level error.",
                "content": {"application/json": {"schema": PROGRESSED_CHART_RESPONSE_SCHEMA}},
            },
            "default": {
                "description": "Progressed chart request could not be calculated.",
                "content": {"application/json": {"schema": ERROR_SCHEMA}},
            },
        },
    }
    progressed_solar_arc_angles_operation = {
        "summary": "Calculate secondary progressed chart with Solar Arc longitude angles",
        "description": (
            "Calculate secondary progressed planetary positions, then calculate progressed ASC, MC, "
            "and house cusps by applying Solar Arc in Longitude to the natal Placidus angles and cusps. "
            "This endpoint does not use progressed-date angles."
        ),
        "operationId": "calculate_progressed_chart_solar_arc_angles",
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": PROGRESSED_CHART_REQUEST_SCHEMA}},
        },
        "responses": {
            "200": {
                "description": "Secondary progressed chart with Solar Arc longitude angles result or readable application-level error.",
                "content": {"application/json": {"schema": PROGRESSED_SOLAR_ARC_ANGLES_RESPONSE_SCHEMA}},
            },
            "default": {
                "description": "Progressed chart with Solar Arc longitude angles request could not be calculated.",
                "content": {"application/json": {"schema": ERROR_SCHEMA}},
            },
        },
    }

    schema["openapi"] = "3.1.0"
    schema["paths"] = {
        "/chart": {"get": chart_operation},
        "/calculate_solar_return": {"post": solar_operation},
        "/calculate_progressed_chart": {"post": progressed_operation},
        "/calculate_progressed_chart_solar_arc_angles": {"post": progressed_solar_arc_angles_operation},
    }
    schema.pop("components", None)
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


def json_response(content: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=content)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    logger.warning("request error status=%s detail=%s", exc.status_code, exc.detail)
    return json_response(
        content={"status": "error", "success": False, "message": str(exc.detail), "details": "", "http_status": exc.status_code},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    logger.warning("validation error details=%s", exc.errors())
    missing_birthplace = any(
        error.get("type") == "missing" and tuple(error.get("loc", ())) == ("query", "birthplace")
        for error in exc.errors()
    )
    if missing_birthplace:
        return json_response(
            content={
                "status": "error",
                "success": False,
                "message": "Birthplace is required to calculate a verified chart. Retry this request with birthplace included.",
                "details": "Missing required query parameter: birthplace.",
                "http_status": 422,
            },
        )
    return json_response(
        content={
            "status": "error",
            "success": False,
            "message": "Invalid request parameters.",
            "details": str(exc.errors()),
            "http_status": 422,
        },
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(_request: Request, exc: Exception):
    logger.exception("unexpected error")
    return json_response(
        content={"status": "error", "success": False, "message": "Internal server error.", "details": str(exc), "http_status": 500},
    )


@app.get("/")
def home():
    return {"status": "Astromeg Oracle API Running"}


@app.get("/robots.txt", include_in_schema=False)
def robots_txt():
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(content=b"", media_type="image/x-icon", status_code=200)


@app.get("/privacy-policy", include_in_schema=False)
def privacy_policy():
    return HTMLResponse(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Astromeg Oracle API Privacy Policy</title>
</head>
<body>
  <main>
    <h1>Astromeg Oracle API Privacy Policy</h1>
    <p>Effective date: May 27, 2026</p>
    <p>
      The Astromeg Oracle chart action processes birth date, birth time, and
      birthplace supplied by the user to calculate an astrology chart.
    </p>
    <h2>How data is used</h2>
    <p>
      Birth data is used only to resolve the location and timezone and to
      calculate chart placements using Swiss Ephemeris.
    </p>
    <h2>Location resolution</h2>
    <p>
      When a birthplace is not already available in the service cache, the
      birthplace may be sent to the Open-Meteo geocoding service to retrieve
      geographic coordinates and a timezone.
    </p>
    <h2>Storage and logging</h2>
    <p>
      Successful location resolutions may be held in temporary application
      memory to improve response speed. Hosting infrastructure may record
      standard request logs for reliability and security. Astromeg does not
      sell birth data submitted to the chart action.
    </p>
    <h2>Contact</h2>
    <p>
      For privacy questions or requests, contact Astromeg through
      <a href="https://www.astromeg.me/contact">www.astromeg.me/contact</a>.
    </p>
    <p>
      General Astromeg privacy information is available at
      <a href="https://www.astromeg.me/privacy-policy">www.astromeg.me/privacy-policy</a>.
    </p>
  </main>
</body>
</html>
"""
    )


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        engine="Swiss Ephemeris",
        zodiac=ZODIAC,
        houses=HOUSE_SYSTEM,
        ephe_path=str(EPHE_PATH),
        ephe_files={filename: (EPHE_PATH / filename).is_file() for filename in EPHE_FILES},
        cache_entries=len(PLACE_CACHE),
    )


@app.get("/ephe-status")
def ephe_status():
    return {
        "cwd": os.getcwd(),
        "base_dir": str(BASE_DIR),
        "ephe_path": str(EPHE_PATH),
        "se_ephe_path": os.environ.get("SE_EPHE_PATH"),
        "files": {filename: (EPHE_PATH / filename).is_file() for filename in EPHE_FILES},
    }


@app.get(
    "/chart",
    operation_id="calculate_chart",
    description=(
        "Calculate a tropical natal chart with Placidus houses using Swiss Ephemeris. "
        "Required query parameters are year, month, day, hour, minute, and birthplace."
    ),
    responses={
        200: {
            "description": "Chart calculated successfully, or a readable application-level error was returned.",
            "content": {"application/json": {"schema": CHART_RESPONSE_SCHEMA}},
        },
        400: {"description": "Invalid birth data or unresolved birthplace.", "content": {"application/json": {"schema": ERROR_SCHEMA}}},
        422: {"description": "Missing or invalid query parameter.", "content": {"application/json": {"schema": ERROR_SCHEMA}}},
        500: {"description": "Unexpected calculation failure.", "content": {"application/json": {"schema": ERROR_SCHEMA}}},
        502: {"description": "External lookup unavailable.", "content": {"application/json": {"schema": ERROR_SCHEMA}}},
    },
)
def calculate_chart(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    birthplace: Annotated[
        Optional[str],
        Query(description="Birthplace to geocode, for example: Quezon City, Philippines."),
    ] = None,
):
    if not birthplace:
        return json_response(
            {
                "status": "error",
                "success": False,
                "message": "birthplace is required",
                "details": "Missing required query parameter: birthplace.",
                "http_status": 200,
            }
        )

    try:
        logger.info("chart birthplace resolution start query=%s", birthplace)
        resolved = resolve_birthplace(birthplace)
        logger.info(
            "chart birthplace resolution success query=%s resolved=%s",
            birthplace,
            resolved.birthplace_resolved,
        )
    except HTTPException as error:
        logger.warning("chart birthplace resolution failed query=%s detail=%s", birthplace, error.detail)
        return json_response(
            {
                "status": "error",
                "success": False,
                "message": "Birthplace lookup failed.",
                "details": str(error.detail),
                "http_status": error.status_code,
            }
        )
    except Exception as error:
        logger.exception("chart birthplace resolution unexpected failure query=%s", birthplace)
        return json_response(
            {
                "status": "error",
                "success": False,
                "message": "Birthplace lookup failed.",
                "details": str(error),
                "http_status": 502,
            }
        )

    timezone_offset = timezone_offset_hours(year, month, day, hour, minute, resolved.timezone_name)

    chart = build_chart_response(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        latitude=resolved.latitude,
        longitude=resolved.longitude,
        timezone_offset=timezone_offset,
        timezone_name=resolved.timezone_name,
        resolved_place=resolved.birthplace_resolved,
        birthplace=birthplace,
    )
    return json_response(action_chart_payload(chart))


@app.post(
    "/calculate_solar_return",
    operation_id="calculate_solar_return",
    description=(
        "Calculate an exact Solar Return. This endpoint first calculates the natal Sun longitude, "
        "then solves for the exact return-year moment when the transiting Sun equals that full-precision longitude."
    ),
    responses={
        200: {"description": "Exact solar return calculation result.", "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}}},
    },
)
def calculate_solar_return(request: SolarReturnRequest):
    logger.info(
        "solar return start birthplace=%s return_location=%s return_year=%s",
        request.birthplace,
        request.return_location,
        request.return_year,
    )
    natal_place = resolve_birthplace(request.birthplace)
    return_place = resolve_birthplace(request.return_location)

    natal_timezone_offset = timezone_offset_hours(
        request.birth_year,
        request.birth_month,
        request.birth_day,
        request.birth_hour,
        request.birth_minute,
        natal_place.timezone_name,
    )
    natal_jd = calculate_julian_day(
        request.birth_year,
        request.birth_month,
        request.birth_day,
        request.birth_hour,
        request.birth_minute,
        natal_timezone_offset,
    )
    natal_sun_longitude = sun_longitude_at_jd(natal_jd)
    exact_return_jd = find_exact_solar_return_jd(
        natal_sun_longitude,
        request.return_year,
        request.birth_month,
        request.birth_day,
    )
    return_sun_longitude = sun_longitude_at_jd(exact_return_jd)
    exact_return_utc = julian_day_to_utc_datetime(exact_return_jd)
    exact_return_local = exact_return_utc.astimezone(ZoneInfo(return_place.timezone_name))
    return_offset = exact_return_local.utcoffset()
    if return_offset is None:
        raise HTTPException(status_code=400, detail=f"Could not determine return timezone offset: {return_place.timezone_name}")

    return_chart = build_chart_response_from_jd(
        jd=exact_return_jd,
        year=exact_return_local.year,
        month=exact_return_local.month,
        day=exact_return_local.day,
        hour=exact_return_local.hour,
        minute=exact_return_local.minute,
        latitude=return_place.latitude,
        longitude=return_place.longitude,
        timezone_offset=return_offset.total_seconds() / 3600.0,
        timezone_name=return_place.timezone_name,
        resolved_place=return_place.birthplace_resolved,
        birthplace=request.return_location,
    )

    payload = solar_return_payload(
        request=request,
        natal_place=natal_place,
        return_place=return_place,
        exact_return_jd=exact_return_jd,
        natal_sun_longitude=natal_sun_longitude,
        return_sun_longitude=return_sun_longitude,
        return_chart=return_chart,
    )
    logger.info(
        "solar return complete verified=%s delta_arcseconds=%s",
        payload.get("verified_solar_return"),
        payload.get("longitude_delta_arcseconds"),
    )
    return json_response(payload)


@app.post(
    "/calculate_progressed_chart",
    operation_id="calculate_progressed_chart",
    description=(
        "Calculate a secondary progressed chart with progressed planets and progressed Placidus angles."
    ),
    responses={
        200: {
            "description": "Secondary progressed chart calculation result.",
            "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}},
        },
    },
)
def calculate_progressed_chart(request: ProgressedChartRequest):
    logger.info(
        "progressed chart start birthplace=%s target=%s-%s-%s location=%s",
        request.birthplace,
        request.progression_year,
        request.progression_month,
        request.progression_day,
        request.progression_location or request.birthplace,
    )
    natal_place = resolve_birthplace(request.birthplace)
    calculation_place = resolve_birthplace(request.progression_location or request.birthplace)

    birth_utc = local_datetime_to_utc(
        request.birth_year,
        request.birth_month,
        request.birth_day,
        request.birth_hour,
        request.birth_minute,
        natal_place.timezone_name,
        "birth",
    )
    target_utc = local_datetime_to_utc(
        request.progression_year,
        request.progression_month,
        request.progression_day,
        request.progression_hour,
        request.progression_minute,
        calculation_place.timezone_name,
        "progression target",
    )
    target_local = target_utc.astimezone(ZoneInfo(calculation_place.timezone_name))
    progressed_utc, progressed_days_after_birth, age_years = secondary_progressed_utc(
        birth_utc=birth_utc,
        target_utc=target_utc,
    )
    progressed_jd = datetime_to_julian_day_utc(progressed_utc)
    progressed_local = progressed_utc.astimezone(ZoneInfo(calculation_place.timezone_name))
    progressed_offset = progressed_local.utcoffset()
    if progressed_offset is None:
        raise HTTPException(
            status_code=400,
            detail=f"Could not determine progressed timezone offset: {calculation_place.timezone_name}",
        )

    progressed_chart = build_chart_response_from_jd(
        jd=progressed_jd,
        year=progressed_local.year,
        month=progressed_local.month,
        day=progressed_local.day,
        hour=progressed_local.hour,
        minute=progressed_local.minute,
        latitude=calculation_place.latitude,
        longitude=calculation_place.longitude,
        timezone_offset=progressed_offset.total_seconds() / 3600.0,
        timezone_name=calculation_place.timezone_name,
        resolved_place=calculation_place.birthplace_resolved,
        birthplace=request.progression_location or request.birthplace,
    )

    payload = progressed_chart_payload(
        request=request,
        natal_place=natal_place,
        calculation_place=calculation_place,
        birth_utc=birth_utc,
        target_utc=target_utc,
        target_local=target_local,
        progressed_utc=progressed_utc,
        progressed_days_after_birth=progressed_days_after_birth,
        age_years=age_years,
        progressed_chart=progressed_chart,
    )
    logger.info(
        "progressed chart complete age_years=%.6f progressed_days=%.6f body_count=%s",
        age_years,
        progressed_days_after_birth,
        payload.get("chart", {}).get("body_count"),
    )
    return json_response(payload)


@app.post(
    "/calculate_progressed_chart_solar_arc_angles",
    operation_id="calculate_progressed_chart_solar_arc_angles",
    description=(
        "Calculate secondary progressed planets with Solar Arc in Longitude directed ASC, MC, and house cusps."
    ),
    responses={
        200: {
            "description": "Secondary progressed chart with Solar Arc longitude angles result.",
            "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}},
        },
    },
)
def calculate_progressed_chart_solar_arc_angles(request: ProgressedChartRequest):
    logger.info(
        "progressed solar arc angles start birthplace=%s target=%s-%s-%s target_location=%s",
        request.birthplace,
        request.progression_year,
        request.progression_month,
        request.progression_day,
        request.progression_location or request.birthplace,
    )
    natal_place = resolve_birthplace(request.birthplace)
    target_place = resolve_birthplace(request.progression_location or request.birthplace)

    birth_utc = local_datetime_to_utc(
        request.birth_year,
        request.birth_month,
        request.birth_day,
        request.birth_hour,
        request.birth_minute,
        natal_place.timezone_name,
        "birth",
    )
    target_utc = local_datetime_to_utc(
        request.progression_year,
        request.progression_month,
        request.progression_day,
        request.progression_hour,
        request.progression_minute,
        target_place.timezone_name,
        "progression target",
    )
    target_local = target_utc.astimezone(ZoneInfo(target_place.timezone_name))
    progressed_utc, progressed_days_after_birth, age_years = secondary_progressed_utc(
        birth_utc=birth_utc,
        target_utc=target_utc,
    )
    natal_jd = datetime_to_julian_day_utc(birth_utc)
    progressed_jd = datetime_to_julian_day_utc(progressed_utc)

    natal_planets = calculate_planets(natal_jd).model_dump(by_alias=True)
    progressed_planet_values = calculate_planets(progressed_jd).model_dump(by_alias=True)
    natal_sun_longitude = float(natal_planets["Sun"] % 360.0)
    progressed_sun_longitude = float(progressed_planet_values["Sun"] % 360.0)
    solar_arc = (progressed_sun_longitude - natal_sun_longitude) % 360.0

    _natal_houses, natal_cusp_values, natal_ascendant, natal_midheaven = calculate_houses(
        natal_jd,
        natal_place.latitude,
        natal_place.longitude,
    )
    directed_cusps = directed_house_cusps(natal_cusp_values, solar_arc)
    directed_cusp_values = [cusp.absolute_degree for cusp in directed_cusps]
    progressed_planets = [
        PlacementResponse(
            body=body,
            sign=zodiac_sign(absolute_degree),
            degree=zodiac_degree(absolute_degree),
            absolute_degree=absolute_degree,
            house=house_for_degree(absolute_degree, directed_cusp_values),
        )
        for body, absolute_degree in progressed_planet_values.items()
    ]

    payload = progressed_solar_arc_angles_payload(
        request=request,
        natal_place=natal_place,
        target_place=target_place,
        birth_utc=birth_utc,
        target_utc=target_utc,
        target_local=target_local,
        progressed_utc=progressed_utc,
        progressed_days_after_birth=progressed_days_after_birth,
        age_years=age_years,
        natal_sun_longitude=natal_sun_longitude,
        progressed_sun_longitude=progressed_sun_longitude,
        natal_ascendant=natal_ascendant,
        natal_midheaven=natal_midheaven,
        directed_cusps=directed_cusps,
        progressed_planets=progressed_planets,
    )
    logger.info(
        "progressed solar arc angles complete solar_arc=%.8f body_count=%s",
        solar_arc,
        payload.get("chart", {}).get("body_count"),
    )
    return json_response(payload)


@app.get("/test", response_model=TestResponse)
def run_tests():
    case_results: list[TestCaseResult] = []

    for birthplace in TEST_BIRTHPLACES:
        try:
            resolved = resolve_birthplace(birthplace)
            timezone_offset = timezone_offset_hours(1972, 7, 31, 22, 50, resolved.timezone_name)
            chart = build_chart_response(
                year=1972,
                month=7,
                day=31,
                hour=22,
                minute=50,
                latitude=resolved.latitude,
                longitude=resolved.longitude,
                timezone_offset=timezone_offset,
                timezone_name=resolved.timezone_name,
                resolved_place=resolved.birthplace_resolved,
                birthplace=birthplace,
            )
            case_results.append(
                TestCaseResult(
                    birthplace=birthplace,
                    status="success",
                    latitude=chart.birth_data.latitude,
                    longitude=chart.birth_data.longitude,
                    timezone=chart.birth_data.timezone_offset,
                )
            )
        except Exception as error:
            logger.exception("test case failed birthplace=%s", birthplace)
            case_results.append(TestCaseResult(birthplace=birthplace, status="error", message=str(error)))

    failed = sum(1 for result in case_results if result.status == "error")
    return TestResponse(
        status="error" if failed else "success",
        total=len(case_results),
        passed=len(case_results) - failed,
        failed=failed,
        cases=case_results,
    )
