from datetime import datetime
import json
import logging
import os
from pathlib import Path
import time
from typing import Annotated, Literal
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import swisseph as swe


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("astromeg-oracle")

BASE_DIR = Path(__file__).resolve().parent
EPHE_PATH = BASE_DIR / "ephe"
EPHE_FILES = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")
USER_AGENT = "astromeg-oracle-api/1.0"
GEOCODE_TIMEOUT_SECONDS = 3
TIMEZONE_TIMEOUT_SECONDS = 3
LOOKUP_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 0.25
HOUSE_SYSTEM = "Placidus"
ZODIAC = "Tropical"

os.environ["SE_EPHE_PATH"] = str(EPHE_PATH)
swe.set_ephe_path(str(EPHE_PATH))


class ErrorResponse(BaseModel):
    status: Literal["error"]
    message: str
    details: str


class HousesResponse(BaseModel):
    system: Literal["Placidus"]
    cusps: dict[str, float]


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
    status: Literal["success"]
    planets: PlanetsResponse
    houses: HousesResponse
    ascendant: float
    midheaven: float
    birthplace_resolved: str | None
    latitude: float
    longitude: float
    timezone: float


class HealthResponse(BaseModel):
    status: Literal["ok"]
    engine: Literal["Swiss Ephemeris"]
    zodiac: Literal["Tropical"]
    houses: Literal["Placidus"]
    ephe_path: str
    ephe_files: dict[str, bool]
    cache_entries: int


class TestCaseResult(BaseModel):
    birthplace: str
    status: Literal["success", "error"]
    latitude: float | None = None
    longitude: float | None = None
    timezone: float | None = None
    message: str | None = None


class TestResponse(BaseModel):
    status: Literal["success", "error"]
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
PLACE_CACHE: dict[str, PlaceResolution] = dict(COMMON_PLACE_CACHE)

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


def normalize_place(value: str) -> str:
    return " ".join(value.casefold().replace(",", " , ").split()).replace(" ,", ",")


def fetch_json(url: str, timeout: int) -> object:
    request = UrlRequest(url, headers={"User-Agent": USER_AGENT})
    last_error = None

    for attempt in range(LOOKUP_ATTEMPTS):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            logger.warning("lookup failed attempt=%s url=%s error=%s", attempt + 1, url, error)
            if attempt < LOOKUP_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_SECONDS)

    raise HTTPException(status_code=502, detail=f"External lookup unavailable: {last_error}")


def geocode_birthplace(birthplace: str) -> tuple[float, float, str]:
    query = urlencode({"q": birthplace, "format": "json", "limit": 1})
    url = f"https://nominatim.openstreetmap.org/search?{query}"
    matches = fetch_json(url, GEOCODE_TIMEOUT_SECONDS)

    if not isinstance(matches, list) or not matches:
        raise HTTPException(status_code=400, detail=f"Could not geocode birthplace: {birthplace}")

    match = matches[0]
    try:
        return float(match["lat"]), float(match["lon"]), match.get("display_name", birthplace)
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=502, detail=f"Malformed geocoder response: {error}") from error


def resolve_timezone_name(latitude: float, longitude: float) -> str:
    query = urlencode({"latitude": latitude, "longitude": longitude})
    url = f"https://timeapi.io/api/TimeZone/coordinate?{query}"
    timezone_data = fetch_json(url, TIMEZONE_TIMEOUT_SECONDS)

    if not isinstance(timezone_data, dict) or not timezone_data.get("timeZone"):
        raise HTTPException(status_code=400, detail="Could not determine timezone for birthplace.")

    return str(timezone_data["timeZone"])


def resolve_birthplace(birthplace: str) -> PlaceResolution:
    cache_key = normalize_place(birthplace)
    cached = PLACE_CACHE.get(cache_key)
    if cached:
        logger.info("birthplace cache hit query=%s resolved=%s", birthplace, cached.birthplace_resolved)
        return cached

    logger.info("birthplace cache miss query=%s", birthplace)
    latitude, longitude, birthplace_resolved = geocode_birthplace(birthplace)
    timezone_name = resolve_timezone_name(latitude, longitude)
    resolution = PlaceResolution(
        query=birthplace,
        birthplace_resolved=birthplace_resolved,
        latitude=latitude,
        longitude=longitude,
        timezone_name=timezone_name,
    )
    PLACE_CACHE[cache_key] = resolution
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


