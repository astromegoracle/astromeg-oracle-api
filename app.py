from datetime import datetime
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
        "midheaven",
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
                },
            },
        },
        "ascendant": {"type": "number"},
        "midheaven": {"type": "number"},
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
                "house": placement.house,
            }
            for placement in chart.placements
        ],
        "houses": [
            {
                "house": house.house,
                "sign": house.sign,
                "degree": round(house.degree, 2),
            }
            for house in chart.houses
        ],
        "ascendant": round(chart.ascendant % 360, 2),
        "midheaven": round(chart.midheaven % 360, 2),
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

    schema["openapi"] = "3.1.0"
    schema["paths"] = {"/chart": {"get": chart_operation}}
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
