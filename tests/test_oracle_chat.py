import json
import os
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import app


MANILA = ZoneInfo("Asia/Manila")


class FakeUrlResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class OracleChatTests(unittest.TestCase):
    def setUp(self):
        self.original_urlopen = app.urlopen
        self.original_api_key = os.environ.get("OPENAI_API_KEY")
        app.app.openapi_schema = None

    def tearDown(self):
        app.urlopen = self.original_urlopen
        app.app.openapi_schema = None
        if self.original_api_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = self.original_api_key

    def test_demo_access_does_not_call_external_validation(self):
        payload = app.OracleChatRequest(question="What should I focus on?", access_code=" demo888 ")
        result = app.validate_oracle_chat_access(payload)

        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "DEMO")
        self.assertEqual(result["permission_level"], "DEMO")

    def test_email_account_can_be_validated_from_rows(self):
        rows = [
            ["Email", "Customer Name", "Expiration Date", "Status", "Permission Level", "Reading Type"],
            ["meg@example.com", "Meg", "2099-12-31", "ACTIVE", "FOUNDER", "ALL"],
        ]
        result = app.validate_account_email_from_rows(
            " MEG@example.com ",
            rows,
            now=datetime(2026, 7, 24, 12, 0, tzinfo=MANILA),
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["customer_name"], "Meg")
        self.assertEqual(result["permission_level"], "FOUNDER")

    def test_context_keeps_only_eight_recent_messages(self):
        payload = app.OracleChatRequest(
            question="What is next?",
            access_code="DEMO888",
            history=[
                app.OracleChatMessage(role="user", content=f"message {index}")
                for index in range(10)
            ],
        )
        context = app.oracle_context_payload(payload, app.demo_access_result())

        self.assertEqual(len(context["recent_history"]), 8)
        self.assertEqual(context["recent_history"][0]["content"], "message 2")

    def test_openai_request_is_not_stored_and_has_output_limit(self):
        os.environ["OPENAI_API_KEY"] = "test-key"
        captured = {}

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeUrlResponse(
                {
                    "output": [
                        {
                            "content": [
                                {"type": "output_text", "text": "Your answer is ready."}
                            ]
                        }
                    ]
                }
            )

        app.urlopen = fake_urlopen
        payload = app.OracleChatRequest(question="What is next?", access_code="DEMO888")
        answer = app.request_openai_oracle_answer(payload, app.demo_access_result())

        self.assertEqual(answer, "Your answer is ready.")
        self.assertFalse(captured["body"]["store"])
        self.assertEqual(captured["body"]["max_output_tokens"], app.ORACLE_CHAT_MAX_OUTPUT_TOKENS)
        self.assertEqual(captured["timeout"], app.ORACLE_CHAT_TIMEOUT_SECONDS)

    def test_solar_return_request_uses_profile_and_recent_chat_details(self):
        payload = app.OracleChatRequest(
            question="Give me the exact planets, degrees, and houses.",
            access_code="DEMO888",
            birth_profile={
                "birth_year": 1972,
                "birth_month": 7,
                "birth_day": 31,
                "birth_hour": 22,
                "birth_minute": 50,
                "birthplace": "Quezon City, Philippines",
            },
            history=[
                app.OracleChatMessage(
                    role="user",
                    content="Calculate my 2026 Solar Return in Quezon City with planets and houses.",
                )
            ],
        )

        request, missing = app.solar_return_chat_request(payload)

        self.assertEqual(missing, [])
        self.assertIsNotNone(request)
        self.assertEqual(request.return_year, 2026)
        self.assertEqual(request.return_location, "Quezon City, Philippines")
        self.assertEqual(request.birth_year, 1972)

    def test_solar_return_calculation_is_added_to_oracle_context(self):
        original_calculator = app.calculate_solar_return
        captured = {}

        def fake_calculator(_request):
            return app.json_response(
                {
                    "success": True,
                    "verified_solar_return": True,
                    "verified_chart_data": True,
                    "exact_return_utc": "2026-07-31T12:00:00Z",
                    "exact_return_local": "2026-07-31T20:00:00+08:00",
                    "return_location": "Quezon City",
                    "return_location_resolved": "Quezon City, Metro Manila, Philippines",
                    "return_location_timezone": "Asia/Manila",
                    "natal_sun_longitude": 128.25,
                    "return_sun_longitude": 128.25,
                    "longitude_delta_arcseconds": 0.01,
                    "chart": {
                        "ascendant_position": {"sign": "Aquarius", "degree": 12.3},
                        "midheaven_position": {"sign": "Scorpio", "degree": 4.5},
                    },
                    "placements": [
                        {"body": "Sun", "sign": "Leo", "degree": 8.25, "house": 6}
                    ],
                    "houses": [
                        {"house": 1, "sign": "Aquarius", "degree": 12.3}
                    ],
                    "aspects": [],
                }
            )

        app.calculate_solar_return = fake_calculator
        try:
            payload = app.OracleChatRequest(
                question="Calculate my 2026 Solar Return in Quezon City.",
                access_code="DEMO888",
                birth_profile={
                    "birth_year": 1972,
                    "birth_month": 7,
                    "birth_day": 31,
                    "birth_hour": 22,
                    "birth_minute": 50,
                    "birthplace": "Quezon City, Philippines",
                },
            )
            calculation = app.oracle_verified_calculation(payload)
            context = app.oracle_context_payload(payload, app.demo_access_result(), calculation)
        finally:
            app.calculate_solar_return = original_calculator

        captured["calculation"] = context["verified_calculation"]
        self.assertEqual(captured["calculation"]["status"], "verified")
        self.assertEqual(captured["calculation"]["source"], "Swiss Ephemeris")
        self.assertEqual(captured["calculation"]["placements"][0]["degree"], 8.25)
        self.assertEqual(captured["calculation"]["placements"][0]["house"], 6)

    def test_custom_gpt_schema_does_not_expose_app_chat(self):
        schema = app.custom_openapi()
        self.assertNotIn("/oracle/chat", schema["paths"])
        self.assertIn("/chart", schema["paths"])
        self.assertIn("/validate-access-code", schema["paths"])

    def test_chat_endpoint_returns_demo_answer(self):
        original_request = app.request_openai_oracle_answer
        app.request_openai_oracle_answer = lambda payload, access, calculation=None: "A live demo answer."
        try:
            result = app.chat_with_astromeg_oracle(
                app.OracleChatRequest(question="What is next?", access_code="DEMO888")
            )
        finally:
            app.request_openai_oracle_answer = original_request

        self.assertTrue(result["success"])
        self.assertEqual(result["answer"], "A live demo answer.")
        self.assertEqual(result["status"], "DEMO")


if __name__ == "__main__":
    unittest.main()
