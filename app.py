from datetime import date, datetime, timedelta, timezone
import csv
import hmac
import io
import json
import logging
import math
import os
from pathlib import Path
import time
from typing import Annotated, Optional
from urllib.error import URLError
from urllib.parse import quote, urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field, StrictInt
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
ACCESS_VALIDATION_TIMEOUT_SECONDS = float(os.environ.get("ORACLE_ACCESS_VALIDATION_TIMEOUT_SECONDS", "6"))
ACCESS_VALIDATION_ATTEMPTS = int(os.environ.get("ORACLE_ACCESS_VALIDATION_ATTEMPTS", "3"))
ACCESS_VALIDATION_RETRY_DELAY_SECONDS = float(os.environ.get("ORACLE_ACCESS_VALIDATION_RETRY_DELAY_SECONDS", "0.5"))
HOUSE_SYSTEM = "Placidus"
ZODIAC = "Tropical"
HOUSE_SYSTEM_CODES = {
    "placidus": ("Placidus", b"P"),
    "regiomontanus": ("Regiomontanus", b"R"),
}
MOON_ASPECT_ORB_DEGREES = 8.0
MOON_ASPECTS = {
    "Conjunction": 0.0,
    "Sextile": 60.0,
    "Square": 90.0,
    "Trine": 120.0,
    "Opposition": 180.0,
}
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
MANILA_TIMEZONE = "Asia/Manila"
FREE_ACCESS_DEADLINE = datetime(2026, 5, 18, 0, 0, tzinfo=ZoneInfo(MANILA_TIMEZONE))
VALID_ACCESS_STATUSES = {"ACTIVE", "PAID"}

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


class HarmonicChartRequest(BaseModel):
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_minute: int
    birthplace: str
    harmonic_number: int = Field(..., ge=1, le=360)
    aspect_orb: float = Field(default=2.0, ge=0.0, le=10.0)


class HarmonicChartsRequest(BaseModel):
    name: Optional[str] = None
    birth_date: date
    birth_time: Optional[str] = None
    birth_place: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    harmonics: list[StrictInt] = Field(default_factory=lambda: [5, 8, 10, 11])
    points: list[str] = Field(
        default_factory=lambda: [
            "Sun",
            "Moon",
            "Mercury",
            "Venus",
            "Mars",
            "Jupiter",
            "Saturn",
            "Uranus",
            "Neptune",
            "Pluto",
            "True Node",
            "Chiron",
        ]
    )
    orb: float = 3.0
    response_level: str = "standard"
    include_clusters: bool = True
    include_natal_reference: bool = False
    include_houses: bool = False


class RelationshipBirthInput(BaseModel):
    name: Optional[str] = None
    birth_date: date
    birth_time: str
    birth_place: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None


class RelationshipChartRequest(BaseModel):
    person_a: RelationshipBirthInput
    person_b: RelationshipBirthInput
    points: list[str] = Field(
        default_factory=lambda: [
            "Sun",
            "Moon",
            "Mercury",
            "Venus",
            "Mars",
            "Jupiter",
            "Saturn",
            "Uranus",
            "Neptune",
            "Pluto",
            "True Node",
            "Lilith",
            "Chiron",
            "ASC",
            "MC",
        ]
    )
    include_houses: bool = True


class AccessCodeValidationRequest(BaseModel):
    access_code: str


