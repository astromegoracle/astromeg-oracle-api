import json
import os
import tempfile
import unittest
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import app


MANILA = ZoneInfo("Asia/Manila")


class FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


class FakeUrlResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class AccessCodeValidationTests(unittest.TestCase):
    def setUp(self):
        self.original_fetch = app.fetch_access_sheet_rows
        self.original_api_key = os.environ.get("ORACLE_BACKEND_API_KEY")
        self.original_env_codes = os.environ.get("ORACLE_ACCESS_CODES_JSON")
        self.original_validation_url = os.environ.get("ORACLE_ACCESS_VALIDATION_URL")
        self.original_validation_secret = os.environ.get("ORACLE_ACCESS_VALIDATION_SECRET")
        self.original_urlopen = app.urlopen
        app.ACCESS_CACHE.clear()

    def tearDown(self):
        app.fetch_access_sheet_rows = self.original_fetch
        app.urlopen = self.original_urlopen
        app.ACCESS_CACHE.clear()
        if self.original_api_key is None:
            os.environ.pop("ORACLE_BACKEND_API_KEY", None)
        else:
            os.environ["ORACLE_BACKEND_API_KEY"] = self.original_api_key
        if self.original_env_codes is None:
            os.environ.pop("ORACLE_ACCESS_CODES_JSON", None)
        else:
            os.environ["ORACLE_ACCESS_CODES_JSON"] = self.original_env_codes
        if self.original_validation_url is None:
            os.environ.pop("ORACLE_ACCESS_VALIDATION_URL", None)
        else:
            os.environ["ORACLE_ACCESS_VALIDATION_URL"] = self.original_validation_url
        if self.original_validation_secret is None:
            os.environ.pop("ORACLE_ACCESS_VALIDATION_SECRET", None)
        else:
            os.environ["ORACLE_ACCESS_VALIDATION_SECRET"] = self.original_validation_secret

    def rows(self):
        return [
            ["Access Code", "Expiration Date", "Status", "Customer Name", "Email", "Permission Level", "Reading Type"],
            ["FULL-CODE", "2099-05-31", "ACTIVE", "Meg Founder", "meg@example.com", "VIP", "FOUNDER"],
            ["MANUAL-VIP", "2099-06-30", "ACTIVE"],
            ["BLANK-NAME", "2099-07-31", "PAID", "", "", "", ""],
            ["OLD-CODE", "2026-05-31", "ACTIVE", "Expired Person", "expired@example.com", "VIP", "30DAY"],
            ["PENDING-CODE", "2099-08-31", "PENDING", "Pending Person", "pending@example.com", "VIP", "30DAY"],
            ["CANCELLED-CODE", "2099-09-30", "CANCELLED", "Cancelled Person", "cancelled@example.com", "VIP", "30DAY"],
        ]

    def test_make_generated_valid_code_with_full_customer_details(self):
        result = app.validate_access_code_from_rows(" full-code ", self.rows())
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "ACTIVE")
        self.assertEqual(result["customer_name"], "Meg Founder")
        self.assertEqual(result["email"], "meg@example.com")
        self.assertEqual(result["expiration_date"], "2099-05-31")
        self.assertEqual(result["permission_level"], "VIP")
        self.assertEqual(result["reading_type"], "FOUNDER")

    def test_manual_vip_code_with_required_fields_only(self):
        result = app.validate_access_code_from_rows("manual-vip", self.rows())
        self.assertTrue(result["valid"])
        self.assertEqual(result["expiration_date"], "2099-06-30")
        self.assertEqual(result["permission_level"], "VIP")
        self.assertEqual(result["reading_type"], "30DAY")

    def test_valid_code_with_blank_name_and_email(self):
        result = app.validate_access_code_from_rows("BLANK-NAME", self.rows())
        self.assertTrue(result["valid"])
        self.assertIsNone(result["customer_name"])
        self.assertIsNone(result["email"])
        self.assertEqual(result["permission_level"], "VIP")
        self.assertEqual(result["reading_type"], "30DAY")

    def test_expired_code(self):
        result = app.validate_access_code_from_rows(
            "OLD-CODE",
            self.rows(),
            now=datetime(2026, 6, 3, 12, 0, tzinfo=MANILA),
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "EXPIRED")
        self.assertEqual(result["expiration_date"], "2026-05-31")

    def test_invalid_code(self):
        result = app.validate_access_code_from_rows("NOT-REAL", self.rows())
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "INVALID")

    def test_pending_code(self):
        result = app.validate_access_code_from_rows("PENDING-CODE", self.rows())
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "INVALID")

    def test_cancelled_code(self):
        result = app.validate_access_code_from_rows("CANCELLED-CODE", self.rows())
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "INVALID")

    def test_weekly_before_deadline(self):
        result = app.validate_access_code_from_rows(
            "WEEKLY",
            self.rows(),
            now=datetime(2026, 5, 17, 23, 59, tzinfo=MANILA),
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["permission_level"], "FREE")
        self.assertEqual(result["reading_type"], "WEEKLY")

    def test_weekly_after_deadline(self):
        result = app.validate_access_code_from_rows(
            "WEEKLY",
            self.rows(),
            now=datetime(2026, 5, 18, 0, 0, tzinfo=MANILA),
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "EXPIRED")

    def test_missing_api_key(self):
        os.environ.pop("ORACLE_BACKEND_API_KEY", None)
        response = app.validate_access_code(
            app.AccessCodeValidationRequest(access_code="FULL-CODE"),
            FakeRequest(),
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(json.loads(response.body)["valid"])

    def test_invalid_api_key(self):
        os.environ["ORACLE_BACKEND_API_KEY"] = "secret"
        response = app.validate_access_code(
            app.AccessCodeValidationRequest(access_code="FULL-CODE"),
            FakeRequest({"Authorization": "Bearer wrong"}),
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(json.loads(response.body)["valid"])

    def test_google_sheets_unavailable(self):
        os.environ["ORACLE_BACKEND_API_KEY"] = "secret"

        def unavailable():
            raise RuntimeError("sheet unavailable")

        app.fetch_access_sheet_rows = unavailable
        response = app.validate_access_code(
            app.AccessCodeValidationRequest(access_code="FULL-CODE"),
            FakeRequest({"Authorization": "Bearer secret"}),
        )
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body)
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["status"], "ERROR")

    def test_published_csv_rows_can_validate_code(self):
        csv_text = (
            "Access Code,Expiration Date,Status,Customer Name,Email,Permission Level,Reading Type\n"
            "CSV-CODE,2099-10-31,ACTIVE,,,,\n"
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".csv", delete=False) as temp_file:
            temp_file.write(csv_text)
            temp_file_path = temp_file.name

        try:
            rows = app.fetch_access_sheet_csv_rows(f"file://{temp_file_path}")
            result = app.validate_access_code_from_rows("csv-code", rows)
            self.assertTrue(result["valid"])
            self.assertEqual(result["expiration_date"], "2099-10-31")
            self.assertEqual(result["permission_level"], "VIP")
            self.assertEqual(result["reading_type"], "30DAY")
        finally:
            os.unlink(temp_file_path)

    def test_private_env_codes_can_validate_code(self):
        os.environ["ORACLE_BACKEND_API_KEY"] = "secret"
        os.environ["ORACLE_ACCESS_CODES_JSON"] = json.dumps(
            [
                {
                    "access_code": "ENV-CODE",
                    "expiration_date": "2099-12-31",
                    "status": "ACTIVE",
                    "permission_level": "VIP",
                    "reading_type": "FOUNDER",
                }
            ]
        )

        response = app.validate_access_code(
            app.AccessCodeValidationRequest(access_code=" env-code "),
            FakeRequest({"Authorization": "Bearer secret"}),
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["expiration_date"], "2099-12-31")
        self.assertEqual(payload["permission_level"], "VIP")
        self.assertEqual(payload["reading_type"], "FOUNDER")
        self.assertIsNone(payload["customer_name"])
        self.assertIsNone(payload["email"])

    def test_private_env_code_object_format_expires_automatically(self):
        os.environ["ORACLE_ACCESS_CODES_JSON"] = json.dumps(
            {
                "EXPIRED-ENV": {
                    "expiration_date": "2026-05-31",
                    "status": "ACTIVE",
                }
            }
        )

        rows = app.fetch_access_sheet_rows()
        result = app.validate_access_code_from_rows(
            "EXPIRED-ENV",
            rows,
            now=datetime(2026, 6, 4, 12, 0, tzinfo=MANILA),
        )

        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "EXPIRED")
        self.assertEqual(result["expiration_date"], "2026-05-31")

    def test_external_access_validator_can_validate_code(self):
        os.environ["ORACLE_BACKEND_API_KEY"] = "secret"
        os.environ["ORACLE_ACCESS_VALIDATION_URL"] = "https://script.google.com/macros/s/example/exec"
        os.environ["ORACLE_ACCESS_VALIDATION_SECRET"] = "bridge-secret"

        def fake_urlopen(request, timeout):
            payload = parse_qs(urlparse(request.full_url).query)
            self.assertEqual(payload["access_code"], ["SCRIPT-CODE"])
            self.assertEqual(payload["secret"], ["bridge-secret"])
            return FakeUrlResponse(
                {
                    "valid": True,
                    "status": "ACTIVE",
                    "message": "Access confirmed.",
                    "expiration_date": "2099-12-31",
                    "permission_level": "VIP",
                    "reading_type": "FOUNDER",
                }
            )

        app.urlopen = fake_urlopen
        response = app.validate_access_code(
            app.AccessCodeValidationRequest(access_code="SCRIPT-CODE"),
            FakeRequest({"Authorization": "Bearer secret"}),
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["status"], "ACTIVE")
        self.assertEqual(payload["expiration_date"], "2099-12-31")
        self.assertEqual(payload["permission_level"], "VIP")
        self.assertEqual(payload["reading_type"], "FOUNDER")

    def test_recent_valid_access_code_uses_cache_when_external_validation_times_out(self):
        os.environ["ORACLE_BACKEND_API_KEY"] = "secret"
        os.environ["ORACLE_ACCESS_VALIDATION_URL"] = "https://script.google.com/macros/s/example/exec"
        os.environ["ORACLE_ACCESS_VALIDATION_SECRET"] = "bridge-secret"
        calls = {"count": 0}

        def fake_urlopen(request, timeout):
            calls["count"] += 1
            if calls["count"] == 1:
                return FakeUrlResponse(
                    {
                        "valid": True,
                        "status": "ACTIVE",
                        "message": "Access confirmed.",
                        "expiration_date": "2099-12-31",
                        "permission_level": "VIP",
                        "reading_type": "FOUNDER",
                    }
                )
            raise TimeoutError("simulated timeout")

        app.urlopen = fake_urlopen
        first_response = app.validate_access_code(
            app.AccessCodeValidationRequest(access_code="SCRIPT-CODE"),
            FakeRequest({"Authorization": "Bearer secret"}),
        )
        second_response = app.validate_access_code(
            app.AccessCodeValidationRequest(access_code="SCRIPT-CODE"),
            FakeRequest({"Authorization": "Bearer secret"}),
        )

        self.assertEqual(first_response.status_code, 200)
        first_payload = json.loads(first_response.body)
        second_payload = json.loads(second_response.body)
        self.assertTrue(first_payload["valid"])
        self.assertTrue(second_payload["valid"])
        self.assertEqual(second_payload["status"], "ACTIVE")
        self.assertEqual(second_payload["cache"], "hit")


if __name__ == "__main__":
    unittest.main()
