import json
from django.test import TestCase, RequestFactory
from django.http import JsonResponse
from authentication.models import User
from authentication.helpers import (
    parse_json_body,
    get_user_or_none,
    handle_failed_login,
    set_user_session,
    build_success_response
)


class ParseJsonBodyTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_returns_empty_dict_for_empty_body(self):
        """Return empty dict and None when body is empty"""
        request = self.factory.post("/login", data=b'')
        data, error = parse_json_body(request)
        self.assertEqual(data, {})
        self.assertIsNone(error)

    def test_returns_json_data_when_valid_json(self):
        """Return parsed JSON dict when body is valid JSON"""
        payload = {"username": "alice"}
        request = self.factory.post("/login", data=json.dumps(payload), content_type="application/json")
        data, error = parse_json_body(request)
        self.assertEqual(data, payload)
        self.assertIsNone(error)

    def test_returns_error_response_for_invalid_json(self):
        """Return error JsonResponse when JSON is invalid"""
        request = self.factory.post("/login", data=b'{"invalid_json": ', content_type="application/json")
        data, error = parse_json_body(request)
        self.assertIsNone(data)
        self.assertIsInstance(error, JsonResponse)
        self.assertEqual(error.status_code, 400)
        self.assertIn("invalid payload", error.content.decode())


class GetUserOrNoneTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="testuser", password="12345")

    def test_returns_user_when_exists(self):
        """Return user when username exists"""
        found = get_user_or_none("testuser")
        self.assertEqual(found, self.user)

    def test_returns_none_when_user_not_found(self):
        """Return None when user does not exist"""
        self.assertIsNone(get_user_or_none("nonexistent"))


class HandleFailedLoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="lockeduser", password="12345")

    def test_returns_locked_response_when_account_locked(self):
        """Return 423 when increment_failed_login locks the account"""
        self.user.increment_failed_login = lambda: True
        response = handle_failed_login(self.user)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 423)
        self.assertIn("locked", response.content.decode())

    def test_returns_invalid_credentials_response_when_not_locked(self):
        """Return 401 when account not locked"""
        self.user.increment_failed_login = lambda: False
        response = handle_failed_login(self.user)
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid credentials", response.content.decode())


class SetUserSessionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create(
            username="session_user",
            password="pass",
            display_name="Session Test",
            email="session@example.com"
        )

    def test_sets_user_session_fields(self):
        """Set user_id and username in session"""
        request = self.factory.get("/dummy")
        request.session = {}
        set_user_session(request, self.user)
        self.assertEqual(request.session["user_id"], str(self.user.user_id))
        self.assertEqual(request.session["username"], self.user.username)


class BuildSuccessResponseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username="success_user",
            password="pass",
            display_name="Success User",
            email="success@example.com"
        )

    def test_returns_expected_response_structure(self):
        """Should return dictionary with expected login success fields"""
        response = build_success_response(self.user)
        self.assertEqual(response["user_id"], f"user {self.user.user_id}")
        self.assertEqual(response["username"], self.user.username)
        self.assertEqual(response["display_name"], self.user.display_name)
        self.assertEqual(response["email"], self.user.email)
        self.assertEqual(response["message"], "Login successful")