class AccessCodeValidationResponse(BaseModel):
    valid: bool
    status: str
    message: str
    customer_name: str | None = None
    email: str | None = None
    expiration_date: str | None = None
    permission_level: str | None = None
    reading_type: str | None = None


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
ACCESS_CODE_REQUEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["access_code"],
    "properties": {
        "access_code": {
            "type": "string",
            "example": "AMO-VIP-30DAY-0072",
            "description": "User-provided access code. Trim spaces before validating.",
        },
    },
}
ACCESS_CODE_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["valid", "status", "message"],
    "properties": {
        "valid": {"type": "boolean"},
        "status": {"type": "string", "example": "ACTIVE"},
        "message": {"type": "string", "example": "Access confirmed."},
        "customer_name": {"type": ["string", "null"]},
        "email": {"type": ["string", "null"]},
        "expiration_date": {"type": ["string", "null"], "example": "2026-05-31"},
        "permission_level": {"type": ["string", "null"], "example": "VIP"},
        "reading_type": {"type": ["string", "null"], "example": "30DAY"},
    },
    "examples": [
        {
            "valid": True,
            "status": "ACTIVE",
            "customer_name": None,
            "email": None,
            "expiration_date": "2026-05-31",
            "permission_level": "VIP",
            "reading_type": "30DAY",
            "message": "Access confirmed.",
        },
        {
            "valid": False,
            "status": "EXPIRED",
            "expiration_date": "2026-05-31",
            "message": "This access code has expired.",
        },
        {
            "valid": False,
            "status": "INVALID",
            "message": "Invalid access code.",
        },
        {
            "valid": False,
            "status": "ERROR",
            "message": "Access validation is temporarily unavailable. Please try again.",
        },
    ],
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
        "verified_chart_data": {"type": "boolean"},
        "chart_text": {"type": "string"},
        "result": {"type": "string"},
        "placements_text": {"type": "string"},
        "body_count": {"type": "integer"},
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
        "verified_chart_data": {"type": "boolean"},
        "chart_text": {"type": "string"},
        "result": {"type": "string"},
        "placements_text": {"type": "string"},
        "body_count": {"type": "integer"},
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
        "verified_chart_data": {"type": "boolean"},
        "chart_text": {"type": "string"},
        "result": {"type": "string"},
        "placements_text": {"type": "string"},
        "body_count": {"type": "integer"},
        "aspects": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
    },
}
PROGRESSED_SOLAR_LONGITUDE_CHART_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": [
        "status",
        "success",
        "verified_progressed_chart",
        "progression_method",
        "angles_method",
        "solar_arc_degrees",
        "natal_sun_longitude",
        "progressed_sun_longitude",
        "natal_angles",
        "progressed_angles",
        "placements",
        "chart_text",
        "placements_text",
        "birth_data",
        "progression_data",
    ],
    "properties": {
        "status": {"type": "string"},
        "success": {"type": "boolean"},
        "message": {"type": "string"},
        "verified_progressed_chart": {"type": "boolean"},
        "progression_method": {"type": "string"},
        "angles_method": {"type": "string"},
        "solar_arc_degrees": {"type": "number"},
        "solar_arc": {"type": "object", "additionalProperties": True},
        "natal_sun_longitude": {"type": "number"},
        "progressed_sun_longitude": {"type": "number"},
        "natal_angles": {"type": "object", "additionalProperties": True},
        "progressed_angles": {"type": "object", "additionalProperties": True},
        "angles_only_houses_supported": {"type": "boolean"},
        "house_assignment_method": {"type": "string"},
        "progressed_house_cusps": CHART_SUCCESS_SCHEMA["properties"]["houses"],
        "placements": CHART_SUCCESS_SCHEMA["properties"]["placements"],
        "verified_chart_data": {"type": "boolean"},
        "chart": {"type": "string"},
        "result": {"type": "string"},
        "chart_text": {"type": "string"},
        "placements_text": {"type": "string"},
        "body_count": {"type": "integer"},
        "birth_data": {"type": "object", "additionalProperties": True},
        "progression_data": {"type": "object", "additionalProperties": True},
    },
}
SOLAR_ARC_DIRECTIONS_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": [
        "status",
        "success",
        "verified_solar_arc_directions",
        "direction_method",
        "solar_arc_degrees",
        "natal_sun_longitude",
        "progressed_sun_longitude",
        "directed_positions",
        "directed_angles",
        "natal_positions",
        "birth_data",
        "progression_data",
        "chart_text",
        "placements_text",
    ],
    "properties": {
        "status": {"type": "string"},
        "success": {"type": "boolean"},
        "message": {"type": "string"},
        "verified_solar_arc_directions": {"type": "boolean"},
        "direction_method": {"type": "string"},
        "solar_arc_degrees": {"type": "number"},
        "solar_arc": {"type": "object", "additionalProperties": True},
        "natal_sun_longitude": {"type": "number"},
        "progressed_sun_longitude": {"type": "number"},
        "directed_positions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "placements": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "directed_angles": {"type": "object", "additionalProperties": True},
        "directed_house_cusps": CHART_SUCCESS_SCHEMA["properties"]["houses"],
        "directed_house_assignment_supported": {"type": "boolean"},
        "natal_positions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "natal_angles": {"type": "object", "additionalProperties": True},
        "natal_houses": CHART_SUCCESS_SCHEMA["properties"]["houses"],
        "birth_data": {"type": "object", "additionalProperties": True},
        "progression_data": {"type": "object", "additionalProperties": True},
        "verified_chart_data": {"type": "boolean"},
        "chart": {"type": "string"},
        "result": {"type": "string"},
        "chart_text": {"type": "string"},
        "placements_text": {"type": "string"},
        "body_count": {"type": "integer"},
    },
}
HARMONIC_CHART_REQUEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "birth_year",
        "birth_month",
        "birth_day",
        "birth_hour",
        "birth_minute",
        "birthplace",
        "harmonic_number",
    ],
    "properties": {
        "birth_year": {"type": "integer", "example": 1972},
        "birth_month": {"type": "integer", "example": 7},
        "birth_day": {"type": "integer", "example": 31},
        "birth_hour": {"type": "integer", "example": 22},
        "birth_minute": {"type": "integer", "example": 50},
        "birthplace": {"type": "string", "example": "Quezon City, Philippines"},
        "harmonic_number": {
            "type": "integer",
            "minimum": 1,
            "maximum": 360,
            "example": 24,
            "description": "Western harmonic number. This is not a Vedic varga or sidereal divisional chart.",
        },
        "aspect_orb": {
            "type": "number",
            "minimum": 0,
            "maximum": 10,
            "default": 2,
            "example": 2,
            "description": "Orb in degrees for harmonic conjunction detection.",
        },
    },
}
HARMONIC_CHART_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": [
        "status",
        "success",
        "verified_harmonic_chart",
        "method",
        "harmonic_number",
        "placements",
        "natal_positions",
        "chart_text",
        "placements_text",
        "body_count",
        "birth_data",
    ],
    "properties": {
        "status": {"type": "string"},
        "success": {"type": "boolean"},
        "message": {"type": "string"},
        "verified_harmonic_chart": {"type": "boolean"},
        "method": {"type": "string"},
        "zodiac": {"type": "string"},
        "harmonic_number": {"type": "integer"},
        "houses_supported": {"type": "boolean"},
        "house_method": {"type": "string"},
        "placements": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "natal_positions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "harmonic_angles": {"type": "object", "additionalProperties": True},
        "conjunctions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "chart_text": {"type": "string"},
        "placements_text": {"type": "string"},
        "body_count": {"type": "integer"},
        "birth_data": {"type": "object", "additionalProperties": True},
    },
}
BULK_HARMONIC_CHART_REQUEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["birth_date"],
    "properties": {
        "name": {"type": "string", "example": "Meg"},
        "birth_date": {"type": "string", "format": "date", "example": "1972-07-31"},
        "birth_time": {"type": "string", "example": "22:50"},
        "birth_place": {"type": "string", "example": "Quezon City, Philippines"},
        "latitude": {"type": "number", "example": 14.6760},
        "longitude": {"type": "number", "example": 121.0437},
        "timezone": {"type": "string", "example": "Asia/Manila"},
        "harmonics": {
            "type": "array",
            "items": {"type": "integer", "minimum": 1, "maximum": 360},
            "default": [5, 8, 10, 11],
            "example": [5, 8, 10, 11],
            "description": "Western harmonic numbers only. No Vedic or sidereal divisional charts.",
        },
        "points": {
            "type": "array",
            "items": {"type": "string"},
            "default": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "True Node", "Chiron"],
        },
        "orb": {"type": "number", "minimum": 0.5, "maximum": 5, "default": 3},
        "response_level": {"type": "string", "enum": ["compact", "standard", "full"], "default": "standard"},
        "include_clusters": {"type": "boolean", "default": True},
        "include_natal_reference": {"type": "boolean", "default": False},
        "include_houses": {"type": "boolean", "default": False},
    },
}
BULK_HARMONIC_CHART_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": ["status", "success", "chart_type", "settings", "harmonic_charts", "warnings"],
    "properties": {
        "status": {"type": "string"},
        "success": {"type": "boolean"},
        "message": {"type": "string"},
        "chart_type": {"type": "string"},
        "settings": {"type": "object", "additionalProperties": True},
        "birth_data": {"type": "object", "additionalProperties": True},
        "requested_harmonics": {"type": "array", "items": {"type": "integer"}},
        "harmonic_charts": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "natal_reference": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "body_count": {"type": "integer"},
    },
}
RELATIONSHIP_BIRTH_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["birth_date", "birth_time"],
    "properties": {
        "name": {"type": "string", "example": "Person A"},
        "birth_date": {"type": "string", "format": "date", "example": "1972-07-31"},
        "birth_time": {"type": "string", "example": "22:50"},
        "birth_place": {"type": "string", "example": "Quezon City, Philippines"},
        "latitude": {"type": "number", "example": 14.676},
        "longitude": {"type": "number", "example": 121.0437},
        "timezone": {"type": "string", "example": "Asia/Manila"},
    },
}
RELATIONSHIP_CHART_REQUEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["person_a", "person_b"],
    "properties": {
        "person_a": RELATIONSHIP_BIRTH_INPUT_SCHEMA,
        "person_b": RELATIONSHIP_BIRTH_INPUT_SCHEMA,
        "points": {
            "type": "array",
            "items": {"type": "string"},
            "default": ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "True Node", "Lilith", "Chiron", "ASC", "MC"],
        },
        "include_houses": {"type": "boolean", "default": True},
    },
}
RELATIONSHIP_CHART_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": ["status", "success", "chart_type", "method", "placements", "birth_data", "chart_text", "placements_text", "body_count"],
    "properties": {
        "status": {"type": "string"},
        "success": {"type": "boolean"},
        "message": {"type": "string"},
        "verified_relationship_chart": {"type": "boolean"},
        "chart_type": {"type": "string"},
        "method": {"type": "string"},
        "settings": {"type": "object", "additionalProperties": True},
        "birth_data": {"type": "object", "additionalProperties": True},
        "calculation_data": {"type": "object", "additionalProperties": True},
        "placements": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "angles": {"type": "object", "additionalProperties": True},
        "houses": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "chart_text": {"type": "string"},
        "placements_text": {"type": "string"},
        "body_count": {"type": "integer"},
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

MAX_HARMONIC_NUMBER = 360
MAX_HARMONIC_COUNT = 20
DEFAULT_HARMONIC_NUMBERS = [5, 8, 10, 11]
DEFAULT_HARMONIC_POINTS = [
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
    "True Node",
    "Chiron",
]
ANGLE_POINT_ALIASES = {
    "ASC": "ASC",
    "ASCENDANT": "ASC",
    "AC": "ASC",
    "MC": "MC",
    "MIDHEAVEN": "MC",
}
PLANET_POINT_ALIASES = {
    "SUN": ("Sun", "Sun"),
    "MOON": ("Moon", "Moon"),
    "MERCURY": ("Mercury", "Mercury"),
    "VENUS": ("Venus", "Venus"),
    "MARS": ("Mars", "Mars"),
    "JUPITER": ("Jupiter", "Jupiter"),
    "SATURN": ("Saturn", "Saturn"),
    "URANUS": ("Uranus", "Uranus"),
    "NEPTUNE": ("Neptune", "Neptune"),
    "PLUTO": ("Pluto", "Pluto"),
    "TRUE NODE": ("True Node", "North Node"),
    "NORTH NODE": ("True Node", "North Node"),
    "NODE": ("True Node", "North Node"),
    "LILITH": ("Lilith", "Lilith"),
    "CHIRON": ("Chiron", "Chiron"),
}
HARMONIC_THEMES = {
    1: "Natal identity",
    2: "Polarity, projection, relationship mirroring",
    3: "Flow, inherited gifts, natural ease",
    4: "Challenge, tension, ambition, manifestation",
    5: "Creative genius, talent, pattern recognition",
    6: "Adjustment, service, refinement, practical integration",
    7: "Mystical destiny, fate, divine compulsion",
    8: "Power, ambition, sexuality, shared resources, transformation",
    9: "Spiritual mastery, wisdom, teacher frequency",
    10: "Career achievement, public structure, legacy",
    11: "Visionary contribution, audience, community, future vision",
    12: "Hidden karma, surrender, unconscious integration",
    15: "Desire, magnetism, material temptation",
    22: "Master builder, extreme ambition, legacy force",
    24: "Grace, learning mastery, integrated talent",
    36: "Structured mysticism",
    48: "Grand material blueprint",
    60: "Karmic fine-tuning",
    72: "Master alchemist",
}

ACCESS_CACHE_TTL_SECONDS = int(os.environ.get("ORACLE_ACCESS_CACHE_TTL_SECONDS", "21600"))
ACCESS_CACHE: dict[str, tuple[float, dict]] = {}

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


def normalize_longitude(absolute_degree: float) -> float:
    return absolute_degree % 360.0


def resolve_house_system(house_system: str | None = None, chart_type: str | None = None) -> tuple[str, bytes]:
    if house_system and str(house_system).strip():
        requested = " ".join(str(house_system).strip().casefold().split())
    elif chart_type and str(chart_type).strip().casefold() == "horary":
        requested = "regiomontanus"
    else:
        requested = HOUSE_SYSTEM.casefold()

    aliases = {
        "p": "placidus",
        "placidus": "placidus",
        "r": "regiomontanus",
        "regiomontanus": "regiomontanus",
        "regio": "regiomontanus",
    }
    key = aliases.get(requested)
    if key not in HOUSE_SYSTEM_CODES:
        supported = ", ".join(name for name, _code in HOUSE_SYSTEM_CODES.values())
        raise HTTPException(status_code=400, detail=f"Unsupported house_system: {house_system}. Supported values: {supported}.")
    return HOUSE_SYSTEM_CODES[key]


def calculate_solar_arc_longitude(natal_sun_longitude: float, progressed_sun_longitude: float) -> float:
    return normalize_longitude(progressed_sun_longitude - natal_sun_longitude)


def apply_solar_arc_longitude(absolute_degree: float, solar_arc: float) -> float:
    return normalize_longitude(absolute_degree + solar_arc)


def harmonic_longitude(absolute_degree: float, harmonic_number: int) -> float:
    return normalize_longitude(absolute_degree * harmonic_number)


def normalize_degrees(value: float) -> float:
    return normalize_longitude(value)


def longitude_to_sign_degree(longitude: float) -> dict[str, object]:
    return zodiac_position(longitude)


def calculate_harmonic_longitude(natal_longitude: float, harmonic_number: int) -> float:
    return harmonic_longitude(natal_longitude, harmonic_number)


def angular_separation(longitude_a: float, longitude_b: float) -> float:
    return abs(((longitude_a - longitude_b + 180.0) % 360.0) - 180.0)


def circular_distance(longitude_a: float, longitude_b: float) -> float:
    return angular_separation(longitude_a, longitude_b)


def circular_mean(longitudes: list[float]) -> float:
    if not longitudes:
        return 0.0
    sin_sum = sum(math.sin(math.radians(longitude)) for longitude in longitudes)
    cos_sum = sum(math.cos(math.radians(longitude)) for longitude in longitudes)
    if abs(sin_sum) < 1e-12 and abs(cos_sum) < 1e-12:
        return normalize_longitude(longitudes[0])
    return normalize_longitude(math.degrees(math.atan2(sin_sum, cos_sum)))


def get_harmonic_theme(harmonic_number: int) -> dict[str, str]:
    theme = HARMONIC_THEMES.get(harmonic_number)
    if theme:
        return {"theme": theme}
    return {
        "theme": "Custom harmonic",
        "theme_note": "No predefined Astromeg theme for this harmonic. Interpret through placements, clusters, and natal anchoring only.",
    }


def zodiac_position(absolute_degree: float) -> dict[str, object]:
    normalized = normalize_longitude(absolute_degree)
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
    normalized = normalize_longitude(arc_degrees)
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
            sign=zodiac_sign(apply_solar_arc_longitude(cusp, solar_arc)),
            degree=zodiac_degree(apply_solar_arc_longitude(cusp, solar_arc)),
            absolute_degree=apply_solar_arc_longitude(cusp, solar_arc),
        )
        for index, cusp in enumerate(cusp_values, start=1)
    ]


def placement_payload(placement: PlacementResponse) -> dict:
    position = zodiac_position(placement.absolute_degree)
    return {
        "body": placement.body,
        "sign": placement.sign,
        "degree": round(placement.degree, 2),
        "decimal_degree": position["decimal_degree"],
        "absolute_degree": position["absolute_degree"],
        "formatted": position["formatted"],
        "position": position,
        "house": placement.house,
    }


def house_payload(house: HouseCuspResponse) -> dict:
    position = zodiac_position(house.absolute_degree)
    return {
        "house": house.house,
        "sign": house.sign,
        "degree": round(house.degree, 2),
        "decimal_degree": position["decimal_degree"],
        "absolute_degree": position["absolute_degree"],
        "formatted": position["formatted"],
        "position": position,
    }


def named_position_payload(name: str, absolute_degree: float, house: int | None = None) -> dict:
    position = zodiac_position(absolute_degree)
    payload = {
        "body": name,
        "sign": position["sign"],
        "degree": round(float(position["decimal_degree"]), 2),
        "decimal_degree": position["decimal_degree"],
        "absolute_degree": position["absolute_degree"],
        "formatted": position["formatted"],
        "position": position,
    }
    if house is not None:
        payload["house"] = house
    return payload


def angle_payload(name: str, absolute_degree: float) -> dict:
    payload = named_position_payload(name, absolute_degree)
    payload["angle"] = payload.pop("body")
    return payload


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


