import json
import unittest

import app


class HoraryRegiomontanusTests(unittest.TestCase):
    def test_chart_accepts_regiomontanus_house_system(self):
        response = app.calculate_chart(
            year=1972,
            month=7,
            day=31,
            hour=22,
            minute=50,
            birthplace="Quezon City, Philippines",
            house_system="Regiomontanus",
        )
        payload = json.loads(response.body)

        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["house_system"], "Regiomontanus")
        self.assertEqual(payload["birth_data"]["house_system"], "Regiomontanus")
        self.assertEqual(len(payload["houses"]), 12)
        self.assertIn("ascendant", payload)
        self.assertIn("midheaven", payload)
        self.assertGreater(len(payload["placements"]), 0)

    def test_horary_defaults_to_regiomontanus(self):
        response = app.calculate_chart(
            year=1972,
            month=7,
            day=31,
            hour=22,
            minute=50,
            birthplace="Quezon City, Philippines",
            chart_type="horary",
        )
        payload = json.loads(response.body)

        self.assertEqual(payload["chart_type"], "horary")
        self.assertEqual(payload["house_system"], "Regiomontanus")
        self.assertEqual(payload["birth_data"]["house_system"], "Regiomontanus")

    def test_chart_returns_moon_aspects(self):
        response = app.calculate_chart(
            year=1972,
            month=7,
            day=31,
            hour=22,
            minute=50,
            birthplace="Quezon City, Philippines",
            house_system="Regiomontanus",
        )
        payload = json.loads(response.body)

        self.assertGreater(len(payload["aspects"]), 0)
        self.assertTrue(all(aspect["body_a"] == "Moon" for aspect in payload["aspects"]))
        self.assertTrue(all("orb" in aspect for aspect in payload["aspects"]))

    def test_openapi_exposes_house_system_and_chart_type(self):
        app.app.openapi_schema = None
        schema = app.custom_openapi()
        parameters = schema["paths"]["/chart"]["get"]["parameters"]
        names = {parameter["name"] for parameter in parameters}

        self.assertIn("house_system", names)
        self.assertIn("chart_type", names)


if __name__ == "__main__":
    unittest.main()
