from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch
from django.contrib.auth.hashers import make_password
from UserRegistration.models import User
import json
import uuid

# to run test, enter in terminal:
# coverage run --source=authentication manage.py test authentication.tests.test_login --settings=kalbe_be.test_settings

class LoginEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url_name = "authentication:login"
        self.username = f"user_{uuid.uuid4().hex[:6]}"
        self.password = "password123"

        self.user = User.objects.create(
            username=self.username,
            password=make_password(self.password)
        )

    def _post_json(self, url, payload: dict):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def testLoginSuccess(self):
        """positive (valid username and password)"""
        try:
            url = reverse(self.url_name)
        except NoReverseMatch:
            self.fail(f"{self.url_name} is not defined")

        payload = {"username": self.username, "password": self.password}
        response = self._post_json(url, payload)

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIn("message", data)
        self.assertEqual(data["message"].lower(), "login successful")

    def testLoginInvalidJsonReturns400(self):
        """negative: invalid JSON payload should return 400"""
        url = reverse("authentication:login")

        response = self.client.post(
            url,
            data="not-a-json{",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400, response.content)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"], "invalid payload")

    def testLoginFailNonexistentCredentials(self):
        """negative (nonexistent username or password)"""
        url = reverse(self.url_name)
        payload = {"username": "doesnotexist", "password": "whatever"}
        response = self._post_json(url, payload)

        self.assertEqual(response.status_code, 401, response.content)
        self.assertIn("error", response.json())

    def testLoginFailInvalidCredentials(self):
        """negative (wrong username or password)"""
        url = reverse(self.url_name)
        payload = {"username": self.username, "password": "wrongpass"}
        response = self._post_json(url, payload)

        self.assertEqual(response.status_code, 401, response.content)
        self.assertIn("error", response.json())

    def testLoginFailEmptyField(self):
        """negative (empty field detected)"""
        url = reverse(self.url_name)
        for payload in (
            {"username": "", "password": self.password},
            {"username": self.username, "password": ""},
        ):
            response = self._post_json(url, payload)
            self.assertEqual(response.status_code, 400, response.content)
            self.assertIn("error", response.json())

    def testLoginFailWhitespaceCredentials(self):
        """negative (whitespace username or password)"""
        url = reverse(self.url_name)
        for payload in (
            {"username": "   ", "password": self.password},
            {"username": self.username, "password": "   "},
        ):
            response = self._post_json(url, payload)
            self.assertEqual(response.status_code, 400, response.content)
            self.assertIn("error", response.json())

    def testInvalidJsonReturns400(self):
        """negative (invalid JSON format in request body)"""
        url = reverse(self.url_name)
        response = self.client.post(
            url,
            data="{invalid_json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("error", response.json())

    def testNonJsonContentTypeReturns415(self):
        """negative (wrong content type, e.g. form-data instead of JSON)"""
        url = reverse(self.url_name)
        response = self.client.post(
            url,
            data={"username": self.username, "password": self.password},
            content_type="application/x-www-form-urlencoded",
        )
        # reject non-Json payloads
        self.assertIn(response.status_code, (400, 415), response.content)

    def testMissingFieldsReturns400(self):
        """negative (payload missing required fields)"""
        url = reverse(self.url_name)
        response = self._post_json(url, {"username": self.username})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("error", response.json())

        response = self._post_json(url, {"password": self.password})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("error", response.json())
