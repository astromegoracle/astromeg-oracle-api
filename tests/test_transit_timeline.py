import unittest
from datetime import date

from fastapi import HTTPException

import app


class TransitTimelineTests(unittest.TestCase):
    def test_jupiter_leo_timeline_includes_requested_events(self):
        payload = app.calculate_transit_timeline_payload(
            app.TransitTimelineRequest(
                planet="Jupiter",
                start_date=date(2026, 6, 1),
                end_date=date(2027, 12, 31),
                sign="Leo",
                target_degrees=[0, 29],
                fixed_stars=[app.FixedStarTransitTarget(name="Regulus", orb_arcminutes=10)],
                timezone="UTC",
                include_retrograde_stations=True,
                step_days=1,
            )
        )

        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["verified_transit_timeline"])
        self.assertEqual(payload["planet"], "Jupiter")
        self.assertGreater(payload["event_count"], 0)
        self.assertEqual(payload["events"], sorted(payload["events"], key=lambda event: event["julian_day"]))
        self.assertTrue(
            any(
                event["event_type"] == "sign_ingress"
                and event.get("target_sign") == "Leo"
                and event.get("target_degree") == 0.0
                for event in payload["events"]
            )
        )
        self.assertTrue(
            any(
                event["event_type"] == "degree_crossing"
                and event.get("target_sign") == "Leo"
                and event.get("target_degree") == 29.0
                for event in payload["events"]
            )
        )
        self.assertTrue(any(event["event_type"] == "fixed_star_conjunction" for event in payload["events"]))
        self.assertIn("VERIFIED_ASTROMEG_TRANSIT_TIMELINE", payload["chart_text"])

    def test_openapi_exposes_transit_timeline_action(self):
        app.app.openapi_schema = None
        schema = app.app.openapi()

        self.assertIn("/calculate_transit_timeline", schema["paths"])
        operation = schema["paths"]["/calculate_transit_timeline"]["post"]
        self.assertEqual(operation["operationId"], "calculate_transit_timeline")
        self.assertEqual(
            operation["requestBody"]["content"]["application/json"]["schema"],
            app.TRANSIT_TIMELINE_REQUEST_SCHEMA,
        )

    def test_unsupported_transit_planet_raises_readable_error(self):
        with self.assertRaises(HTTPException) as context:
            app.calculate_transit_timeline_payload(
                app.TransitTimelineRequest(
                    planet="Vulcan",
                    start_date=date(2026, 6, 1),
                    end_date=date(2026, 6, 2),
                )
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("Unsupported transit planet", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
