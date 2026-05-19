from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim
import os
from pathlib import Path
import swisseph as swe
from timezonefinder import TimezoneFinder
from typing import Annotated
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent
EPHE_PATH = BASE_DIR / "ephe"
EPHE_FILES = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")
os.environ["SE_EPHE_PATH"] = str(EPHE_PATH)
swe.set_ephe_path(str(EPHE_PATH))
GEOCODER = Nominatim(user_agent="astromeg-oracle-api")
TIMEZONE_FINDER = TimezoneFinder()

app = FastAPI(
    title="Astromeg Oracle Swiss Ephemeris API",
    servers=[
        {"url": "https://astromeg-oracle-api.onrender.com"},
    ],
)

@app.get("/")
def home():
    return {"status": "Astromeg Oracle API Running"}

@app.get("/ephe-status")
def ephe_status():
    return {
        "cwd": os.getcwd(),
        "base_dir": str(BASE_DIR),
        "ephe_path": str(EPHE_PATH),
        "se_ephe_path": os.environ.get("SE_EPHE_PATH"),
        "files": {
            filename: (EPHE_PATH / filename).is_file()
            for filename in EPHE_FILES
        },
    }

@app.get(
    "/chart",
    description=(
        "Calculate a natal chart using either "
        "year, month, day, hour, minute, timezone, latitude, longitude "
        "or year, month, day, hour, minute, birthplace."
    ),
)
def calculate_chart(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    timezone: Annotated[
        float | None,
        Query(
            description="UTC offset in hours. Required with latitude and longitude. Omit when using birthplace.",
        ),
    ] = None,
    latitude: Annotated[
        float | None,
        Query(
            description="Birth latitude in decimal degrees. Required with longitude and timezone unless birthplace is provided.",
        ),
    ] = None,
    longitude: Annotated[
        float | None,
        Query(
            description="Birth longitude in decimal degrees. Required with latitude and timezone unless birthplace is provided.",
        ),
    ] = None,
    birthplace: Annotated[
        str | None,
        Query(
            description="Birthplace to geocode. When provided, latitude, longitude, and timezone are resolved automatically.",
        ),
    ] = None,
):
    if birthplace:
        try:
            location = GEOCODER.geocode(birthplace, exactly_one=True, timeout=10)
        except (GeocoderServiceError, GeocoderTimedOut) as e:
            raise HTTPException(status_code=502, detail=f"Geocoder unavailable: {e}") from e

        if location is None:
            raise HTTPException(status_code=400, detail=f"Could not geocode birthplace: {birthplace}")

        latitude = location.latitude
        longitude = location.longitude
        timezone_name = TIMEZONE_FINDER.timezone_at(lat=latitude, lng=longitude)
        if timezone_name is None:
            raise HTTPException(status_code=400, detail=f"Could not determine timezone for birthplace: {birthplace}")

        try:
            birth_datetime = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(timezone_name))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        utc_offset = birth_datetime.utcoffset()
        if utc_offset is None:
            raise HTTPException(status_code=400, detail=f"Could not determine UTC offset for timezone: {timezone_name}")

        timezone = utc_offset.total_seconds() / 3600
    elif timezone is None or latitude is None or longitude is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Provide either year, month, day, hour, minute, timezone, latitude, longitude "
                "or year, month, day, hour, minute, birthplace."
            ),
        )

    utc_hour = hour - timezone + (minute / 60)
    jd = swe.julday(year, month, day, utc_hour)

    planets = {
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
        "Chiron": swe.CHIRON,
        "North Node": swe.TRUE_NODE,
        "Lilith": swe.MEAN_APOG,
    }

    results = {}

    for name, planet in planets.items():
        try:
            position, _flags = swe.calc_ut(jd, planet)
            results[name] = position[0]
        except Exception as e:
            results[name] = f"ERROR: {str(e)}"

    return results