def normalize_access_code(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def normalize_sheet_header(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def sheet_cell(row: list[object], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return str(row[index]).strip()


ACCESS_COLUMN_ALIASES = {
    "access_code": {"accesscode", "code"},
    "expiration_date": {"expirationdate", "expiration", "expirydate", "expires", "expireson"},
    "status": {"status"},
    "permission_level": {"permissionlevel", "permission", "level"},
    "reading_type": {"readingtype", "codetype", "type"},
    "customer_name": {"customername", "name", "clientname"},
    "email": {"email", "customeremail", "clientemail"},
}


def sheet_rows_to_records(rows: list[list[object]]) -> list[dict[str, str]]:
    if not rows:
        return []

    header_map = {normalize_sheet_header(str(header)): index for index, header in enumerate(rows[0])}
    indexes = {
        field: next((header_map[alias] for alias in aliases if alias in header_map), None)
        for field, aliases in ACCESS_COLUMN_ALIASES.items()
    }

    records = []
    for row in rows[1:]:
        if not any(str(cell).strip() for cell in row):
            continue
        records.append(
            {
                field: sheet_cell(row, index)
                for field, index in indexes.items()
            }
        )
    return records


def parse_expiration_date(value: str) -> date | None:
    stripped = value.strip()
    if not stripped:
        return None

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%Y/%m/%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(stripped, fmt).date()
        except ValueError:
            continue

    try:
        serial_value = float(stripped)
    except ValueError:
        return None

    if serial_value <= 0:
        return None

    return date(1899, 12, 30) + timedelta(days=int(serial_value))


def access_response(
    valid: bool,
    status: str,
    message: str,
    expiration_date: str | None = None,
    permission_level: str | None = None,
    reading_type: str | None = None,
    customer_name: str | None = None,
    email: str | None = None,
    include_null_fields: bool = False,
) -> dict:
    response = {
        "valid": valid,
        "status": status,
        "message": message,
    }
    optional_fields = {
        "customer_name": customer_name,
        "email": email,
        "expiration_date": expiration_date,
        "permission_level": permission_level,
        "reading_type": reading_type,
    }
    for key, value in optional_fields.items():
        if value is not None or include_null_fields:
            response[key] = value
    return response


def get_cached_access_response(access_code: str) -> dict | None:
    cache_key = normalize_access_code(access_code)
    cached = ACCESS_CACHE.get(cache_key)
    if cached is None:
        return None

    expires_at, response = cached
    if time.time() >= expires_at:
        ACCESS_CACHE.pop(cache_key, None)
        return None

    cached_response = dict(response)
    cached_response["cache"] = "hit"
    cached_response["message"] = cached_response.get("message") or "Access confirmed."
    logger.info("access code cache hit status=%s valid=%s", cached_response.get("status"), cached_response.get("valid"))
    return cached_response


def cache_access_response(access_code: str, response: dict) -> None:
    if not response.get("valid"):
        return

    status = str(response.get("status") or "").strip().upper()
    if status not in VALID_ACCESS_STATUSES:
        return

    ACCESS_CACHE[normalize_access_code(access_code)] = (time.time() + ACCESS_CACHE_TTL_SECONDS, dict(response))
    logger.info("access code cache saved status=%s ttl_seconds=%s", status, ACCESS_CACHE_TTL_SECONDS)


def validate_access_code_from_rows(
    access_code: str,
    rows: list[list[object]],
    now: datetime | None = None,
) -> dict:
    submitted_code = normalize_access_code(access_code)
    current_time = now or datetime.now(ZoneInfo(MANILA_TIMEZONE))
    today = current_time.date()

    if not submitted_code:
        return access_response(False, "INVALID", "Invalid access code.")

    if submitted_code in {"weekly", "daily"}:
        reading_type = submitted_code.upper()
        if current_time < FREE_ACCESS_DEADLINE:
            return access_response(
                True,
                "ACTIVE",
                "Access confirmed.",
                expiration_date=FREE_ACCESS_DEADLINE.date().isoformat(),
                permission_level="FREE",
                reading_type=reading_type,
            )
        return access_response(
            False,
            "EXPIRED",
            "This access code has expired.",
            expiration_date=FREE_ACCESS_DEADLINE.date().isoformat(),
        )

    for record in sheet_rows_to_records(rows):
        if normalize_access_code(record.get("access_code", "")) != submitted_code:
            continue

        raw_expiration = record.get("expiration_date", "")
        expiration = parse_expiration_date(raw_expiration)
        expiration_iso = expiration.isoformat() if expiration else None
        status = record.get("status", "").strip().upper()

        if expiration is not None and expiration < today:
            return access_response(False, "EXPIRED", "This access code has expired.", expiration_date=expiration_iso)

        if status not in VALID_ACCESS_STATUSES:
            return access_response(False, "INVALID", "Invalid access code.", expiration_date=expiration_iso)

        if expiration is None:
            return access_response(False, "INVALID", "Invalid access code.")

        return access_response(
            True,
            status,
            "Access confirmed.",
            customer_name=record.get("customer_name") or None,
            email=record.get("email") or None,
            expiration_date=expiration_iso,
            permission_level=record.get("permission_level") or "VIP",
            reading_type=record.get("reading_type") or "30DAY",
            include_null_fields=True,
        )

    return access_response(False, "INVALID", "Invalid access code.")


def fetch_access_sheet_csv_rows(csv_url: str) -> list[list[object]]:
    request = UrlRequest(csv_url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=GEOCODE_TIMEOUT_SECONDS) as response:
        raw_csv = response.read().decode("utf-8-sig")

    rows = list(csv.reader(io.StringIO(raw_csv)))
    if not rows:
        raise RuntimeError("Published Google Sheet CSV is empty.")
    return rows


def access_code_rows_from_env() -> list[list[object]] | None:
    raw_codes = os.environ.get("ORACLE_ACCESS_CODES_JSON", "").strip()
    if not raw_codes:
        return None

    try:
        payload = json.loads(raw_codes)
    except json.JSONDecodeError as error:
        raise RuntimeError("ORACLE_ACCESS_CODES_JSON must be valid JSON.") from error

    rows: list[list[object]] = [["Access Code", "Expiration Date", "Status", "Permission Level", "Reading Type"]]

    if isinstance(payload, dict):
        iterable = [
            {"access_code": code, **details} if isinstance(details, dict) else {"access_code": code, "expiration_date": details}
            for code, details in payload.items()
        ]
    elif isinstance(payload, list):
        iterable = payload
    else:
        raise RuntimeError("ORACLE_ACCESS_CODES_JSON must be a JSON object or array.")

    for item in iterable:
        if not isinstance(item, dict):
            raise RuntimeError("Each ORACLE_ACCESS_CODES_JSON entry must be an object.")

        access_code = str(item.get("access_code") or item.get("code") or "").strip()
        expiration_date = str(item.get("expiration_date") or item.get("expires") or item.get("expires_on") or "").strip()
        status = str(item.get("status") or "ACTIVE").strip()
        permission_level = str(item.get("permission_level") or item.get("permission") or "VIP").strip()
        reading_type = str(item.get("reading_type") or item.get("type") or "30DAY").strip()

        if not access_code:
            raise RuntimeError("Each ORACLE_ACCESS_CODES_JSON entry must include access_code.")
        if not expiration_date:
            raise RuntimeError(f"Access code {access_code} is missing expiration_date.")

        rows.append([access_code, expiration_date, status, permission_level, reading_type])

    return rows


def fetch_access_sheet_rows() -> list[list[object]]:
    env_rows = access_code_rows_from_env()
    if env_rows is not None:
        return env_rows

    csv_url = os.environ.get("GOOGLE_SHEET_CSV_URL", "").strip()
    if csv_url:
        return fetch_access_sheet_csv_rows(csv_url)

    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    tab_name = os.environ.get("GOOGLE_SHEET_TAB_NAME", "").strip()

    if not service_account_json or not sheet_id or not tab_name:
        raise RuntimeError("Missing access-code configuration. Set ORACLE_ACCESS_CODES_JSON, GOOGLE_SHEET_CSV_URL, or Google service account variables.")

    try:
        from google.auth.transport.requests import Request as GoogleAuthRequest
        from google.oauth2 import service_account
    except ImportError as error:
        raise RuntimeError("Google Sheets authentication dependency is not installed.") from error

    credentials_info = json.loads(service_account_json)
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    credentials.refresh(GoogleAuthRequest())

    escaped_tab_name = tab_name.replace("'", "''")
    range_name = f"'{escaped_tab_name}'!A:Z"
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{quote(sheet_id, safe='')}/values/"
        f"{quote(range_name, safe='')}?{urlencode({'majorDimension': 'ROWS'})}"
    )
    request = UrlRequest(
        url,
        headers={
            "Authorization": f"Bearer {credentials.token}",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=GEOCODE_TIMEOUT_SECONDS) as response:
        payload = json.load(response)

    values = payload.get("values", [])
    if not isinstance(values, list):
        raise RuntimeError("Malformed Google Sheets response.")
    return values


def validate_access_code_with_external_service(access_code: str) -> dict | None:
    validation_url = os.environ.get("ORACLE_ACCESS_VALIDATION_URL", "").strip()
    if not validation_url:
        return None

    validation_secret = os.environ.get("ORACLE_ACCESS_VALIDATION_SECRET", "").strip()
    separator = "&" if "?" in validation_url else "?"
    request_url = f"{validation_url}{separator}{urlencode({'access_code': access_code, 'secret': validation_secret})}"
    request = UrlRequest(
        request_url,
        headers={
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    result = None
    last_error = None
    for attempt in range(ACCESS_VALIDATION_ATTEMPTS):
        try:
            logger.info(
                "external access validation start attempt=%s timeout_seconds=%s",
                attempt + 1,
                ACCESS_VALIDATION_TIMEOUT_SECONDS,
            )
            with urlopen(request, timeout=ACCESS_VALIDATION_TIMEOUT_SECONDS) as response:
                result = json.load(response)
            logger.info(
                "external access validation response attempt=%s status=%s valid=%s",
                attempt + 1,
                result.get("status") if isinstance(result, dict) else None,
                result.get("valid") if isinstance(result, dict) else None,
            )
            break
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            logger.warning("external access validation failed attempt=%s error=%s", attempt + 1, error)
            if attempt < ACCESS_VALIDATION_ATTEMPTS - 1:
                time.sleep(ACCESS_VALIDATION_RETRY_DELAY_SECONDS)

    if result is None:
        raise RuntimeError(f"External access validation unavailable: {last_error}")

    if not isinstance(result, dict):
        raise RuntimeError("External access validation returned malformed JSON.")

    valid = bool(result.get("valid"))
    status = str(result.get("status") or ("ACTIVE" if valid else "INVALID")).strip().upper()
    message = str(result.get("message") or ("Access confirmed." if valid else "Invalid access code.")).strip()
    expiration_date = result.get("expiration_date") or result.get("expires_on") or result.get("expires")
    permission_level = result.get("permission_level") or result.get("permission")
    reading_type = result.get("reading_type") or result.get("type")

    return access_response(
        valid,
        status,
        message,
        expiration_date=str(expiration_date).strip() if expiration_date else None,
        permission_level=str(permission_level).strip() if permission_level else None,
        reading_type=str(reading_type).strip() if reading_type else None,
        include_null_fields=valid,
    )


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


def calculate_houses(
    jd: float,
    latitude: float,
    longitude: float,
    house_system: str | None = None,
) -> tuple[list[HouseCuspResponse], list[float], float, float]:
    house_system_name, house_system_code = resolve_house_system(house_system)
    try:
        cusps, ascmc = swe.houses(jd, latitude, longitude, house_system_code)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not calculate {house_system_name} houses: {error}") from error

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


def calculate_moon_aspects(planet_values: dict[str, float], orb_limit: float = MOON_ASPECT_ORB_DEGREES) -> list[AspectResponse]:
    moon_longitude = planet_values.get("Moon")
    if moon_longitude is None:
        return []

    aspects = []
    for body, longitude in planet_values.items():
        if body == "Moon":
            continue
        separation = angular_separation(moon_longitude, longitude)
        closest_name = None
        closest_orb = None
        for aspect_name, aspect_angle in MOON_ASPECTS.items():
            orb = abs(separation - aspect_angle)
            if closest_orb is None or orb < closest_orb:
                closest_name = aspect_name
                closest_orb = orb
        if closest_name is not None and closest_orb is not None and closest_orb <= orb_limit:
            aspects.append(
                AspectResponse(
                    body_a="Moon",
                    body_b=body,
                    aspect=closest_name,
                    orb=round(closest_orb, 4),
                )
            )
    return aspects


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
    house_system: str | None = None,
) -> ChartResponse:
    house_system_name, _house_system_code = resolve_house_system(house_system)
    planets = calculate_planets(jd)
    houses, cusp_values, ascendant, midheaven = calculate_houses(jd, latitude, longitude, house_system_name)
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
        house_system=house_system_name,
    )
    chart_text = chart_summary(placements)
    placements_text = placement_summary(placements)
    moon_aspects = calculate_moon_aspects(planet_values)
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
        aspects=moon_aspects,
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
    house_system: str | None = None,
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
        house_system=house_system,
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
        "aspects": [
            {
                "body_a": aspect.body_a,
                "body_b": aspect.body_b,
                "aspect": aspect.aspect,
                "orb": aspect.orb,
            }
            for aspect in chart.aspects
        ],
    }


def harmonic_chart_text(harmonic_number: int, placements: list[dict]) -> str:
    formatted = "\n".join(
        f"{placement['body']}: {placement['formatted']}"
        for placement in placements
    )
    return f"VERIFIED_ASTROMEG_HARMONIC_CHART_DATA\nH{harmonic_number} Western Tropical Harmonic\n{formatted}"


def harmonic_placements_text(harmonic_number: int, placements: list[dict]) -> str:
    formatted = "; ".join(
        f"{placement['body']}: {placement['formatted']}"
        for placement in placements
    )
    return f"SUCCESS | Western harmonic chart calculated | harmonic=H{harmonic_number} | body_count={len(placements)} | {formatted}"


def harmonic_conjunctions(placements: list[dict], orb: float) -> list[dict]:
    conjunctions = []
    for first_index, first in enumerate(placements):
        for second in placements[first_index + 1:]:
            separation = angular_separation(first["absolute_degree"], second["absolute_degree"])
            if separation <= orb:
                conjunctions.append(
                    {
                        "body_a": first["body"],
                        "body_b": second["body"],
                        "aspect": "Conjunction",
                        "orb": round(separation, 6),
                        "orb_degrees": separation,
                        "body_a_position": first["position"],
                        "body_b_position": second["position"],
                    }
                )
    return conjunctions


def harmonic_birth_data_payload(request: HarmonicChartRequest, natal_place: PlaceResolution, birth_utc: datetime) -> dict:
    return {
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
        "house_system": "Not used for Western harmonic placements",
    }


def calculate_harmonic_chart_payload(request: HarmonicChartRequest) -> dict:
    natal_place = resolve_birthplace(request.birthplace)
    birth_utc = local_datetime_to_utc(
        request.birth_year,
        request.birth_month,
        request.birth_day,
        request.birth_hour,
        request.birth_minute,
        natal_place.timezone_name,
        "birth",
    )
    natal_jd = datetime_to_julian_day_utc(birth_utc)
    natal_planets = calculate_planets(natal_jd).model_dump(by_alias=True)
    _natal_houses, _natal_cusp_values, natal_ascendant, natal_midheaven = calculate_houses(
        natal_jd,
        natal_place.latitude,
        natal_place.longitude,
    )

    natal_positions = [
        named_position_payload(body, normalize_longitude(longitude))
        for body, longitude in natal_planets.items()
    ]
    placements = []
    for body, natal_longitude in natal_planets.items():
        absolute_degree = harmonic_longitude(natal_longitude, request.harmonic_number)
        position = zodiac_position(absolute_degree)
        placements.append(
            {
                "body": body,
                "sign": position["sign"],
                "degree": round(float(position["decimal_degree"]), 2),
                "decimal_degree": position["decimal_degree"],
                "absolute_degree": position["absolute_degree"],
                "formatted": position["formatted"],
                "position": position,
                "natal_absolute_degree": normalize_longitude(natal_longitude),
                "natal_position": zodiac_position(natal_longitude),
                "harmonic_number": request.harmonic_number,
            }
        )

    harmonic_angles = {
        "ascendant": angle_payload("Ascendant", harmonic_longitude(natal_ascendant, request.harmonic_number)),
        "midheaven": angle_payload("Midheaven", harmonic_longitude(natal_midheaven, request.harmonic_number)),
        "source": "Natal ASC/MC multiplied by harmonic number. Houses are not generated.",
    }
    chart_text = harmonic_chart_text(request.harmonic_number, placements)
    placements_text = harmonic_placements_text(request.harmonic_number, placements)

    return {
        "status": "success",
        "success": True,
        "message": "Western harmonic chart calculated successfully",
        "verified_harmonic_chart": True,
        "verified_chart_data": True,
        "method": "Western tropical harmonic chart: natal ecliptic longitudes multiplied by harmonic number and normalized to 0-360.",
        "zodiac": ZODIAC,
        "calculation_engine": "Swiss Ephemeris",
        "harmonic_number": request.harmonic_number,
        "aspect_orb": request.aspect_orb,
        "houses_supported": False,
        "house_method": "Western harmonic charts prioritize planetary harmonic longitudes and aspect resonance. Placidus houses are not fabricated.",
        "placements": placements,
        "natal_positions": natal_positions,
        "harmonic_angles": harmonic_angles,
        "conjunctions": harmonic_conjunctions(placements, request.aspect_orb),
        "chart": chart_text,
        "chart_text": chart_text,
        "result": placements_text,
        "placements_text": placements_text,
        "body_count": len(placements),
        "birth_data": harmonic_birth_data_payload(request, natal_place, birth_utc),
    }


def parse_harmonic_birth_time(value: str | None) -> tuple[int, int, bool]:
    if value is None or not str(value).strip():
        return 12, 0, False

    parts = str(value).strip().split(":")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="birth_time must use HH:MM format.")

    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError as error:
        raise HTTPException(status_code=400, detail="birth_time must use numeric HH:MM format.") from error

    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise HTTPException(status_code=400, detail="birth_time must be a valid 24-hour local time.")

    return hour, minute, True


def normalize_point_name(point: str) -> str:
    return " ".join(str(point or "").replace("_", " ").strip().upper().split())


def resolve_harmonic_birth_location(request: HarmonicChartsRequest) -> PlaceResolution:
    if request.birth_place and request.birth_place.strip():
        try:
            return resolve_birthplace(request.birth_place)
        except HTTPException as error:
            raise HTTPException(
                status_code=error.status_code,
                detail="Unable to geocode birth_place. Please provide latitude, longitude, and timezone.",
            ) from error

    if request.latitude is None or request.longitude is None or not request.timezone:
        raise HTTPException(
            status_code=400,
            detail="The harmonic chart endpoint needs birth_place or latitude, longitude, and timezone.",
        )

    try:
        ZoneInfo(request.timezone)
    except ZoneInfoNotFoundError as error:
        raise HTTPException(status_code=400, detail="Unable to determine timezone for birth location.") from error

    return PlaceResolution(
        query="coordinates",
        birthplace_resolved="Coordinates supplied by request",
        latitude=float(request.latitude),
        longitude=float(request.longitude),
        timezone_name=request.timezone,
    )


def validate_harmonic_request_options(request: HarmonicChartsRequest) -> tuple[str, float, list[int]]:
    response_level = request.response_level.strip().lower()
    if response_level not in {"compact", "standard", "full"}:
        raise HTTPException(status_code=400, detail="response_level must be compact, standard, or full.")

    orb = float(request.orb)
    if orb < 0.5 or orb > 5:
        raise HTTPException(status_code=400, detail="orb must be between 0.5 and 5 degrees.")

    harmonics = request.harmonics or DEFAULT_HARMONIC_NUMBERS
    if not harmonics:
        raise HTTPException(status_code=400, detail="harmonics array must not be empty.")
    if len(harmonics) > MAX_HARMONIC_COUNT:
        raise HTTPException(status_code=400, detail="Too many harmonics requested. Maximum allowed per request is 20.")

    for harmonic_number in harmonics:
        if not isinstance(harmonic_number, int):
            raise HTTPException(status_code=400, detail="harmonics must contain positive integers only.")
        if harmonic_number <= 0:
            raise HTTPException(status_code=400, detail="harmonics must contain positive integers only.")
        if harmonic_number > MAX_HARMONIC_NUMBER:
            raise HTTPException(status_code=400, detail="Harmonic number exceeds maximum allowed value of 360.")

    return response_level, orb, harmonics


def requested_harmonic_points(
    request: HarmonicChartsRequest,
    has_exact_time: bool,
    warnings: list[str],
) -> tuple[list[tuple[str, str]], list[str]]:
    requested_points = request.points or DEFAULT_HARMONIC_POINTS
    planet_points: list[tuple[str, str]] = []
    angle_points: list[str] = []
    seen: set[str] = set()

    for point in requested_points:
        key = normalize_point_name(point)
        if key in PLANET_POINT_ALIASES:
            display_name, source_name = PLANET_POINT_ALIASES[key]
            if display_name not in seen:
                planet_points.append((display_name, source_name))
                seen.add(display_name)
            continue

        if key in ANGLE_POINT_ALIASES:
            angle_name = ANGLE_POINT_ALIASES[key]
            if not has_exact_time:
                continue
            if angle_name not in seen:
                angle_points.append(angle_name)
                seen.add(angle_name)
            continue

        if str(point).strip():
            warnings.append(f"Unsupported point excluded: {point}.")

    if not has_exact_time and any(normalize_point_name(point) in ANGLE_POINT_ALIASES for point in requested_points):
        warnings.append("ASC and MC require exact birth time and birth location. These points were excluded.")

    if not planet_points and not angle_points:
        raise HTTPException(status_code=400, detail="No supported harmonic points were requested.")

    return planet_points, angle_points


def compact_harmonic_position_payload(point: str, longitude: float) -> dict:
    position = zodiac_position(longitude)
    return {
        "point": point,
        "longitude": position["absolute_degree"],
        "position": position["formatted"],
    }


def standard_harmonic_position_payload(
    point: str,
    longitude: float,
    natal_longitude: float | None = None,
    include_natal_reference: bool = False,
) -> dict:
    position = zodiac_position(longitude)
    payload = {
        "point": point,
        "longitude": position["absolute_degree"],
        "sign": position["sign"],
        "degree": position["degree"],
        "minute": position["minute"],
        "second": position["second"],
        "decimal_degree": position["decimal_degree"],
        "position": position["formatted"],
    }
    if include_natal_reference and natal_longitude is not None:
        natal_position = zodiac_position(natal_longitude)
        payload["natal_longitude"] = natal_position["absolute_degree"]
        payload["natal_position"] = natal_position["formatted"]
    return payload


def detect_harmonic_clusters(placements: list[dict], orb: float, harmonic_number: int) -> list[dict]:
    if len(placements) < 2:
        return []

    candidates: list[tuple[frozenset[str], float, list[dict]]] = []
    seen_keys: set[frozenset[str]] = set()
    for seed in placements:
        nearby = [
            placement
            for placement in placements
            if circular_distance(seed["longitude"], placement["longitude"]) <= orb
        ]
        if len(nearby) < 2:
            continue

        center = circular_mean([placement["longitude"] for placement in nearby])
        refined = [
            placement
            for placement in placements
            if circular_distance(center, placement["longitude"]) <= orb
        ]
        if len(refined) < 2:
            continue

        key = frozenset(placement["point"] for placement in refined)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        candidates.append((key, center, refined))

    selected: list[tuple[frozenset[str], float, list[dict]]] = []
    for key, center, members in sorted(candidates, key=lambda item: (-len(item[2]), item[1])):
        if any(key < selected_key for selected_key, _selected_center, _selected_members in selected):
            continue
        selected.append((key, center, members))

    clusters = []
    for index, (_key, center, members) in enumerate(sorted(selected, key=lambda item: item[1]), start=1):
        center_position = zodiac_position(center)
        clusters.append(
            {
                "cluster_id": f"H{harmonic_number}_cluster_{index}",
                "strength": "major" if len(members) >= 3 else "minor",
                "center_longitude": center_position["absolute_degree"],
                "position": center_position["formatted"],
                "orb": orb,
                "members": [
                    {
                        "point": member["point"],
                        "longitude": member["longitude"],
                        "position": member["position"],
                        "orb_from_cluster_center": round(circular_distance(center, member["longitude"]), 6),
                    }
                    for member in sorted(members, key=lambda item: circular_distance(center, item["longitude"]))
                ],
            }
        )
    return clusters


def cluster_source_relationships(cluster: dict, natal_reference: dict[str, dict]) -> list[dict]:
    relationships = []
    members = cluster.get("members", [])
    for first_index, first in enumerate(members):
        for second in members[first_index + 1:]:
            first_natal = natal_reference.get(first["point"])
            second_natal = natal_reference.get(second["point"])
            if not first_natal or not second_natal:
                continue
            separation = circular_distance(first_natal["longitude"], second_natal["longitude"])
            relationships.append(
                {
                    "point_a": first["point"],
                    "point_b": second["point"],
                    "natal_longitude_a": first_natal["longitude"],
                    "natal_longitude_b": second_natal["longitude"],
                    "natal_position_a": first_natal["position"],
                    "natal_position_b": second_natal["position"],
                    "natal_angular_separation": round(separation, 6),
                }
            )
    return relationships


def harmonic_birth_data_summary(
    request: HarmonicChartsRequest,
    place: PlaceResolution,
    hour: int,
    minute: int,
    has_exact_time: bool,
    birth_utc: datetime,
) -> dict:
    return {
        "name": request.name,
        "birth_date": request.birth_date.isoformat(),
        "birth_time": request.birth_time if has_exact_time else None,
        "birth_time_used": f"{hour:02d}:{minute:02d}",
        "birth_time_exact": has_exact_time,
        "birth_place": request.birth_place,
        "resolved_place": place.birthplace_resolved,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "timezone": place.timezone_name,
        "birth_utc": birth_utc.isoformat().replace("+00:00", "Z"),
    }


def harmonic_text_summary(harmonic_charts: list[dict]) -> tuple[str, str]:
    chart_lines = ["VERIFIED_ASTROMEG_HARMONIC_CHART_DATA"]
    placement_chunks = ["SUCCESS | Western harmonic charts calculated"]
    for chart in harmonic_charts:
        placements = chart.get("placements", [])
        chart_lines.append(f"H{chart['harmonic']}: {chart.get('theme', 'Custom harmonic')}")
        chart_lines.extend(
            f"{placement['point']}: {placement['position']}"
            for placement in placements
        )
        placement_chunks.append(
            f"H{chart['harmonic']} body_count={len(placements)} "
            + "; ".join(f"{placement['point']}: {placement['position']}" for placement in placements)
        )
    return "\n".join(chart_lines), " | ".join(placement_chunks)


def calculate_bulk_harmonic_chart_payload(request: HarmonicChartsRequest) -> dict:
    warnings: list[str] = []
    response_level, orb, harmonics = validate_harmonic_request_options(request)
    hour, minute, has_exact_time = parse_harmonic_birth_time(request.birth_time)
    if not has_exact_time:
        warnings.append("Birth time was not supplied. Planetary positions were calculated for 12:00 local time.")

    planet_points, angle_points = requested_harmonic_points(request, has_exact_time, warnings)
    place = resolve_harmonic_birth_location(request)
    birth_utc = local_datetime_to_utc(
        request.birth_date.year,
        request.birth_date.month,
        request.birth_date.day,
        hour,
        minute,
        place.timezone_name,
        "birth",
    )
    natal_jd = datetime_to_julian_day_utc(birth_utc)

    try:
        natal_planets = calculate_planets(natal_jd).model_dump(by_alias=True)
    except HTTPException as error:
        raise HTTPException(
            status_code=error.status_code,
            detail="Natal chart calculation failed. Harmonic chart cannot be calculated without natal longitudes.",
        ) from error

    natal_values: dict[str, float] = {}
    for display_name, source_name in planet_points:
        natal_values[display_name] = normalize_longitude(natal_planets[source_name])

    natal_cusp_values: list[float] = []
    if has_exact_time and (angle_points or request.include_houses):
        _natal_houses, natal_cusp_values, natal_ascendant, natal_midheaven = calculate_houses(
            natal_jd,
            place.latitude,
            place.longitude,
        )
        if "ASC" in angle_points:
            natal_values["ASC"] = normalize_longitude(natal_ascendant)
        if "MC" in angle_points:
            natal_values["MC"] = normalize_longitude(natal_midheaven)
    elif request.include_houses:
        warnings.append("Harmonic houses require exact birth time and location. Houses were not calculated.")

    if request.include_houses and has_exact_time:
        warnings.append("Harmonic houses are experimental. Primary harmonic interpretation should focus on planetary clusters and natal anchoring.")

    natal_reference = {
        point: {
            "point": point,
            "longitude": longitude,
            "position": zodiac_position(longitude)["formatted"],
        }
        for point, longitude in natal_values.items()
    }

    harmonic_charts = []
    include_natal_reference = response_level == "full" or request.include_natal_reference
    for harmonic_number in harmonics:
        chart_theme = get_harmonic_theme(harmonic_number)
        placements = []
        for point, natal_longitude in natal_values.items():
            harmonic_value = calculate_harmonic_longitude(natal_longitude, harmonic_number)
            if response_level == "compact":
                placements.append(compact_harmonic_position_payload(point, harmonic_value))
            else:
                placements.append(
                    standard_harmonic_position_payload(
                        point,
                        harmonic_value,
                        natal_longitude=natal_longitude,
                        include_natal_reference=include_natal_reference,
                    )
                )

        chart_payload = {
            "harmonic": harmonic_number,
            **chart_theme,
            "placements": placements,
        }

        clusters = []
        if request.include_clusters and response_level != "compact":
            clusters = detect_harmonic_clusters(placements, orb, harmonic_number)
            chart_payload["clusters"] = clusters
            if response_level == "full" and not clusters:
                warnings.append("No major harmonic cluster found within selected orb. Interpret this harmonic lightly and return to natal chart.")

        if response_level == "full":
            chart_payload["source_relationships"] = [
                {
                    "cluster_id": cluster["cluster_id"],
                    "relationships": cluster_source_relationships(cluster, natal_reference),
                }
                for cluster in clusters
            ]

        if request.include_houses and has_exact_time and natal_cusp_values:
            chart_payload["harmonic_houses"] = [
                standard_harmonic_position_payload(
                    f"House {index}",
                    calculate_harmonic_longitude(cusp, harmonic_number),
                )
                for index, cusp in enumerate(natal_cusp_values, start=1)
            ]

        harmonic_charts.append(chart_payload)

    settings = {
        "zodiac": ZODIAC,
        "ephemeris": "Swiss Ephemeris",
        "positions": "Geocentric",
        "formula": "(natal_longitude * harmonic_number) % 360",
        "cluster_orb_degrees": orb,
        "houses_default": False,
        "vedic": False,
        "sidereal": False,
    }

    chart_text, placements_text = harmonic_text_summary(harmonic_charts)
    payload = {
        "status": "success",
        "success": True,
        "message": "Western harmonic charts calculated successfully",
        "verified_harmonic_chart": True,
        "verified_chart_data": True,
        "chart_type": "harmonic",
        "response_level": response_level,
        "settings": settings,
        "requested_harmonics": harmonics,
        "harmonic_charts": harmonic_charts,
        "warnings": warnings,
        "chart_text": chart_text,
        "placements_text": placements_text,
        "body_count": sum(len(chart.get("placements", [])) for chart in harmonic_charts),
    }

    if response_level != "compact":
        payload["birth_data"] = harmonic_birth_data_summary(request, place, hour, minute, has_exact_time, birth_utc)

    if include_natal_reference:
        payload["natal_reference"] = list(natal_reference.values())

    return payload


def midpoint_longitude(longitude_a: float, longitude_b: float) -> float:
    return normalize_longitude(longitude_a + signed_longitude_delta(longitude_b, longitude_a) / 2.0)


def geographic_midpoint(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> tuple[float, float]:
    lat_a = math.radians(latitude_a)
    lon_a = math.radians(longitude_a)
    lat_b = math.radians(latitude_b)
    lon_b = math.radians(longitude_b)

    x = math.cos(lat_a) * math.cos(lon_a) + math.cos(lat_b) * math.cos(lon_b)
    y = math.cos(lat_a) * math.sin(lon_a) + math.cos(lat_b) * math.sin(lon_b)
    z = math.sin(lat_a) + math.sin(lat_b)
    hypotenuse = math.hypot(x, y)

    if hypotenuse < 1e-12:
        return ((latitude_a + latitude_b) / 2.0, normalize_longitude((longitude_a + longitude_b) / 2.0))

    midpoint_latitude = math.degrees(math.atan2(z, hypotenuse))
    midpoint_longitude_value = math.degrees(math.atan2(y, x))
    return midpoint_latitude, midpoint_longitude_value


def resolve_relationship_birth_location(person: RelationshipBirthInput) -> PlaceResolution:
    if person.birth_place and person.birth_place.strip():
        return resolve_birthplace(person.birth_place)

    if person.latitude is None or person.longitude is None or not person.timezone:
        raise HTTPException(
            status_code=400,
            detail="Each person needs birth_place or latitude, longitude, and timezone.",
        )

    try:
        ZoneInfo(person.timezone)
    except ZoneInfoNotFoundError as error:
        raise HTTPException(status_code=400, detail="Unable to determine timezone for one birth location.") from error

    return PlaceResolution(
        query=person.name or "coordinates",
        birthplace_resolved="Coordinates supplied by request",
        latitude=float(person.latitude),
        longitude=float(person.longitude),
        timezone_name=person.timezone,
    )


def relationship_birth_context(person: RelationshipBirthInput, label: str) -> dict:
    hour, minute, has_exact_time = parse_harmonic_birth_time(person.birth_time)
    if not has_exact_time:
        raise HTTPException(status_code=400, detail=f"{label} birth_time is required for relationship charts.")

    place = resolve_relationship_birth_location(person)
    birth_utc = local_datetime_to_utc(
        person.birth_date.year,
        person.birth_date.month,
        person.birth_date.day,
        hour,
        minute,
        place.timezone_name,
        label,
    )
    jd = datetime_to_julian_day_utc(birth_utc)
    planets = calculate_planets(jd).model_dump(by_alias=True)
    houses, cusp_values, ascendant, midheaven = calculate_houses(jd, place.latitude, place.longitude)
    return {
        "name": person.name,
        "birth_date": person.birth_date.isoformat(),
        "birth_time": f"{hour:02d}:{minute:02d}",
        "birth_place": person.birth_place,
        "place": place,
        "birth_utc": birth_utc,
        "jd": jd,
        "planets": planets,
        "houses": houses,
        "cusp_values": cusp_values,
        "ascendant": normalize_longitude(ascendant),
        "midheaven": normalize_longitude(midheaven),
    }


def relationship_person_summary(context: dict) -> dict:
    place: PlaceResolution = context["place"]
    return {
        "name": context["name"],
        "birth_date": context["birth_date"],
        "birth_time": context["birth_time"],
        "birth_place": context["birth_place"],
        "resolved_place": place.birthplace_resolved,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "timezone": place.timezone_name,
        "birth_utc": context["birth_utc"].isoformat().replace("+00:00", "Z"),
    }


def requested_relationship_points(request: RelationshipChartRequest, warnings: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    planet_points: list[tuple[str, str]] = []
    angle_points: list[str] = []
    seen: set[str] = set()

    for point in request.points:
        key = normalize_point_name(point)
        if key in PLANET_POINT_ALIASES:
            display_name, source_name = PLANET_POINT_ALIASES[key]
            if display_name not in seen:
                planet_points.append((display_name, source_name))
                seen.add(display_name)
            continue
        if key in ANGLE_POINT_ALIASES:
            angle_name = ANGLE_POINT_ALIASES[key]
            if angle_name not in seen:
                angle_points.append(angle_name)
                seen.add(angle_name)
            continue
        if str(point).strip():
            warnings.append(f"Unsupported point excluded: {point}.")

    if not planet_points and not angle_points:
        raise HTTPException(status_code=400, detail="No supported relationship chart points were requested.")
    return planet_points, angle_points


def house_cusps_from_longitudes(cusp_values: list[float]) -> list[HouseCuspResponse]:
    return [
        HouseCuspResponse(
            house=index,
            sign=zodiac_sign(cusp),
            degree=zodiac_degree(cusp),
            absolute_degree=normalize_longitude(cusp),
        )
        for index, cusp in enumerate(cusp_values, start=1)
    ]


def relationship_placement(body: str, longitude: float, cusp_values: list[float] | None = None) -> dict:
    house = house_for_degree(longitude, cusp_values) if cusp_values else None
    return named_position_payload(body, longitude, house=house)


def relationship_text_summary(chart_type: str, placements: list[dict]) -> tuple[str, str]:
    prefix = "VERIFIED_ASTROMEG_COMPOSITE_CHART_DATA" if chart_type == "composite" else "VERIFIED_ASTROMEG_DAVISON_CHART_DATA"
    formatted = "\n".join(f"{placement['body']}: {placement['formatted']}" for placement in placements)
    placements_text = "; ".join(f"{placement['body']}: {placement['formatted']}" for placement in placements)
    return f"{prefix}\n{formatted}", f"SUCCESS | {chart_type.title()} chart calculated | body_count={len(placements)} | {placements_text}"


def relationship_settings(method: str) -> dict:
    return {
        "zodiac": ZODIAC,
        "houses": HOUSE_SYSTEM,
        "ephemeris": "Swiss Ephemeris",
        "positions": "Geocentric",
        "method": method,
    }


def calculate_composite_chart_payload(request: RelationshipChartRequest) -> dict:
    warnings: list[str] = []
    person_a = relationship_birth_context(request.person_a, "person_a")
    person_b = relationship_birth_context(request.person_b, "person_b")
    planet_points, angle_points = requested_relationship_points(request, warnings)

    composite_values: dict[str, float] = {}
    for display_name, source_name in planet_points:
        composite_values[display_name] = midpoint_longitude(
            person_a["planets"][source_name],
            person_b["planets"][source_name],
        )
    if "ASC" in angle_points:
        composite_values["ASC"] = midpoint_longitude(person_a["ascendant"], person_b["ascendant"])
    if "MC" in angle_points:
        composite_values["MC"] = midpoint_longitude(person_a["midheaven"], person_b["midheaven"])

    composite_cusp_values: list[float] = []
    if request.include_houses:
        composite_cusp_values = [
            midpoint_longitude(cusp_a, cusp_b)
            for cusp_a, cusp_b in zip(person_a["cusp_values"], person_b["cusp_values"])
        ]
        warnings.append("Composite houses are midpoint-derived reference cusps. Do not treat them as an independently timed event chart.")

    placements = [
        relationship_placement(body, longitude, composite_cusp_values if request.include_houses else None)
        for body, longitude in composite_values.items()
    ]
    houses = [house_payload(cusp) for cusp in house_cusps_from_longitudes(composite_cusp_values)] if composite_cusp_values else []
    angles = {
        "ascendant": angle_payload("Ascendant", composite_values["ASC"]) if "ASC" in composite_values else None,
        "midheaven": angle_payload("Midheaven", composite_values["MC"]) if "MC" in composite_values else None,
    }
    chart_text, placements_text = relationship_text_summary("composite", placements)

    return {
        "status": "success",
        "success": True,
        "message": "Composite chart calculated successfully",
        "verified_relationship_chart": True,
        "verified_composite_chart": True,
        "chart_type": "composite",
        "method": "Midpoint Composite: each natal ecliptic longitude is combined by circular midpoint.",
        "settings": relationship_settings("Circular midpoint of two natal charts"),
        "birth_data": {
            "person_a": relationship_person_summary(person_a),
            "person_b": relationship_person_summary(person_b),
        },
        "calculation_data": {
            "midpoint_method": "shortest-arc circular midpoint",
            "houses_included": bool(composite_cusp_values),
        },
        "placements": placements,
        "angles": angles,
        "houses": houses,
        "warnings": warnings,
        "chart": chart_text,
        "chart_text": chart_text,
        "result": placements_text,
        "placements_text": placements_text,
        "body_count": len(placements),
    }


def calculate_davison_chart_payload(request: RelationshipChartRequest) -> dict:
    warnings: list[str] = []
    person_a = relationship_birth_context(request.person_a, "person_a")
    person_b = relationship_birth_context(request.person_b, "person_b")
    planet_points, angle_points = requested_relationship_points(request, warnings)
    place_a: PlaceResolution = person_a["place"]
    place_b: PlaceResolution = person_b["place"]

    midpoint_utc = person_a["birth_utc"] + ((person_b["birth_utc"] - person_a["birth_utc"]) / 2)
    midpoint_latitude, midpoint_longitude_value = geographic_midpoint(
        place_a.latitude,
        place_a.longitude,
        place_b.latitude,
        place_b.longitude,
    )
    midpoint_jd = datetime_to_julian_day_utc(midpoint_utc)
    davison_planets = calculate_planets(midpoint_jd).model_dump(by_alias=True)
    houses, cusp_values, ascendant, midheaven = calculate_houses(
        midpoint_jd,
        midpoint_latitude,
        midpoint_longitude_value,
    )

    davison_values: dict[str, float] = {}
    for display_name, source_name in planet_points:
        davison_values[display_name] = normalize_longitude(davison_planets[source_name])
    if "ASC" in angle_points:
        davison_values["ASC"] = normalize_longitude(ascendant)
    if "MC" in angle_points:
        davison_values["MC"] = normalize_longitude(midheaven)

    placements = [
        relationship_placement(body, longitude, cusp_values if request.include_houses else None)
        for body, longitude in davison_values.items()
    ]
    houses_payload = [house_payload(house) for house in houses] if request.include_houses else []
    angles = {
        "ascendant": angle_payload("Ascendant", ascendant) if "ASC" in davison_values else None,
        "midheaven": angle_payload("Midheaven", midheaven) if "MC" in davison_values else None,
    }
    chart_text, placements_text = relationship_text_summary("davison", placements)

    return {
        "status": "success",
        "success": True,
        "message": "Davison chart calculated successfully",
        "verified_relationship_chart": True,
        "verified_davison_chart": True,
        "chart_type": "davison",
        "method": "Davison Relationship Chart: chart cast for midpoint of the two UTC birth times and geographic birth locations.",
        "settings": relationship_settings("Midpoint in time and space, then Swiss Ephemeris event chart"),
        "birth_data": {
            "person_a": relationship_person_summary(person_a),
            "person_b": relationship_person_summary(person_b),
        },
        "calculation_data": {
            "midpoint_utc": midpoint_utc.isoformat().replace("+00:00", "Z"),
            "midpoint_latitude": midpoint_latitude,
            "midpoint_longitude": midpoint_longitude_value,
            "timezone": "UTC",
            "julian_day": midpoint_jd,
            "houses_included": request.include_houses,
        },
        "placements": placements,
        "angles": angles,
        "houses": houses_payload,
        "warnings": warnings,
        "chart": chart_text,
        "chart_text": chart_text,
        "result": placements_text,
        "placements_text": placements_text,
        "body_count": len(placements),
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
        "verified_chart_data": True,
        "chart_text": return_chart.chart_text,
        "result": return_chart.result,
        "placements_text": return_chart.placements_text,
        "body_count": return_chart.body_count,
    }


def progression_context(request: ProgressedChartRequest) -> dict:
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
    return {
        "natal_place": natal_place,
        "target_place": target_place,
        "birth_utc": birth_utc,
        "target_utc": target_utc,
        "target_local": target_local,
        "progressed_utc": progressed_utc,
        "progressed_days_after_birth": progressed_days_after_birth,
        "age_years": age_years,
        "natal_jd": datetime_to_julian_day_utc(birth_utc),
        "progressed_jd": datetime_to_julian_day_utc(progressed_utc),
    }


def birth_data_payload(request: ProgressedChartRequest, natal_place: PlaceResolution, birth_utc: datetime) -> dict:
    return {
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
    }


def progression_data_payload(
    request: ProgressedChartRequest,
    target_utc: datetime,
    target_local: datetime,
    progressed_utc: datetime,
    progressed_days_after_birth: float,
    age_years: float,
    timezone_name: str,
) -> dict:
    progressed_local = progressed_utc.astimezone(ZoneInfo(timezone_name))
    return {
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
    }


def angles_payload(ascendant: float, midheaven: float) -> dict:
    return {
        "ASC": angle_payload("ASC", ascendant),
        "MC": angle_payload("MC", midheaven),
        "DSC": angle_payload("DSC", ascendant + 180.0),
        "IC": angle_payload("IC", midheaven + 180.0),
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
        "angles_method": "Progressed Julian Day Angles",
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
        "verified_chart_data": True,
        "chart_text": progressed_chart.chart_text,
        "result": progressed_chart.result,
        "placements_text": progressed_chart.placements_text,
        "body_count": progressed_chart.body_count,
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
        "angles_method": "Solar Arc in Longitude Angles",
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
        "verified_chart_data": True,
        "chart_text": chart_text,
        "result": placements_text,
        "placements_text": placements_text,
        "body_count": len(progressed_planets),
    }


def calculate_progressed_solar_longitude_payload(request: ProgressedChartRequest) -> dict:
    context = progression_context(request)
    natal_place = context["natal_place"]
    target_place = context["target_place"]
    natal_planets = calculate_planets(context["natal_jd"]).model_dump(by_alias=True)
    progressed_planet_values = calculate_planets(context["progressed_jd"]).model_dump(by_alias=True)
    _natal_houses, natal_cusp_values, natal_ascendant, natal_midheaven = calculate_houses(
        context["natal_jd"],
        natal_place.latitude,
        natal_place.longitude,
    )
    natal_sun_longitude = normalize_longitude(natal_planets["Sun"])
    progressed_sun_longitude = normalize_longitude(progressed_planet_values["Sun"])
    solar_arc = calculate_solar_arc_longitude(natal_sun_longitude, progressed_sun_longitude)
    directed_cusps = directed_house_cusps(natal_cusp_values, solar_arc)
    directed_cusp_values = [cusp.absolute_degree for cusp in directed_cusps]
    placements = [
        PlacementResponse(
            body=body,
            sign=zodiac_sign(absolute_degree),
            degree=zodiac_degree(absolute_degree),
            absolute_degree=absolute_degree,
            house=house_for_degree(absolute_degree, directed_cusp_values),
        )
        for body, absolute_degree in progressed_planet_values.items()
    ]
    placement_items = [placement_payload(placement) for placement in placements]
    directed_cusp_items = [house_payload(cusp) for cusp in directed_cusps]
    chart_text = chart_summary(placements)
    placements_text = placement_summary(placements)

    return {
        "status": "success",
        "success": True,
        "message": "Progressed solar longitude chart calculated successfully",
        "verified_progressed_chart": True,
        "progression_method": "Secondary progressions: planets day-for-year; angles advanced by Solar Arc in longitude.",
        "angles_method": "Solar Arc in longitude",
        "solar_arc_degrees": solar_arc,
        "solar_arc": {
            **arc_position(solar_arc),
            "decimal_degree": solar_arc,
            "absolute_degree": solar_arc,
        },
        "natal_sun_longitude": natal_sun_longitude,
        "natal_sun": zodiac_position(natal_sun_longitude),
        "progressed_sun_longitude": progressed_sun_longitude,
        "progressed_sun": zodiac_position(progressed_sun_longitude),
        "natal_angles": angles_payload(natal_ascendant, natal_midheaven),
        "progressed_angles": angles_payload(
            apply_solar_arc_longitude(natal_ascendant, solar_arc),
            apply_solar_arc_longitude(natal_midheaven, solar_arc),
        ),
        "angles_only_houses_supported": True,
        "house_assignment_method": "Progressed planets assigned to Solar Arc-directed natal Placidus cusps.",
        "progressed_house_cusps": directed_cusp_items,
        "placements": placement_items,
        "progressed_planets": placement_items,
        "verified_chart_data": True,
        "chart": chart_text,
        "result": placements_text,
        "chart_text": chart_text,
        "placements_text": placements_text,
        "body_count": len(placements),
        "birth_data": birth_data_payload(request, natal_place, context["birth_utc"]),
        "progression_data": progression_data_payload(
            request,
            context["target_utc"],
            context["target_local"],
            context["progressed_utc"],
            context["progressed_days_after_birth"],
            context["age_years"],
            target_place.timezone_name,
        ),
        "calculation_location": request.birthplace,
        "calculation_location_resolved": natal_place.birthplace_resolved,
        "calculation_location_latitude": natal_place.latitude,
        "calculation_location_longitude": natal_place.longitude,
        "calculation_location_timezone": natal_place.timezone_name,
        "target_location": request.progression_location or request.birthplace,
        "target_location_resolved": target_place.birthplace_resolved,
        "target_location_latitude": target_place.latitude,
        "target_location_longitude": target_place.longitude,
        "target_location_timezone": target_place.timezone_name,
    }


def calculate_solar_arc_directions_payload(request: ProgressedChartRequest) -> dict:
    context = progression_context(request)
    natal_place = context["natal_place"]
    target_place = context["target_place"]
    natal_planet_values = calculate_planets(context["natal_jd"]).model_dump(by_alias=True)
    progressed_planet_values = calculate_planets(context["progressed_jd"]).model_dump(by_alias=True)
    natal_houses, natal_cusp_values, natal_ascendant, natal_midheaven = calculate_houses(
        context["natal_jd"],
        natal_place.latitude,
        natal_place.longitude,
    )
    natal_sun_longitude = normalize_longitude(natal_planet_values["Sun"])
    progressed_sun_longitude = normalize_longitude(progressed_planet_values["Sun"])
    solar_arc = calculate_solar_arc_longitude(natal_sun_longitude, progressed_sun_longitude)
    directed_cusps = directed_house_cusps(natal_cusp_values, solar_arc)
    directed_cusp_values = [cusp.absolute_degree for cusp in directed_cusps]
    natal_positions = [
        named_position_payload(
            body,
            longitude,
            house_for_degree(longitude, natal_cusp_values),
        )
        for body, longitude in natal_planet_values.items()
    ]
    directed_placements = [
        PlacementResponse(
            body=body,
            sign=zodiac_sign(apply_solar_arc_longitude(longitude, solar_arc)),
            degree=zodiac_degree(apply_solar_arc_longitude(longitude, solar_arc)),
            absolute_degree=apply_solar_arc_longitude(longitude, solar_arc),
            house=house_for_degree(apply_solar_arc_longitude(longitude, solar_arc), directed_cusp_values),
        )
        for body, longitude in natal_planet_values.items()
    ]
    directed_positions = [placement_payload(placement) for placement in directed_placements]
    chart_text = "VERIFIED_ASTROMEG_SOLAR_ARC_DIRECTIONS\n" + "\n".join(
        f"{item['body']}: {item['formatted']}, house {item.get('house')}"
        for item in directed_positions
    )
    placements_text = (
        f"SUCCESS | Solar Arc Directions calculated successfully | body_count={len(directed_positions)} | "
        + "; ".join(
            f"{item['body']}: {item['formatted']}, house {item.get('house')}"
            for item in directed_positions
        )
    )

    return {
        "status": "success",
        "success": True,
        "message": "Solar Arc Directions calculated successfully",
        "verified_solar_arc_directions": True,
        "direction_method": "Solar Arc Directions in longitude",
        "solar_arc_degrees": solar_arc,
        "solar_arc": {
            **arc_position(solar_arc),
            "decimal_degree": solar_arc,
            "absolute_degree": solar_arc,
        },
        "natal_sun_longitude": natal_sun_longitude,
        "natal_sun": zodiac_position(natal_sun_longitude),
        "progressed_sun_longitude": progressed_sun_longitude,
        "progressed_sun": zodiac_position(progressed_sun_longitude),
        "directed_positions": directed_positions,
        "placements": directed_positions,
        "directed_angles": angles_payload(
            apply_solar_arc_longitude(natal_ascendant, solar_arc),
            apply_solar_arc_longitude(natal_midheaven, solar_arc),
        ),
        "directed_house_cusps": [house_payload(cusp) for cusp in directed_cusps],
        "directed_house_assignment_supported": True,
        "directed_house_assignment_method": "Directed bodies assigned to Solar Arc-directed natal Placidus cusps.",
        "natal_positions": natal_positions,
        "natal_angles": angles_payload(natal_ascendant, natal_midheaven),
        "natal_houses": [house_payload(house) for house in natal_houses],
        "birth_data": birth_data_payload(request, natal_place, context["birth_utc"]),
        "progression_data": progression_data_payload(
            request,
            context["target_utc"],
            context["target_local"],
            context["progressed_utc"],
            context["progressed_days_after_birth"],
            context["age_years"],
            target_place.timezone_name,
        ),
        "verified_chart_data": True,
        "chart": chart_text,
        "result": placements_text,
        "chart_text": chart_text,
        "placements_text": placements_text,
        "body_count": len(directed_positions),
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
        "Calculate a tropical Swiss Ephemeris chart. Requires year, month, day, hour, minute, "
        "and birthplace. Uses Placidus by default; send house_system=Regiomontanus or "
        "chart_type=horary for horary."
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
        {
            "name": "house_system",
            "in": "query",
            "required": False,
            "schema": {"type": "string", "example": "Regiomontanus"},
            "description": "Optional house system. Supported values: Placidus, Regiomontanus.",
        },
        {
            "name": "chart_type",
            "in": "query",
            "required": False,
            "schema": {"type": "string", "example": "horary"},
            "description": "Optional chart type. If set to horary and house_system is omitted, Regiomontanus is used.",
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
    validate_access_operation = {
        "summary": "Validate access code",
        "description": (
            "Read-only access-code validation against private Render env codes, Apps Script, published CSV, or Google Sheets API. "
            "Requires Authorization: Bearer <ORACLE_BACKEND_API_KEY>. "
            "Does not write to Google Sheets and does not expose the full code list."
        ),
        "operationId": "validateAccessCode",
        "security": [{"BearerAuth": []}],
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": ACCESS_CODE_REQUEST_SCHEMA}},
        },
        "responses": {
            "200": {
                "description": "Access code validation result.",
                "content": {"application/json": {"schema": ACCESS_CODE_RESPONSE_SCHEMA}},
            },
            "401": {
                "description": "Missing or invalid backend API key.",
                "content": {"application/json": {"schema": ACCESS_CODE_RESPONSE_SCHEMA}},
            },
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
            "Progressed planets are calculated by the day-for-a-year method. "
            "angles_method returns: Progressed Julian Day Angles."
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
            "angles_method returns: Solar Arc in Longitude Angles. "
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
    progressed_solar_longitude_operation = {
        "summary": "Calculate progressed solar longitude chart",
        "description": (
            "Calculate secondary progressed planets by day-for-year, then advance natal ASC, MC, DSC, IC, "
            "and Placidus cusps by Solar Arc in longitude. This endpoint does not calculate angles from "
            "the progressed Julian day."
        ),
        "operationId": "calculate_progressed_solar_longitude_chart",
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": PROGRESSED_CHART_REQUEST_SCHEMA}},
        },
        "responses": {
            "200": {
                "description": "Progressed solar longitude chart result or readable application-level error.",
                "content": {"application/json": {"schema": PROGRESSED_SOLAR_LONGITUDE_CHART_RESPONSE_SCHEMA}},
            },
            "default": {
                "description": "Progressed solar longitude chart request could not be calculated.",
                "content": {"application/json": {"schema": ERROR_SCHEMA}},
            },
        },
    }
    solar_arc_directions_operation = {
        "summary": "Calculate Solar Arc Directions",
        "description": (
            "Calculate Solar Arc Directions in longitude by advancing every natal planet, point, angle, "
            "and available Placidus house cusp by the Solar Arc derived from the secondary progressed Sun."
        ),
        "operationId": "calculate_solar_arc_directions",
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": PROGRESSED_CHART_REQUEST_SCHEMA}},
        },
        "responses": {
            "200": {
                "description": "Solar Arc Directions result or readable application-level error.",
                "content": {"application/json": {"schema": SOLAR_ARC_DIRECTIONS_RESPONSE_SCHEMA}},
            },
            "default": {
                "description": "Solar Arc Directions request could not be calculated.",
                "content": {"application/json": {"schema": ERROR_SCHEMA}},
            },
        },
    }
    harmonic_operation = {
        "summary": "Calculate Western harmonic chart",
        "description": (
            "Calculate a Western tropical harmonic chart using Swiss Ephemeris natal longitudes multiplied "
            "by harmonic_number and normalized to 0-360. This is not a Vedic varga, not sidereal, and does not fabricate houses."
        ),
        "operationId": "calculate_harmonic_chart",
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": HARMONIC_CHART_REQUEST_SCHEMA}},
        },
        "responses": {
            "200": {
                "description": "Western harmonic chart result or readable application-level error.",
                "content": {"application/json": {"schema": HARMONIC_CHART_RESPONSE_SCHEMA}},
            },
            "default": {
                "description": "Harmonic chart request could not be calculated.",
                "content": {"application/json": {"schema": ERROR_SCHEMA}},
            },
        },
    }
    bulk_harmonic_operation = {
        "summary": "Calculate Western harmonic charts",
        "description": (
            "Calculate one or more Western tropical harmonic charts from natal Swiss Ephemeris longitudes. "
            "Harmonic positions are derived with (natal_longitude * harmonic_number) % 360. "
            "No Vedic, sidereal, or long-form interpretation is returned."
        ),
        "operationId": "calculate_harmonic_charts",
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": BULK_HARMONIC_CHART_REQUEST_SCHEMA}},
        },
        "responses": {
            "200": {
                "description": "Western harmonic chart results or readable application-level error.",
                "content": {"application/json": {"schema": BULK_HARMONIC_CHART_RESPONSE_SCHEMA}},
            },
            "default": {
                "description": "Harmonic chart request could not be calculated.",
                "content": {"application/json": {"schema": ERROR_SCHEMA}},
            },
        },
    }
    composite_operation = {
        "summary": "Calculate Composite relationship chart",
        "description": (
            "Calculate a midpoint Composite chart from two natal charts. Each requested natal longitude "
            "is combined by shortest-arc circular midpoint. Tropical zodiac and Swiss Ephemeris natal positions only."
        ),
        "operationId": "calculate_composite_chart",
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": RELATIONSHIP_CHART_REQUEST_SCHEMA}},
        },
        "responses": {
            "200": {
                "description": "Composite chart result or readable application-level error.",
                "content": {"application/json": {"schema": RELATIONSHIP_CHART_RESPONSE_SCHEMA}},
            },
            "default": {
                "description": "Composite chart request could not be calculated.",
                "content": {"application/json": {"schema": ERROR_SCHEMA}},
            },
        },
    }
    davison_operation = {
        "summary": "Calculate Davison relationship chart",
        "description": (
            "Calculate a Davison Relationship Chart by finding the midpoint UTC time and geographic midpoint "
            "between two births, then casting a Tropical Placidus chart with Swiss Ephemeris."
        ),
        "operationId": "calculate_davison_chart",
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": RELATIONSHIP_CHART_REQUEST_SCHEMA}},
        },
        "responses": {
            "200": {
                "description": "Davison chart result or readable application-level error.",
                "content": {"application/json": {"schema": RELATIONSHIP_CHART_RESPONSE_SCHEMA}},
            },
            "default": {
                "description": "Davison chart request could not be calculated.",
                "content": {"application/json": {"schema": ERROR_SCHEMA}},
            },
        },
    }

    schema["openapi"] = "3.1.0"
    schema["paths"] = {
        "/validate-access-code": {"post": validate_access_operation},
        "/chart": {"get": chart_operation},
        "/calculate_solar_return": {"post": solar_operation},
        "/calculate_progressed_chart": {"post": progressed_operation},
        "/calculate_progressed_chart_solar_arc_angles": {"post": progressed_solar_arc_angles_operation},
        "/calculate_progressed_solar_longitude_chart": {"post": progressed_solar_longitude_operation},
        "/calculate_solar_arc_directions": {"post": solar_arc_directions_operation},
        "/calculate_harmonic_chart": {"post": harmonic_operation},
        "/api/charts/harmonic": {"post": bulk_harmonic_operation},
        "/api/charts/composite": {"post": composite_operation},
        "/api/charts/davison": {"post": davison_operation},
    }
    schema.pop("components", None)
    schema["components"] = {
        "schemas": {},
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": "Use ORACLE_BACKEND_API_KEY as the bearer token.",
            }
        }
    }
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


