import os
import unittest

import app


class GoogleAuthTests(unittest.TestCase):
    def setUp(self):
        self.original_client_id = os.environ.get("GOOGLE_CLIENT_ID")
        self.original_verify_google_credential = app.verify_google_credential
        self.original_validate_account_email = app.validate_account_email

    def tearDown(self):
        if self.original_client_id is None:
            os.environ.pop("GOOGLE_CLIENT_ID", None)
        else:
            os.environ["GOOGLE_CLIENT_ID"] = self.original_client_id
        app.verify_google_credential = self.original_verify_google_credential
        app.validate_account_email = self.original_validate_account_email

    def test_google_auth_routes_are_exposed(self):
        paths = {route.path for route in app.app.routes}

        self.assertIn("/auth/google/config", paths)
        self.assertIn("/auth/google", paths)

    def test_google_sign_in_returns_make_validated_account_access(self):
        os.environ["GOOGLE_CLIENT_ID"] = "google-client-id"
        app.verify_google_credential = lambda credential, client_id: {
            "email": "meg.sanchez@gmail.com",
            "email_verified": True,
            "iss": "https://accounts.google.com",
            "name": "Astromeg",
            "picture": "https://example.com/meg.png",
        }
        app.validate_account_email = lambda email: {
            "valid": True,
            "status": "ACTIVE",
            "email": email,
            "customer_name": "Astromeg",
            "expiration_date": "2099-01-01",
            "permission_level": "ALL_ACCESS_ANNUAL",
            "reading_type": "ALL_ACCESS_ANNUAL",
        }

        result = app.sign_in_with_google(app.GoogleSignInRequest(credential="verified-google-token"))

        self.assertTrue(result["success"])
        self.assertEqual(result["email"], "meg.sanchez@gmail.com")
        self.assertEqual(result["expiration_date"], "2099-01-01")
        self.assertEqual(result["permission_level"], "ALL_ACCESS_ANNUAL")
        self.assertEqual(result["reading_type"], "ALL_ACCESS_ANNUAL")


if __name__ == "__main__":
    unittest.main()
