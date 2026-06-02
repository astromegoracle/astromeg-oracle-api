import unittest

from pydantic import ValidationError

import app


class SolarArcMathTests(unittest.TestCase):
    def test_solar_arc_crossing_zero_aries_normalization(self):
        self.assertAlmostEqual(app.calculate_solar_arc_longitude(358.0, 2.0), 4.0)

    def test_natal_asc_plus_solar_arc_normalization(self):
        self.assertAlmostEqual(app.apply_solar_arc_longitude(358.0, 4.0), 2.0)

    def test_mc_plus_solar_arc_normalization(self):
        self.assertAlmostEqual(app.apply_solar_arc_longitude(359.0, 5.0), 4.0)

    def test_directed_planet_equals_natal_longitude_plus_solar_arc(self):
        natal_longitude = 123.456789
        solar_arc = 52.194991
        self.assertAlmostEqual(
            app.apply_solar_arc_longitude(natal_longitude, solar_arc),
            (natal_longitude + solar_arc) % 360.0,
        )


class ProgressedSolarArcEndpointTests(unittest.TestCase):
    def request(self):
        return app.ProgressedChartRequest(
            birth_year=1972,
            birth_month=7,
            birth_day=31,
            birth_hour=22,
            birth_minute=50,
            birthplace="Quezon City, Philippines",
            progression_year=2026,
            progression_month=8,
            progression_day=1,
            progression_hour=12,
            progression_minute=0,
            progression_location="Quezon City, Philippines",
        )

    def test_birthplace_is_required(self):
        with self.assertRaises(ValidationError):
            app.ProgressedChartRequest(
                birth_year=1972,
                birth_month=7,
                birth_day=31,
                birth_hour=22,
                birth_minute=50,
                progression_year=2026,
                progression_month=8,
                progression_day=1,
            )

    def test_progressed_solar_longitude_chart_verified_output(self):
        payload = app.calculate_progressed_solar_longitude_payload(self.request())
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["success"])
        self.assertTrue(payload["verified_progressed_chart"])
        self.assertGreater(payload["body_count"], 0)

    def test_solar_arc_directions_verified_output(self):
        payload = app.calculate_solar_arc_directions_payload(self.request())
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["success"])
        self.assertTrue(payload["verified_solar_arc_directions"])
        self.assertTrue(payload["verified_chart_data"])
        self.assertEqual(payload["placements"], payload["directed_positions"])
        self.assertTrue(payload["chart"].startswith("VERIFIED_ASTROMEG_SOLAR_ARC_DIRECTIONS"))
        self.assertIn("SUCCESS", payload["result"])
        self.assertGreater(payload["body_count"], 0)

    def test_solar_arc_equals_progressed_sun_minus_natal_sun(self):
        payload = app.calculate_solar_arc_directions_payload(self.request())
        expected = app.calculate_solar_arc_longitude(
            payload["natal_sun_longitude"],
            payload["progressed_sun_longitude"],
        )
        self.assertAlmostEqual(payload["solar_arc_degrees"], expected)

    def test_directed_planets_equal_natal_plus_solar_arc(self):
        payload = app.calculate_solar_arc_directions_payload(self.request())
        solar_arc = payload["solar_arc_degrees"]
        natal_by_body = {item["body"]: item for item in payload["natal_positions"]}
        directed_by_body = {item["body"]: item for item in payload["directed_positions"]}

        for body, natal_position in natal_by_body.items():
            expected = app.apply_solar_arc_longitude(natal_position["absolute_degree"], solar_arc)
            self.assertAlmostEqual(directed_by_body[body]["absolute_degree"], expected)


if __name__ == "__main__":
    unittest.main()
