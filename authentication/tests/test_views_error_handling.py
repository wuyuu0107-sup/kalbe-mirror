from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.hashers import make_password
from authentication.models import User
from unittest.mock import patch
import json


class ViewsErrorHandlingTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        self.user = User.objects.create(
            username="testuser",
            password=make_password("TestPassword123"),  # Properly hash the password
            display_name="Test User",
            email="test@example.com",
            is_verified=False,
        )

    @patch('authentication.views.send_mail')
    def test_send_otp_email_exception(self, mock_send_mail):
        """Test send_otp_email function when email sending fails"""
        from authentication.views import send_otp_email
        
        # Mock send_mail to raise an exception
        mock_send_mail.side_effect = Exception("Email server error")
        
        result = send_otp_email(self.user)
        self.assertFalse(result)

    @patch('authentication.views.send_mail')
    def test_send_welcome_email_exception(self, mock_send_mail):
        """Test send_welcome_email function when email sending fails"""
        from authentication.views import send_welcome_email
        
        # Mock send_mail to raise an exception
        mock_send_mail.side_effect = Exception("Email server error")
        
        result = send_welcome_email(self.user)
        self.assertFalse(result)

    def test_login_unverified_user_specific_path(self):
        """Test login path for unverified user - covers line 139"""
        # Test with unverified user (our main test user)
        # Use a password that meets validation requirements
        response = self.client.post(
            reverse('authentication:login'),
            data=json.dumps({
                "username": "testuser",
                "password": "TestPassword123"  # Meets all validation requirements
            }),
            content_type='application/json'
        )
        
        # Should return 403 for unverified user
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn("Email not verified", data["error"])
        self.assertIn("Please verify your email before logging in", data["message"])