def json_response(content: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=content)


def authorized_backend_request(request: Request) -> bool:
    expected_token = os.environ.get("ORACLE_BACKEND_API_KEY", "").strip()
    authorization = request.headers.get("Authorization", "")
    prefix = "Bearer "

    if not expected_token or not authorization.startswith(prefix):
        return False

    supplied_token = authorization[len(prefix):].strip()
    return hmac.compare_digest(supplied_token, expected_token)


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


@app.post(
    "/validate-access-code",
    response_model=AccessCodeValidationResponse,
    operation_id="validateAccessCode",
    description="Validate a user access code against the configured Google Sheet in read-only mode.",
    responses={
        200: {"description": "Access code validation result.", "content": {"application/json": {"schema": ACCESS_CODE_RESPONSE_SCHEMA}}},
        401: {"description": "Missing or invalid backend API key.", "content": {"application/json": {"schema": ACCESS_CODE_RESPONSE_SCHEMA}}},
    },
)
def validate_access_code(payload: AccessCodeValidationRequest, request: Request):
    if not authorized_backend_request(request):
        return json_response(
            access_response(False, "ERROR", "Unauthorized."),
            status_code=401,
        )

    cached_result = get_cached_access_response(payload.access_code)
    if cached_result is not None:
        return json_response(cached_result)

    try:
        try:
            external_result = validate_access_code_with_external_service(payload.access_code)
        except Exception as error:
            logger.warning("external access validation unavailable; trying row source error=%s", error)
            external_result = None

        if external_result is not None:
            logger.info("access code external validation status=%s valid=%s", external_result.get("status"), external_result.get("valid"))
            cache_access_response(payload.access_code, external_result)
            return json_response(external_result)

        rows = fetch_access_sheet_rows()
        result = validate_access_code_from_rows(payload.access_code, rows)
        logger.info("access code validation status=%s valid=%s", result.get("status"), result.get("valid"))
        cache_access_response(payload.access_code, result)
        return json_response(result)
    except Exception as error:
        logger.exception("access code validation unavailable error=%s", error)
        cached_result = get_cached_access_response(payload.access_code)
        if cached_result is not None:
            cached_result["message"] = "Access confirmed from recent validation cache."
            cached_result["validation_source"] = "render_cache"
            return json_response(cached_result)
        return json_response(
            access_response(False, "ERROR", "Access validation is temporarily unavailable. Please try again.")
        )


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
        "Calculate a tropical chart with selectable houses using Swiss Ephemeris. "
        "Required query parameters are year, month, day, hour, minute, and birthplace. "
        "Horary requests default to Regiomontanus houses."
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
    house_system: Annotated[
        Optional[str],
        Query(description="House system to use. Supported: Placidus, Regiomontanus."),
    ] = None,
    chart_type: Annotated[
        Optional[str],
        Query(description="Optional chart type. If set to horary and house_system is omitted, Regiomontanus is used."),
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
    house_system_name, _house_system_code = resolve_house_system(house_system, chart_type)

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
        house_system=house_system_name,
    )
    payload = action_chart_payload(chart)
    payload["chart_type"] = chart_type or "natal"
    payload["house_system"] = house_system_name
    return json_response(payload)


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


