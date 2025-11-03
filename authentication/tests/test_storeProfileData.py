import json
from django.test import TestCase, Client
from django.urls import reverse
from django.db import IntegrityError
from django.contrib.auth.hashers import check_password
from unittest.mock import patch

from authentication.models import User

class RegisterEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url_name = "authentication:register"

    def _post_json(self, url, payload: dict):
        return self.client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )
    
    # ----- Happy Path ----- #
    def test_register_stores_profile_and_hashes_password(self):
        url = reverse(self.url_name)
        
        payload = {
            "username": "dummy",
            "password": "Pass_dummy1",
            "confirm_password": "Pass_dummy1",
            "display_name": "dummy dummy",
            "email": "dummy@gmail.com",
            "roles": ["researcher"]
        }
        r = self._post_json(url, payload)
        self.assertEqual(r.status_code, 201, r.content)

        # Created once
        self.assertEqual(User.objects.filter(username="dummy").count(), 1)
        u = User.objects.get(username="dummy")

        # Profile fields stored
        self.assertEqual(u.display_name, "dummy dummy")
        self.assertEqual(u.email, "dummy@gmail.com")
        self.assertEqual(u.roles, ["researcher"])

        # Password hashed, check_password works on encoded string
        self.assertNotEqual(u.password, payload["password"])
        self.assertTrue(check_password("Pass_dummy1", u.password))

    # ----- Uniqueness ----- #
    def test_duplicate_username_reject(self):
        url = reverse(self.url_name)

        # First user
        payload_1 = {
            "username": "duplicate",
            "password": "Pass_dummy1",
            "confirm_password": "Pass_dummy1",
            "display_name": "dummy dummy",
            "email": "dummy@gmail.com",
            "roles": ["researcher"]
        }
        r1 = self._post_json(url, payload_1)
        self.assertEqual(r1.status_code, 201, r1.content)

        # Second user (duplicate username)
        payload_2 = {
            "username": "duplicate",
            "password": "duplicate_user",
            "confirm_password": "duplicate_user",
            "display_name": "Duplicate",
            "email": "duplicate_dummy@gmail.com",
            "roles": ["researcher"]
        }
        r2 = self._post_json(url, payload_2)
        self.assertIn(r2.status_code, (400,409), r2.content)
        self.assertEqual(User.objects.filter(username="duplicate").count(), 1)

    def test_duplicate_email_reject(self):
        url = reverse(self.url_name)

        # First user
        payload_1 = {
            "username": "dummy1",
            "password": "Pass_dummy1",
            "confirm_password": "Pass_dummy1",
            "display_name": "dummy dummy",
            "email": "dummy@gmail.com",
            "roles": ["researcher"]
        }
        r1 = self._post_json(url, payload_1)
        self.assertEqual(r1.status_code, 201, r1.content)

        # Second user (duplicate email)
        payload_2 = {
            "username": "dummy2",
            "password": "Pass_dummmy2",
            "confirm_password": "Pass_dummy2",
            "display_name": "dummy dum",
            "email": "dummy@gmail.com",
            "roles": ["researcher"]
        }
        r2 = self._post_json(url, payload_2)
        self.assertIn(r2.status_code, (400,409), r2.content)
    
    def test_duplicate_username_and_email_reject(self):
        url = reverse(self.url_name)

        r1 = self._post_json(url, {
            "username": "dupeboth",
            "password": "Pass_dummy1!",
            "confirm_password": "Pass_dummy1!",
            "display_name": "Dupe Both A",
            "email": "dupeboth@example.com",
            "roles": ["researcher"]
        })
        self.assertEqual(r1.status_code, 201, r1.content)

        r2 = self._post_json(url, {
            "username": "dupeboth",                 # duplicate username
            "password": "Pass_dummy2!",             
            "confirm_password": "Pass_dummy2!",
            "display_name": "Dupe Both B",
            "email": "dupeboth@example.com",        # duplicate email
            "roles": ["researcher"]
        })
        self.assertIn(r2.status_code, (400, 409), r2.content)
        self.assertEqual(User.objects.filter(username="dupeboth").count(), 1)
        self.assertEqual(User.objects.filter(email="dupeboth@example.com").count(), 1)
    
    def test_integrity_error_returns_409(self):
        url = reverse(self.url_name)
        payload = {
            "username": "dup_user",
            "password": "Pass_dummy1!",
            "confirm_password": "Pass_dummy1!",
            "display_name": "Dup User",
            "email": "dup@example.com",
            "roles": ["researcher"],
        }

        with patch("authentication.views.User.objects.create", side_effect=IntegrityError("duplicate")):
            resp = self._post_json(url, payload)

        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(resp.json(), {"error": "user already exists"})
    
    # ----- Input Validation ----- #
    def test_missing_blank_and_whitespace_fields_return_400(self):
        url = reverse(self.url_name)

        # missing required
        for payload in (
            {"password": "x", "display_name": "A", "email": "a@x.com"},
            {"username": "a", "display_name": "A", "email": "a@x.com"},
            {"username": "a", "password": "x", "email": "a@x.com"},
            {"username": "a", "password": "x", "display_name": "A"},
        ):
            r = self._post_json(url, payload)
            self.assertEqual(r.status_code, 400, r.content)

        # blank
        for payload in (
            {"username": "", "password": "x", "display_name": "A", "email": "a@x.com"},
            {"username": "a", "password": "", "display_name": "A", "email": "a@x.com"},
        ):
            r = self._post_json(url, payload)
            self.assertEqual(r.status_code, 400, r.content)

        # whitespace-only
        for payload in (
            {"username": "   ", "password": "valid_pass"},
            {"username": "valid_user", "password": "   "},
            {"username": "   ", "password": "   "},
        ):
            r = self._post_json(url, payload)
            self.assertEqual(r.status_code, 400, r.content)
    
    # ----- Response Errors ----- #
    def test_invalid_json_or_empty_body_returns_400(self):
        url = reverse(self.url_name)

        # invalid JSON
        r1 = self.client.post(url, data='{"username: "oops', content_type="application/json")
        self.assertEqual(r1.status_code, 400, r1.content)

        # empty body
        r2 = self.client.post(url, data="", content_type="application/json")
        self.assertEqual(r2.status_code, 400, r2.content)

    # ----- Method Guards / Error Branch ----- #
    def test_non_post_methods_not_allowed(self):
        url = reverse(self.url_name)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.put(url).status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)
    
    def test_patch_method_not_allowed(self):
        url = reverse(self.url_name)
        r = self.client.patch(url, data=json.dumps({}), content_type="application/json")
        self.assertEqual(r.status_code, 405)
    
    # ----- Password Validation ----- #
    def test_password_too_short_reject(self):
        url = reverse(self.url_name)
        payload = {
            "username": "shorty",
            "password": "1234567",  # 7 chars
            "confirm_password": "1234567",
            "display_name": "Short Y",
            "email": "short@example.com",
        }
        r = self._post_json(url, payload)
        self.assertEqual(r.status_code, 400, r.content)

        data = r.json()
        self.assertTrue("error" in data or "errors" in data, data)

    def test_password_mismatch_returns_400(self):
        url = reverse(self.url_name)
        r = self._post_json(url, {
            "username": "mismatch",
            "password": "Pass_dummy1!",
            "confirm_password": "Pass_dummy2!",
            "display_name": "Mismatch",
            "email": "mismatch@example.com",
            "roles": ["researcher"]
        })
        self.assertEqual(r.status_code, 400, r.content)
        data = r.json()
        self.assertTrue("error" in data or "errors" in data, data)
    
    def test_password_missing_uppercase_reject(self):
        url = reverse(self.url_name)
        r = self._post_json(url, {
            "username": "noupcase",
            "password": "pass_dummy1!",  
            "confirm_password": "pass_dummy1!",
            "display_name": "No Upcase",
            "email": "noupcase@example.com",
            "roles": ["researcher"]
        })
        self.assertEqual(r.status_code, 400, r.content)
    
    def test_password_missing_digit_reject(self):
        url = reverse(self.url_name)
        r = self._post_json(url, {
            "username": "nodigit",
            "password": "Pass_dummy!",
            "confirm_password": "Pass_dummy!",
            "display_name": "No Digit",
            "email": "nodigit@example.com",
            "roles": ["researcher"]
        })
        self.assertEqual(r.status_code, 400, r.content)
    
    # ----- Email Validation ----- #
    def test_invalid_email_format_reject(self):
        url = reverse(self.url_name)
        r = self._post_json(url, {
            "username": "bademail",
            "password": "Pass_dummy1!",
            "confirm_password": "Pass_dummy1!",
            "display_name": "Bad Email",
            "email": "not-an-email",
            "roles": ["researcher"]
        })
        self.assertEqual(r.status_code, 400, r.content)
    
    def test_email_is_normalized_to_lowercase(self):
        url = reverse(self.url_name)
        r = self._post_json(url, {
            "username": "casey",
            "password": "Pass_dummy1!",
            "confirm_password": "Pass_dummy1!",
            "display_name": "Casey",
            "email": "Casey@Example.COM",   # mixed case
            "roles": ["researcher"]
        })
        self.assertEqual(r.status_code, 201, r.content)
        u = User.objects.get(username="casey")
        self.assertEqual(u.email, "casey@example.com")