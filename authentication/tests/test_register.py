from django.test import TestCase, Client
from django.urls import reverse
from authentication.models import User
from django.contrib.auth.hashers import check_password
import json

# to run test, enter in terminal:
# coverage run --source=authentication manage.py test authentication.tests.test_register --settings=kalbe_be.test_settings

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
        url = reverse(self.url_name)

        payload = {
            "username": "dummy",
            "password": "Dummy_pass1",
            "confirm_password": "Dummy_pass1",
            "display_name": "Dummy User",
            "email": "dummy@example.com",
        }
        response = self._post_json(url, payload)

        self.assertEqual(response.status_code, 201, response.content)

        # User is created once
        self.assertEqual(User.objects.filter(username="dummy").count(), 1)
        user = User.objects.get(username="dummy")

        # Password is hashed & works with check_password
        self.assertNotEqual(user.password, "Dummy_pass1")
        self.assertTrue(check_password("Dummy_pass1", user.password))

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

    def test_whitespace_only_fields_returns_400(self):
        """Test that whitespace-only username/password are rejected"""
        url = reverse(self.url_name)
        for payload in (
            {"username": "   ", "password": "valid_pass"},
            {"username": "valid_user", "password": "   "},
            {"username": "   ", "password": "   "},
        ):
            r = self._post_json(url, payload)
            self.assertEqual(r.status_code, 400, r.content)

    def test_invalid_json_returns_400(self):
        """Test that invalid JSON payload returns 400"""
        url = reverse(self.url_name)
        response = self.client.post(
            url,
            data="invalid json{",
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_empty_request_body_returns_400(self):
        """Test that empty request body returns 400"""
        url = reverse(self.url_name)
        response = self.client.post(
            url,
            data="",
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_duplicate_username_handling(self):
        """Test behavior when username already exists"""
        url = reverse(self.url_name)
        
        # Create first user
        payload = {
            "username": "duplicate_user",
            "password": "HollowKn1ght",
            "confirm_password": "HollowKn1ght",
            "display_name": "Hornet Lover",
            "email": "fake@example.com",
        }
        response1 = self._post_json(url, payload)
        self.assertEqual(response1.status_code, 201)
        
        # Try to create user with same username
        payload2 = {
            "username": "duplicate_user",
            "password": "HollowKn2ght",
            "confirm_password": "HollowKn2ght",
            "display_name": "Hornet Hater",
            "email": "fake2@example.com",
        }
        response2 = self._post_json(url, payload2)
        
        # This will likely cause an IntegrityError - you may want to handle this in your view
        # For now, we just ensure only one user exists
        self.assertIn(response2.status_code, [400, 409])
        self.assertEqual(User.objects.filter(username="duplicate_user").count(), 1)

    def test_response_content_structure(self):
        """Test that successful response has correct structure"""
        url = reverse(self.url_name)
        payload = {
            "username": "test_structure",
            "password": "T3st_pass1",
            "confirm_password": "T3st_pass1",
            "display_name": "Test Structure",
            "email": "structure@example.com",
        }
        response = self._post_json(url, payload)
        
        self.assertEqual(response.status_code, 201)
        response_data = json.loads(response.content)
        
        # Check response has expected keys
        self.assertIn("user_id", response_data)
        self.assertIn("message", response_data)
        self.assertEqual(response_data["message"], "Registration is successful. Please log in")
        
        # Check user_id format
        user = User.objects.get(username="test_structure")
        expected_user_id = f"user {user.user_id}"
        self.assertEqual(response_data["user_id"], expected_user_id)

    def test_non_post_methods_not_allowed(self):
        """Test that non-POST methods return 405 Method Not Allowed"""
        url = reverse(self.url_name)
        
        # Test GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        
        # Test PUT request
        response = self.client.put(url)
        self.assertEqual(response.status_code, 405)
        
        # Test DELETE request
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 405)


