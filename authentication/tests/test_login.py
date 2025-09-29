from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.hashers import make_password
from authentication.models import User
import json
import uuid

class LoginEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url_name = "authentication:login"
        self.logout_url_name = "authentication:logout"
        self.username = f"user_{uuid.uuid4().hex[:6]}"
        self.password = "KalbePPL2025"

        self.user = User.objects.create(
            username=self.username,
            password=make_password(self.password),
            is_verified=True
        )

    def _post_json(self, url, payload: dict):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_login_success(self):
        url = reverse(self.login_url_name)
        payload = {"username": self.username, "password": self.password}
        response = self._post_json(url, payload)

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIn("message", data)
        self.assertEqual(data["message"].lower(), "login successful")

    def test_login_success_and_logout_flow(self):
        login_url = reverse(self.login_url_name)
        payload = {"username": self.username, "password": self.password}
        login_response = self._post_json(login_url, payload)
        self.assertEqual(login_response.status_code, 200)

        logout_url = reverse(self.logout_url_name)
        logout_response = self.client.post(
            logout_url,
            content_type="application/json"
        )
        self.assertEqual(logout_response.status_code, 200)
        data = logout_response.json()
        self.assertIn("message", data)
        self.assertEqual(data["message"], "Logged out")

    def test_login_invalid_json_returns_400(self):
        url = reverse(self.login_url_name)
        response = self.client.post(
            url,
            data="not-a-json{",
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("error", response.json())

    def test_invalid_unicode_payload_returns_400(self):
        """negative: requests with bytes that cannot be UTF-8 decoded should return 400"""
        url = reverse(self.login_url_name)
        # Send raw bytes that are invalid UTF-8 to trigger UnicodeDecodeError
        invalid_bytes = b"\xff\xfe\xff"
        response = self.client.post(url, data=invalid_bytes, content_type="application/json")
        self.assertEqual(response.status_code, 400, response.content)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "invalid payload")

    def test_login_nonexistent_credentials(self):
        url = reverse(self.login_url_name)
        payload = {"username": "doesnotexist", "password": "Password123"}
        response = self._post_json(url, payload)
        self.assertEqual(response.status_code, 401, response.content)
        self.assertIn("error", response.json())

    def test_login_invalid_credentials(self):
        url = reverse(self.login_url_name)
        payload = {"username": self.username, "password": "Password123"}
        response = self._post_json(url, payload)
        self.assertEqual(response.status_code, 401, response.content)
        self.assertIn("error", response.json())

    def test_login_empty_fields(self):
        url = reverse(self.login_url_name)
        for payload in (
            {"username": "", "password": self.password},
            {"username": self.username, "password": ""},
        ):
            response = self._post_json(url, payload)
            self.assertEqual(response.status_code, 400, response.content)
            self.assertIn("error", response.json())

    def test_login_whitespace_credentials(self):
        url = reverse(self.login_url_name)
        for payload in (
            {"username": "   ", "password": self.password},
            {"username": self.username, "password": "   "},
        ):
            response = self._post_json(url, payload)
            self.assertEqual(response.status_code, 400, response.content)
            self.assertIn("error", response.json())

    def test_login_missing_fields(self):
        """Negative: missing username or password → 400"""
        url = reverse(self.login_url_name)
        response = self._post_json(url, {"username": self.username})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("error", response.json())

        response = self._post_json(url, {"password": self.password})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("error", response.json())

    def test_login_non_json_content_type(self):
        """Negative: form-data instead of JSON → 400/415"""
        url = reverse(self.login_url_name)
        response = self.client.post(
            url,
            data={"username": self.username, "password": self.password},
            content_type="application/x-www-form-urlencoded",
        )
        self.assertIn(response.status_code, (400, 415), response.content)

    def test_login_empty_body_returns_400(self):
        """Negative: empty request body should be treated as empty JSON and return 400 (missing fields)"""
        url = reverse(self.login_url_name)
        # Post with no body (empty) but JSON content type
        response = self.client.post(url, content_type="application/json")
        self.assertEqual(response.status_code, 400, response.content)
        data = response.json()
        self.assertIn("error", data)

    def test_login_whitespace_body_returns_400(self):
        """Negative: whitespace-only body should be treated like empty JSON and return 400"""
        url = reverse(self.login_url_name)
        response = self.client.post(url, data=b"   ", content_type="application/json")
        self.assertEqual(response.status_code, 400, response.content)
        data = response.json()
        self.assertIn("error", data)

    def test_login_unverified_user(self):
        """Negative: unverified user → 403"""
        url = reverse(self.login_url_name)
        unverified_user = User.objects.create(
            username="stranger",
            password=make_password("Password123"),
            email="stranger@email.com",
            is_verified=False
        )
        payload = {"username": "stranger", "password": "Password123"}
        response = self._post_json(url, payload)
        self.assertEqual(response.status_code, 403, response.content)
        data = response.json()
        self.assertEqual(data["error"], "Email not verified")
        self.assertEqual(data["message"], "Please verify your email before logging in")

    def test_logout_endpoint(self):
        """Logout without login → still 200 (Django logout is idempotent)"""
        url = reverse(self.logout_url_name)
        response = self.client.post(url, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["message"], "Logged out")