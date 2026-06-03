import json
import os
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import app


MANILA = ZoneInfo("Asia/Manila")


class FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


class AccessCodeValidationTests(unittest.TestCase):
    def setUp(self):
        self.original_fetch = app.fetch_access_sheet_rows
        self.original_api_key = os.environ.get("ORACLE_BACKEND_API_KEY")

    def tearDown(self):
        app.fetch_access_sheet_rows = self.original_fetch
        if self.original_api_key is None:
            os.environ.pop("ORACLE_BACKEND_API_KEY", None)
        else:
            os.environ["ORACLE_BACKEND_API_KEY"] = self.original_api_key

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


if __name__ == "__main__":
    unittest.main()
