import swisseph as swe
swe.set_ephe_path("ephe")
# ----------------------------
# USER INPUT
# ----------------------------

year = 1972
month = 7
day = 31

hour = 22
minute = 50

timezone = 8

latitude = 14.6760
longitude = 121.0437

# ----------------------------
# TIME CONVERSION
# ----------------------------

hour_utc = hour + minute / 60 - timezone

jd = swe.julday(year, month, day, hour_utc)

# ----------------------------
# ZODIAC SIGNS
# ----------------------------

signs = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

def zodiac_position(longitude):
    sign_index = int(longitude // 30)
    degree = longitude % 30
    return f"{degree:.2f}° {signs[sign_index]}"

# ----------------------------
# PLANETS
# ----------------------------

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
# ----------------------------
# HOUSES (PLACIDUS)
# ----------------------------

houses, ascmc = swe.houses(jd, latitude, longitude, b'P')

ascendant = ascmc[0]
midheaven = ascmc[1]
sun_long = swe.calc_ut(jd, swe.SUN)[0][0]
moon_long = swe.calc_ut(jd, swe.MOON)[0][0]
vertex = ascmc[3]
# ----------------------------
# PART OF FORTUNE — DAY/NIGHT FORMULA
# ----------------------------

# Sun above horizon = day chart
# Houses 7 to 12 are above the horizon in this setup
sun_house = None

for i in range(12):
    start = houses[i]
    end = houses[(i + 1) % 12]

    if end < start:
        end += 360

    sun_check = sun_long
    if sun_check < start:
        sun_check += 360

    if start <= sun_check < end:
        sun_house = i + 1
        break

is_day_chart = sun_house in [7, 8, 9, 10, 11, 12]

if is_day_chart:
    pof = ascendant + moon_long - sun_long
else:
    pof = ascendant + sun_long - moon_long

pof = pof % 360
# ----------------------------
# OUTPUT
# ----------------------------

print("\nASTROMEG ORACLE V3\n")

print("ASC :", zodiac_position(ascendant))
print("MC  :", zodiac_position(midheaven))
print("POF :", zodiac_position(pof))
print("Vertex:", zodiac_position(vertex))
print("\nPLANETS + POINTS\n")

for name, planet in planets.items():

    result = swe.calc_ut(jd, planet)
    longitude = result[0][0]

    print(f"{name}: {zodiac_position(longitude)}")

# ----------------------------
# FIXED STARS
# ----------------------------

print("\nFIXED STARS\n")

fixed_stars = [
    "Regulus",
    "Spica",
    "Sirius",
    "Algol",
    "Aldebaran",
    "Antares",
    "Fomalhaut"
]

for star in fixed_stars:

    star_data = swe.fixstar_ut(star, jd)

    star_longitude = star_data[0][0]

    print(f"{star}: {zodiac_position(star_longitude)}")
