import json
from django.test import TestCase, Client
from django.urls import path, reverse, NoReverseMatch
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import check_password
from UserRegistration.models import User

class RegisterProfileTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url_name = "UserRegistration:register"

    def _post_json(self, url, payload: dict):
        return self.client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )
    
    def test_register_stores_profile_and_hashes_password(self):
        try:
            url = reverse(self.url_name)
        except NoReverseMatch:
            self.fail(f"URL name {self.url_name} not defined")
        
        payload = {
            "username": "dummy",
            "password": "pass_dummy",
            "display_name": "dummy dummy",
            "email": "dummy@gmail.com",
            "roles": ["researcher"]
        }
        r = self._post_json(url, payload)
        self.assertEqual(r.status_code, 201, r.content)

        # Created once
        self.assertEqual(User.objects.filter(username="alice").count(), 1)
        u = User.objects.get(username="dummy")

        # Profile fields stored
        self.assertEqual(u.display_name, "Dr.Alice Pharma")
        self.assertEqual(u.email, "dummy@gmail.com")
        self.assertEqual(u.roles, ["researcher"])

        # Password hashed, check_password works on encoded string
        self.assertNotEqual(u.password, payload["password"])
        self.assertTrue(check_password("pass_dummy", u.password))

        # response shape
        data = r.json()
        self.assertIn("user_id", data)
        self.assertIn("message", data)
    
    def test_duplicate_username_reject(self):
        User.objects.create(
            username="dummy",
            password="pbkdf2_sha256$dummy$hash",  # pre-existing row
            display_name="Existing",
            email="dummy@gmail.com",
            roles=[]
        )
        url = reverse(self.url_name)

        # duplicate username
        r = self._post_json(url, {
            "username": "dummy",
            "password": "dummy_testing",
            "display_name": "X",
            "email": "someone@gmail.com",
        })
        self.assertIn(r.status_code, (400, 409), r.content)

    def test_duplicate_email_reject(self):
        User.objects.create(
            username="dummy",
            password="pbkdf2_sha256$dummy$hash",  # pre-existing row
            display_name="Existing",
            email="dummy@gmail.com",
            roles=[]
        )
        url = reverse(self.url_name)
        
        # duplicate email
        r = self._post_json(url, {
            "username": "unique",
            "password": "X",
            "display_name": "Y",
            "email": "dummy@gmail.com",
        })
        self.assertIn(r.status_code, (400, 409), r.content)
    
    def test_missing_or_blank_fields_400(self):
        url = reverse(self.url_name)

        # missing any required field -> 400
        for payload in (
            {"password": "pass_dummy", "display_name": "A", "email": "a@x.com"},
            {"username": "a", "display_name": "A", "email": "a@x.com"},
            {"username": "a", "password": "pass_dummy", "email": "a@x.com"},
            {"username": "a", "password": "pass_dummy", "display_name": "A"},
        ):
            r = self._post_json(url, payload)
            self.assertEqual(r.status_code, 400, r.content)

        # blank username or password -> 400
        for payload in (
            {"username": "", "password": "pass_dummy", "display_name": "A", "email": "a@x.com"},
            {"username": "a", "password": "", "display_name": "A", "email": "a@x.com"},
        ):
            r = self._post_json(url, payload)
            self.assertEqual(r.status_code, 400, r.content)