def calculate_houses(jd: float, latitude: float, longitude: float) -> tuple[HousesResponse, float, float]:
    try:
        cusps, ascmc = swe.houses(jd, latitude, longitude, b'P')
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not calculate Placidus houses: {error}") from error

    houses = HousesResponse(
        system=HOUSE_SYSTEM,
        cusps={str(index): cusp for index, cusp in enumerate(cusps, start=1)},
    )
    return houses, ascmc[0], ascmc[1]


def build_chart_response(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    latitude: float,
    longitude: float,
    timezone: float,
    birthplace_resolved: str | None,
) -> ChartResponse:
    jd = calculate_julian_day(year, month, day, hour, minute, timezone)
    planets = calculate_planets(jd)
    houses, ascendant, midheaven = calculate_houses(jd, latitude, longitude)

    return ChartResponse(
        status="success",
        planets=planets,
        houses=houses,
        ascendant=ascendant,
        midheaven=midheaven,
        birthplace_resolved=birthplace_resolved,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
    )


app = FastAPI(
    title="Astromeg Oracle Swiss Ephemeris API",
    version="1.0.0",
    servers=[{"url": "https://astromeg-oracle-api.onrender.com"}],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    logger.warning("request error status=%s detail=%s", exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": str(exc.detail), "details": ""},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    logger.warning("validation error details=%s", exc.errors())
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": "Invalid request parameters.", "details": str(exc.errors())},
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(_request: Request, exc: Exception):
    logger.exception("unexpected error")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error.", "details": str(exc)},
    )


@app.get("/")
def home():
    return {"status": "Astromeg Oracle API Running"}


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
    response_model=ChartResponse,
    description=(
        "Calculate a tropical natal chart with Placidus houses using Swiss Ephemeris. "
        "Provide either year, month, day, hour, minute, timezone, latitude, longitude "
        "or year, month, day, hour, minute, birthplace."
    ),
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
def calculate_chart(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    timezone: Annotated[
        float | None,
        Query(description="UTC offset in hours. Required with latitude and longitude. Omit when using birthplace."),
    ] = None,
    latitude: Annotated[
        float | None,
        Query(description="Birth latitude in decimal degrees. Required with longitude and timezone unless birthplace is provided."),
    ] = None,
    longitude: Annotated[
        float | None,
        Query(description="Birth longitude in decimal degrees. Required with latitude and timezone unless birthplace is provided."),
    ] = None,
    birthplace: Annotated[
        str | None,
        Query(description="Birthplace to geocode. When provided, latitude, longitude, and timezone are resolved automatically."),
    ] = None,
):
    birthplace_resolved = None

    if birthplace:
        resolved = resolve_birthplace(birthplace)
        latitude = resolved.latitude
        longitude = resolved.longitude
        birthplace_resolved = resolved.birthplace_resolved
        timezone = timezone_offset_hours(year, month, day, hour, minute, resolved.timezone_name)
    elif timezone is None or latitude is None or longitude is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Provide either year, month, day, hour, minute, timezone, latitude, longitude "
                "or year, month, day, hour, minute, birthplace."
            ),
        )

    return build_chart_response(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        birthplace_resolved=birthplace_resolved,
    )


@app.get("/test", response_model=TestResponse)
def run_tests():
    case_results: list[TestCaseResult] = []

    for birthplace in TEST_BIRTHPLACES:
        try:
            resolved = resolve_birthplace(birthplace)
            timezone = timezone_offset_hours(1972, 7, 31, 22, 50, resolved.timezone_name)
            chart = build_chart_response(
                year=1972,
                month=7,
                day=31,
                hour=22,
                minute=50,
                latitude=resolved.latitude,
                longitude=resolved.longitude,
                timezone=timezone,
                birthplace_resolved=resolved.birthplace_resolved,
            )
            case_results.append(
                TestCaseResult(
                    birthplace=birthplace,
                    status="success",
                    latitude=chart.latitude,
                    longitude=chart.longitude,
                    timezone=chart.timezone,
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
