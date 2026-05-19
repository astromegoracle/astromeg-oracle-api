from fastapi import FastAPI
import swisseph as swe

EPHE_PATH = "ephe"
swe.set_ephe_path(EPHE_PATH)

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Astromeg Oracle API Running"}

@app.get("/chart")
def calculate_chart(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    timezone: float,
    latitude: float,
    longitude: float
):

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