@app.post(
    "/calculate_progressed_solar_longitude_chart",
    operation_id="calculate_progressed_solar_longitude_chart",
    description=(
        "Calculate secondary progressed planets with Solar Arc in longitude angles and cusps."
    ),
    responses={
        200: {
            "description": "Progressed solar longitude chart result.",
            "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}},
        },
    },
)
def calculate_progressed_solar_longitude_chart(request: ProgressedChartRequest):
    logger.info(
        "progressed solar longitude chart start birthplace=%s target=%s-%s-%s target_location=%s",
        request.birthplace,
        request.progression_year,
        request.progression_month,
        request.progression_day,
        request.progression_location or request.birthplace,
    )
    payload = calculate_progressed_solar_longitude_payload(request)
    logger.info(
        "progressed solar longitude chart complete solar_arc=%.8f body_count=%s",
        payload.get("solar_arc_degrees"),
        payload.get("body_count"),
    )
    return json_response(payload)


@app.post(
    "/calculate_solar_arc_directions",
    operation_id="calculate_solar_arc_directions",
    description="Calculate Solar Arc Directions in longitude for natal planets, points, angles, and cusps.",
    responses={
        200: {
            "description": "Solar Arc Directions result.",
            "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}},
        },
    },
)
def calculate_solar_arc_directions(request: ProgressedChartRequest):
    logger.info(
        "solar arc directions start birthplace=%s target=%s-%s-%s target_location=%s",
        request.birthplace,
        request.progression_year,
        request.progression_month,
        request.progression_day,
        request.progression_location or request.birthplace,
    )
    payload = calculate_solar_arc_directions_payload(request)
    logger.info(
        "solar arc directions complete solar_arc=%.8f body_count=%s",
        payload.get("solar_arc_degrees"),
        payload.get("body_count"),
    )
    return json_response(payload)


