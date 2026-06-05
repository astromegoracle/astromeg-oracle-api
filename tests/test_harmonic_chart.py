import unittest

from fastapi import HTTPException
from pydantic import ValidationError

import app


class HarmonicChartMathTests(unittest.TestCase):
    def test_harmonic_longitude_normalizes_across_zero_aries(self):
        self.assertAlmostEqual(app.harmonic_longitude(181.0, 2), 2.0)
        self.assertAlmostEqual(app.harmonic_longitude(359.5, 24), 348.0)
        self.assertAlmostEqual(app.calculate_harmonic_longitude(80.0, 5), 40.0)
        self.assertAlmostEqual(app.calculate_harmonic_longitude(359.0, 2), 358.0)
        self.assertAlmostEqual(app.calculate_harmonic_longitude(181.0, 8), 8.0)

    def test_normalize_degrees(self):
        self.assertAlmostEqual(app.normalize_degrees(400.0), 40.0)
        self.assertAlmostEqual(app.normalize_degrees(-10.0), 350.0)

    def test_angular_separation_uses_shortest_arc(self):
        self.assertAlmostEqual(app.angular_separation(359.0, 1.0), 2.0)
        self.assertAlmostEqual(app.circular_distance(10.0, 350.0), 20.0)

    def test_longitude_to_sign_degree(self):
        taurus = app.longitude_to_sign_degree(40.0)
        aquarius = app.longitude_to_sign_degree(306.0)

        self.assertEqual(taurus["sign"], "Taurus")
        self.assertEqual(taurus["degree"], 10)
        self.assertEqual(taurus["minute"], 0)
        self.assertEqual(aquarius["sign"], "Aquarius")
        self.assertEqual(aquarius["degree"], 6)


class HarmonicChartEndpointTests(unittest.TestCase):
    def request(self, harmonic_number=24):
        return app.HarmonicChartRequest(
            birth_year=1972,
            birth_month=7,
            birth_day=31,
            birth_hour=22,
            birth_minute=50,
            birthplace="Quezon City, Philippines",
            harmonic_number=harmonic_number,
            aspect_orb=2.0,
        )

    def test_harmonic_number_is_required_and_positive(self):
        with self.assertRaises(ValidationError):
            app.HarmonicChartRequest(
                birth_year=1972,
                birth_month=7,
                birth_day=31,
                birth_hour=22,
                birth_minute=50,
                birthplace="Quezon City, Philippines",
                harmonic_number=0,
            )

    def test_harmonic_payload_is_western_tropical_only(self):
        payload = app.calculate_harmonic_chart_payload(self.request(24))

        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["success"])
        self.assertTrue(payload["verified_harmonic_chart"])
        self.assertEqual(payload["harmonic_number"], 24)
        self.assertEqual(payload["zodiac"], "Tropical")
        self.assertFalse(payload["houses_supported"])
        self.assertGreater(payload["body_count"], 0)
        self.assertNotIn("Vedic", payload["method"])
        self.assertNotIn("sidereal", payload["method"].lower())

    def test_harmonic_placements_equal_natal_longitude_times_harmonic(self):
        harmonic_number = 9
        payload = app.calculate_harmonic_chart_payload(self.request(harmonic_number))

        for placement in payload["placements"]:
            expected = app.harmonic_longitude(placement["natal_absolute_degree"], harmonic_number)
            self.assertAlmostEqual(placement["absolute_degree"], expected)

    def test_response_has_action_friendly_text_fields(self):
        payload = app.calculate_harmonic_chart_payload(self.request(12))

        self.assertTrue(payload["chart_text"].startswith("VERIFIED_ASTROMEG_HARMONIC_CHART_DATA"))
        self.assertIn("SUCCESS", payload["placements_text"])
        self.assertEqual(payload["body_count"], len(payload["placements"]))


class BulkHarmonicChartEndpointTests(unittest.TestCase):
    def test_bulk_endpoint_default_harmonics(self):
        payload = app.calculate_bulk_harmonic_chart_payload(
            app.HarmonicChartsRequest(
                birth_date="1972-07-31",
                birth_time="22:50",
                birth_place="Quezon City, Philippines",
                harmonics=[5, 8, 10, 11],
            )
        )

        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["chart_type"], "harmonic")
        self.assertEqual(len(payload["harmonic_charts"]), 4)
        for chart in payload["harmonic_charts"]:
            self.assertIn("theme", chart)
            self.assertGreater(len(chart["placements"]), 0)

    def test_bulk_endpoint_custom_harmonic_theme(self):
        payload = app.calculate_bulk_harmonic_chart_payload(
            app.HarmonicChartsRequest(
                birth_date="1972-07-31",
                birth_time="22:50",
                birth_place="Quezon City, Philippines",
                harmonics=[13],
            )
        )
        chart = payload["harmonic_charts"][0]

        self.assertEqual(chart["harmonic"], 13)
        self.assertEqual(chart["theme"], "Custom harmonic")
        self.assertIn("theme_note", chart)

    def test_bulk_endpoint_rejects_too_many_harmonics(self):
        with self.assertRaises(HTTPException) as context:
            app.calculate_bulk_harmonic_chart_payload(
                app.HarmonicChartsRequest(
                    birth_date="1972-07-31",
                    birth_time="22:50",
                    birth_place="Quezon City, Philippines",
                    harmonics=list(range(1, 22)),
                )
            )

        self.assertIn("Too many harmonics", context.exception.detail)

    def test_missing_birth_time_excludes_angles(self):
        payload = app.calculate_bulk_harmonic_chart_payload(
            app.HarmonicChartsRequest(
                birth_date="1972-07-31",
                birth_place="Quezon City, Philippines",
                harmonics=[5],
                points=["Sun", "ASC", "MC"],
            )
        )
        points = {placement["point"] for placement in payload["harmonic_charts"][0]["placements"]}

        self.assertEqual(payload["status"], "success")
        self.assertIn("Sun", points)
        self.assertNotIn("ASC", points)
        self.assertNotIn("MC", points)
        self.assertTrue(any("ASC and MC require exact birth time" in warning for warning in payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
