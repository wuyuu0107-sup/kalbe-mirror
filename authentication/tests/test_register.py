from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch
from django.contrib.auth.models import User
import json

# Create your tests here.
class RegisterEndpointTests(TestCase):
    def setUp(self):  
        self.client = Client()
        self.url_name = "authentication:register"
    
    def _post_json(self, url, payload:dict):
        return self.client.post(
            url, 
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_register_user_success(self):
        try:
            url = reverse(self.url_name)
        except NoReverseMatch as e:
            self.fail(f"{self.url_name} is not defined")

        payload = {"username": "dummy", "password": "dummy_pass"}
        response = self._post_json(url, payload)

        self.assertEqual(response.status_code, 201, response.content)

        # User is created once
        self.assertEqual(User.objects.filter(username="dummy").count(), 1)
        user = User.objects.get(username="dummy")

        # Password is hashed & works with check_password
        self.assertNotEqual(user.password, "dummy_pass")
        self.assertTrue(user.check_password("dummy_pass"))

    def test_missing_fields_returns_400(self):
        url = reverse(self.url_name)

        # No username
        response = self._post_json(url, {"password": "dummy_pass"})
        self.assertEqual(response.status_code, 400, response.content)

        # No password
        response = self._post_json(url, {"username": "dummy"})
        self.assertEqual(response.status_code, 400, response.content)
    
    def test_disallows_blank_username_or_password(self):
        url = reverse(self.url_name)
        for payload in (
            {"username": "", "password": "x"},
            {"username": "x", "password": ""},
        ):
            r = self._post_json(url, payload)
            self.assertEqual(r.status_code, 400, r.content)