@app.post(
    "/calculate_harmonic_chart",
    operation_id="calculate_harmonic_chart",
    description="Calculate a Western tropical harmonic chart from natal Swiss Ephemeris longitudes.",
    responses={
        200: {
            "description": "Western harmonic chart result.",
            "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}},
        },
    },
)
def calculate_harmonic_chart(request: HarmonicChartRequest):
    logger.info(
        "harmonic chart start birthplace=%s harmonic=H%s",
        request.birthplace,
        request.harmonic_number,
    )
    payload = calculate_harmonic_chart_payload(request)
    logger.info(
        "harmonic chart complete harmonic=H%s body_count=%s conjunctions=%s",
        request.harmonic_number,
        payload.get("body_count"),
        len(payload.get("conjunctions", [])),
    )
    return json_response(payload)


@app.post(
    "/api/charts/harmonic",
    operation_id="calculate_harmonic_charts",
    description="Calculate one or more Western tropical harmonic charts from natal Swiss Ephemeris longitudes.",
    responses={
        200: {
            "description": "Western harmonic charts result.",
            "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}},
        },
    },
)
def calculate_harmonic_charts(request: HarmonicChartsRequest):
    logger.info(
        "bulk harmonic charts start birth_place=%s harmonics=%s response_level=%s",
        request.birth_place,
        request.harmonics,
        request.response_level,
    )
    payload = calculate_bulk_harmonic_chart_payload(request)
    logger.info(
        "bulk harmonic charts complete harmonics=%s body_count=%s warnings=%s",
        payload.get("requested_harmonics"),
        payload.get("body_count"),
        len(payload.get("warnings", [])),
    )
    return json_response(payload)


