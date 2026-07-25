import json
import os
import unittest
from datetime import date, datetime, timedelta
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
        self.assertIn("expiration_date", result)
        self.assertIsNone(result["expiration_date"])

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

    def test_context_keeps_only_six_recent_messages(self):
        payload = app.OracleChatRequest(
            question="What is next?",
            access_code="DEMO888",
            history=[
                app.OracleChatMessage(role="user", content=f"message {index}")
                for index in range(10)
            ],
        )
        context = app.oracle_context_payload(payload, app.demo_access_result())

        self.assertEqual(len(context["recent_history"]), 6)
        self.assertEqual(context["recent_history"][0]["content"], "message 4")

    def test_long_history_is_accepted_and_compacted_for_model_context(self):
        long_reading = "Opening insight. " + ("deep interpretation " * 700) + "Closing guidance."
        payload = app.OracleChatRequest(
            question="What does this mean for me now?",
            access_code="DEMO888",
            history=[
                app.OracleChatMessage(role="assistant", content=long_reading),
            ],
        )

        context = app.oracle_context_payload(payload, app.demo_access_result())
        compacted = context["recent_history"][0]["content"]

        self.assertLessEqual(len(compacted), app.ORACLE_HISTORY_MESSAGE_LIMIT)
        self.assertIn(app.ORACLE_HISTORY_COMPACTION_MARKER.strip(), compacted)
        self.assertTrue(compacted.startswith("Opening insight."))
        self.assertTrue(compacted.endswith("Closing guidance."))

    def test_runtime_context_uses_authoritative_manila_clock(self):
        original_now = app.oracle_now
        app.oracle_now = lambda: datetime(2026, 7, 24, 18, 30, tzinfo=MANILA)
        try:
            context = app.oracle_runtime_context()
        finally:
            app.oracle_now = original_now

        self.assertEqual(context["current_date"], "2026-07-24")
        self.assertEqual(context["weekday"], "Friday")
        self.assertEqual(context["timezone"], "Asia/Manila")

    def test_current_date_question_bypasses_model_memory(self):
        original_now = app.oracle_now
        original_request = app.request_openai_oracle_answer
        app.oracle_now = lambda: datetime(2026, 7, 24, 18, 30, tzinfo=MANILA)
        app.request_openai_oracle_answer = lambda *_args, **_kwargs: self.fail(
            "The model must not answer an exact current-date question."
        )
        try:
            result = app.chat_with_astromeg_oracle(
                app.OracleChatRequest(
                    question="What is the date today???",
                    access_code="DEMO888",
                )
            )
        finally:
            app.oracle_now = original_now
            app.request_openai_oracle_answer = original_request

        self.assertEqual(
            result["answer"],
            "Today is Friday, July 24, 2026, in Manila (Asia/Manila).",
        )

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
        self.assertEqual(captured["body"]["model"], app.OPENAI_MODEL)
        self.assertEqual(
            captured["body"]["reasoning"],
            {"effort": app.OPENAI_REASONING_EFFORT},
        )
        self.assertEqual(
            captured["body"]["text"],
            {"verbosity": app.OPENAI_TEXT_VERBOSITY},
        )
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

    def test_chat_dispatches_every_supported_calculator(self):
        birth_profile = {
            "name": "Meg",
            "birth_year": 1972,
            "birth_month": 7,
            "birth_day": 31,
            "birth_hour": 22,
            "birth_minute": 50,
            "birthplace": "Quezon City, Philippines",
        }
        saved_people = [
            {
                "name": "Alex",
                "birthDate": "1993-12-06",
                "birthTime": "14:10",
                "birthCity": "Quezon City",
                "birthCountry": "Philippines",
            }
        ]
        calculator_cases = [
            ("calculate_chart", "Calculate my natal chart.", "natal_chart"),
            (
                "calculate_solar_return",
                "Calculate my 2026 Solar Return in Quezon City.",
                "solar_return",
            ),
            (
                "calculate_transit_timeline",
                "Calculate a Jupiter transit timeline from 2026-07-01 to 2026-08-01.",
                "transit_timeline",
            ),
            (
                "calculate_progressed_chart",
                "Calculate my secondary progressed chart for 2026-08-01.",
                "progressed_chart",
            ),
            (
                "calculate_progressed_chart_solar_arc_angles",
                "Calculate my progressed chart Solar Arc angles for 2026-08-01.",
                "progressed_solar_arc_angles",
            ),
            (
                "calculate_progressed_solar_longitude_chart",
                "Calculate my progressed solar longitude chart for 2026-08-01.",
                "progressed_solar_longitude",
            ),
            (
                "calculate_solar_arc_directions",
                "Calculate Solar Arc Directions for 2026-08-01.",
                "solar_arc_directions",
            ),
            (
                "calculate_harmonic_chart",
                "Calculate my 24th harmonic chart.",
                "harmonic_chart",
            ),
            (
                "calculate_harmonic_charts",
                "Calculate harmonic charts 5, 8, 10 and 11.",
                "harmonic_charts",
            ),
            (
                "calculate_composite_chart",
                "Calculate a composite chart with Alex.",
                "composite_chart",
            ),
            (
                "calculate_davison_chart",
                "Calculate a Davison chart with Alex.",
                "davison_chart",
            ),
        ]
        verification_payload = {
            "status": "success",
            "success": True,
            "verified_chart_data": True,
            "verified_solar_return": True,
            "verified_transit_timeline": True,
            "verified_progressed_chart": True,
            "verified_solar_arc_directions": True,
            "verified_harmonic_chart": True,
            "verified_composite_chart": True,
            "verified_davison_chart": True,
            "placements": [{"body": "Sun", "sign": "Leo", "degree": 8.25}],
        }

        for calculator_name, question, expected_type in calculator_cases:
            with self.subTest(calculator=calculator_name):
                original_calculator = getattr(app, calculator_name)
                captured = {}

                def fake_calculator(*args, **kwargs):
                    captured["args"] = args
                    captured["kwargs"] = kwargs
                    return app.json_response(verification_payload)

                setattr(app, calculator_name, fake_calculator)
                try:
                    calculation = app.oracle_verified_calculation(
                        app.OracleChatRequest(
                            question=question,
                            access_code="DEMO888",
                            birth_profile=birth_profile,
                            saved_people=saved_people,
                        )
                    )
                finally:
                    setattr(app, calculator_name, original_calculator)

                self.assertTrue(captured)
                self.assertEqual(calculation["status"], "verified")
                self.assertEqual(calculation["type"], expected_type)
                self.assertEqual(calculation["source"], "Swiss Ephemeris")

    def test_transit_request_uses_automatic_manila_window(self):
        original_now = app.oracle_now
        app.oracle_now = lambda: datetime(2026, 7, 24, 18, 30, tzinfo=MANILA)
        try:
            request, missing = app.oracle_transit_request(
                app.OracleChatRequest(
                    question="Calculate my current transits.",
                    access_code="DEMO888",
                )
            )
        finally:
            app.oracle_now = original_now

        self.assertEqual(missing, [])
        self.assertEqual(request.start_date, date(2026, 7, 24))
        self.assertEqual(request.end_date, date(2026, 7, 24) + timedelta(days=180))
        self.assertEqual(request.timezone, "Asia/Manila")
        self.assertEqual(request.planet, "all")

    def test_transit_window_ignores_assistant_dates_and_uses_user_relative_range(self):
        original_now = app.oracle_now
        app.oracle_now = lambda: datetime(2026, 7, 24, 19, 0, tzinfo=MANILA)
        try:
            payload = app.OracleChatRequest(
                question="Use the next three months.",
                access_code="DEMO888",
                history=[
                    app.OracleChatMessage(
                        role="user",
                        content="Calculate my transit timeline.",
                    ),
                    app.OracleChatMessage(
                        role="assistant",
                        content=(
                            "I will start from April 27, 2024 and end July 27, 2024. "
                            "Which planets should I include?"
                        ),
                    ),
                ],
            )
            request, missing = app.oracle_transit_request(payload)
        finally:
            app.oracle_now = original_now

        self.assertEqual(missing, [])
        self.assertEqual(request.start_date, date(2026, 7, 24))
        self.assertEqual(request.end_date, date(2026, 10, 24))
        self.assertEqual(request.timezone, "Asia/Manila")
        self.assertEqual(request.planet, "all")

    def test_timing_mode_routes_relative_window_to_transit_calculator(self):
        payload = app.OracleChatRequest(
            question="Use the next three months.",
            chat_mode="timing",
            access_code="DEMO888",
        )

        self.assertEqual(app.oracle_calculation_intent(payload), "transit_timeline")

    def test_verified_calculation_denial_is_rejected_and_regenerated(self):
        original_calculation = app.oracle_verified_calculation
        original_request = app.request_openai_oracle_answer
        correction_flags = []

        app.oracle_verified_calculation = lambda _payload: {
            "type": "solar_return",
            "status": "verified",
            "source": "Swiss Ephemeris",
            "placements": [{"body": "Sun", "sign": "Leo", "degree": 8.25, "house": 6}],
        }

        def fake_request(_payload, _access, _calculation=None, correction_required=False):
            correction_flags.append(correction_required)
            if not correction_required:
                return "Currently, I don't have the precise Solar Return chart data loaded here."
            return "## Your Solar Return\n\nYour exact verified Sun is 8.25° Leo in the 6th house."

        app.request_openai_oracle_answer = fake_request
        try:
            result = app.chat_with_astromeg_oracle(
                app.OracleChatRequest(
                    question="Give me my exact Solar Return placements.",
                    access_code="DEMO888",
                )
            )
        finally:
            app.oracle_verified_calculation = original_calculation
            app.request_openai_oracle_answer = original_request

        self.assertTrue(result["success"])
        self.assertEqual(correction_flags, [False, True])
        self.assertIn("8.25° Leo", result["answer"])
        self.assertNotIn("don't have", result["answer"].casefold())

    def test_verified_calculation_prompt_forbids_unavailable_claims(self):
        payload = app.OracleChatRequest(
            question="List my exact Solar Return placements.",
            access_code="DEMO888",
        )
        prompt = app.oracle_user_input(
            payload,
            app.demo_access_result(),
            {
                "type": "solar_return",
                "status": "verified",
                "placements": [{"body": "Sun", "sign": "Leo", "degree": 8.25, "house": 6}],
            },
        )

        self.assertIn("authoritative", prompt)
        self.assertIn("Never claim verified data is unavailable", prompt)

    def test_private_knowledge_retrieval_prioritizes_style_and_progressions(self):
        chunks = [
            {
                "id": "style:1",
                "source_id": "style",
                "category": "reading_style",
                "priority": 10,
                "keywords": ["reading sequence", "action plan", "warm voice"],
                "text": (
                    "Begin with the immediate chart theme, interpret with warmth, "
                    "and close with insight and a practical action plan."
                ),
            },
            {
                "id": "progressed:1",
                "source_id": "progressed",
                "category": "progressed_charts",
                "priority": 9,
                "keywords": ["progressed chart", "progressed moon", "solar arc"],
                "text": (
                    "The progressed Moon describes the emotional chapter and is "
                    "the first priority in a secondary progressed chart."
                ),
            },
            {
                "id": "wisdom:1",
                "source_id": "wisdom",
                "category": "wisdom_reference",
                "priority": 3,
                "keywords": ["tesla"],
                "text": "Tesla worked with resonance and electrical systems.",
            },
        ]

        selected = app.select_oracle_knowledge(
            chunks,
            "Give me an in-depth secondary progressed chart reading.",
            calculation_type="progressed_chart",
        )

        topics = {item["topic"] for item in selected}
        self.assertIn("reading_style", topics)
        self.assertIn("progressed_charts", topics)
        self.assertNotIn("wisdom_reference", topics)

    def test_private_knowledge_selection_stays_inside_context_budget(self):
        original_max_chars = app.ORACLE_KNOWLEDGE_MAX_CHARS
        original_max_chunks = app.ORACLE_KNOWLEDGE_MAX_CHUNKS
        app.ORACLE_KNOWLEDGE_MAX_CHARS = 120
        app.ORACLE_KNOWLEDGE_MAX_CHUNKS = 2
        try:
            chunks = [
                {
                    "id": f"style:{index}",
                    "source_id": "style",
                    "category": "reading_style",
                    "priority": 10,
                    "keywords": ["love"],
                    "text": "love relationship warmth guidance " * 3,
                }
                for index in range(4)
            ]
            selected = app.select_oracle_knowledge(
                chunks,
                "Give me a warm love relationship reading.",
            )
        finally:
            app.ORACLE_KNOWLEDGE_MAX_CHARS = original_max_chars
            app.ORACLE_KNOWLEDGE_MAX_CHUNKS = original_max_chunks

        self.assertTrue(selected)
        self.assertLessEqual(sum(len(item["content"]) for item in selected), 120)
        self.assertLessEqual(len(selected), 2)

    def test_private_knowledge_prompt_keeps_sources_hidden(self):
        original_loader = app.load_oracle_knowledge
        app.load_oracle_knowledge = lambda: [
            {
                "id": "style:1",
                "source_id": "style",
                "category": "reading_style",
                "priority": 10,
                "keywords": ["warm"],
                "text": "Write a warm, deep interpretation with an action plan.",
            }
        ]
        try:
            prompt = app.oracle_user_input(
                app.OracleChatRequest(
                    question="Give me a warm reading.",
                    access_code="DEMO888",
                ),
                app.demo_access_result(),
            )
        finally:
            app.load_oracle_knowledge = original_loader

        self.assertIn('"private_knowledge"', prompt)
        self.assertIn("Use private_knowledge silently", prompt)
        self.assertIn("Never name, quote, reveal", prompt)

    def test_model_instructions_enforce_conversational_astromeg_voice(self):
        instructions = app.oracle_model_instructions()

        self.assertIn("ASTROMEG APP VOICE CONTRACT", instructions)
        self.assertIn("private one-to-one conversation", instructions)
        self.assertIn("lightly witty", instructions)
        self.assertIn("trace the dispositors", instructions)
        self.assertIn("Thank you for your insightful question", instructions)
        self.assertIn("grounded action plan", instructions)

    def test_health_reports_private_knowledge_readiness(self):
        original_loader = app.load_oracle_knowledge
        app.load_oracle_knowledge = lambda: [{"text": "one"}, {"text": "two"}]
        try:
            result = app.health()
        finally:
            app.load_oracle_knowledge = original_loader

        self.assertTrue(result.oracle_knowledge_loaded)
        self.assertEqual(result.oracle_knowledge_chunks, 2)

    def test_relationship_chart_requires_named_person_when_several_are_saved(self):
        payload = app.OracleChatRequest(
            question="Calculate a composite chart.",
            access_code="DEMO888",
            birth_profile={
                "birth_year": 1972,
                "birth_month": 7,
                "birth_day": 31,
                "birth_hour": 22,
                "birth_minute": 50,
                "birthplace": "Quezon City, Philippines",
            },
            saved_people=[
                {"name": "Alex"},
                {"name": "Jordan"},
            ],
        )

        calculation = app.oracle_verified_calculation(payload)

        self.assertEqual(calculation["status"], "missing_inputs")
        self.assertIn("saved_person_name", calculation["missing"])

    def test_regular_oracle_question_does_not_trigger_a_calculator(self):
        payload = app.OracleChatRequest(
            question="What should I focus on emotionally today?",
            access_code="DEMO888",
        )

        self.assertIsNone(app.oracle_verified_calculation(payload))

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
