import unittest

import app


def relationship_request(points=None, include_houses=True):
    return app.RelationshipChartRequest(
        person_a={
            "name": "Person A",
            "birth_date": "1972-07-31",
            "birth_time": "22:50",
            "birth_place": "Quezon City, Philippines",
        },
        person_b={
            "name": "Person B",
            "birth_date": "1993-12-06",
            "birth_time": "14:10",
            "birth_place": "Quezon City, Philippines",
        },
        points=points
        or [
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
        ],
        include_houses=include_houses,
    )


class RelationshipChartMathTests(unittest.TestCase):
    def test_midpoint_longitude_wraps_across_zero_aries(self):
        self.assertAlmostEqual(app.midpoint_longitude(350.0, 10.0), 0.0)
        self.assertAlmostEqual(app.midpoint_longitude(10.0, 350.0), 0.0)

    def test_geographic_midpoint_same_place(self):
        latitude, longitude = app.geographic_midpoint(14.676, 121.0437, 14.676, 121.0437)

        self.assertAlmostEqual(latitude, 14.676, places=6)
        self.assertAlmostEqual(longitude, 121.0437, places=6)


class RelationshipChartPayloadTests(unittest.TestCase):
    def test_composite_payload_success(self):
        payload = app.calculate_composite_chart_payload(relationship_request())

        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["verified_composite_chart"])
        self.assertEqual(payload["chart_type"], "composite")
        self.assertGreater(payload["body_count"], 0)
        self.assertTrue(payload["chart_text"].startswith("VERIFIED_ASTROMEG_COMPOSITE_CHART_DATA"))
        self.assertIn("person_a", payload["birth_data"])
        self.assertGreater(len(payload["houses"]), 0)

    def test_davison_payload_success(self):
        payload = app.calculate_davison_chart_payload(relationship_request())

        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["verified_davison_chart"])
        self.assertEqual(payload["chart_type"], "davison")
        self.assertGreater(payload["body_count"], 0)
        self.assertTrue(payload["chart_text"].startswith("VERIFIED_ASTROMEG_DAVISON_CHART_DATA"))
        self.assertIn("midpoint_utc", payload["calculation_data"])
        self.assertGreater(len(payload["houses"]), 0)

    def test_unsupported_points_are_warned(self):
        payload = app.calculate_composite_chart_payload(
            relationship_request(points=["Sun", "Imaginary Point"], include_houses=False)
        )

        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["body_count"], 1)
        self.assertTrue(any("Unsupported point excluded" in warning for warning in payload["warnings"]))

    def test_openapi_has_relationship_paths(self):
        app.app.openapi_schema = None
        schema = app.custom_openapi()

        self.assertIn("/api/charts/composite", schema["paths"])
        self.assertIn("/api/charts/davison", schema["paths"])
        self.assertEqual(schema["paths"]["/api/charts/composite"]["post"]["operationId"], "calculate_composite_chart")
        self.assertEqual(schema["paths"]["/api/charts/davison"]["post"]["operationId"], "calculate_davison_chart")


if __name__ == "__main__":
    unittest.main()