@app.post(
    "/api/charts/composite",
    operation_id="calculate_composite_chart",
    description="Calculate a midpoint Composite relationship chart from two natal charts.",
    responses={
        200: {
            "description": "Composite relationship chart result.",
            "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}},
        },
    },
)
def calculate_composite_chart(request: RelationshipChartRequest):
    logger.info(
        "composite chart start person_a=%s person_b=%s",
        request.person_a.birth_place or request.person_a.name,
        request.person_b.birth_place or request.person_b.name,
    )
    payload = calculate_composite_chart_payload(request)
    logger.info("composite chart complete body_count=%s", payload.get("body_count"))
    return json_response(payload)


@app.post(
    "/api/charts/davison",
    operation_id="calculate_davison_chart",
    description="Calculate a Davison relationship chart from midpoint time and midpoint location.",
    responses={
        200: {
            "description": "Davison relationship chart result.",
            "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}},
        },
    },
)
def calculate_davison_chart(request: RelationshipChartRequest):
    logger.info(
        "davison chart start person_a=%s person_b=%s",
        request.person_a.birth_place or request.person_a.name,
        request.person_b.birth_place or request.person_b.name,
    )
    payload = calculate_davison_chart_payload(request)
    logger.info("davison chart complete body_count=%s", payload.get("body_count"))
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
