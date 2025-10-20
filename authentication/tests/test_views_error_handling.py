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

    def test_login_account_locked_path(self):
        """Test login when account is locked - covers line 121"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Create verified user and lock account
        locked_user = User.objects.create(
            username="lockeduser",
            password=make_password("TestPassword123"),
            display_name="Locked User",
            email="locked@example.com",
            is_verified=True,
            failed_login_attempts=5,
            account_locked_until=timezone.now() + timedelta(minutes=30)
        )
        
        response = self.client.post(
            reverse('authentication:login'),
            data=json.dumps({
                "username": "lockeduser",
                "password": "TestPassword123"
            }),
            content_type='application/json'
        )
        
        # Should return 423 for locked account
        self.assertEqual(response.status_code, 423)
        data = response.json()
        self.assertIn("Account is temporarily locked due to too many failed attempts", data["error"])

    def test_login_unverified_email_path(self):
        """Test login when email is not verified - covers line 139"""
        # Create user with unverified email
        user = User.objects.create(
            username="unverified",
            password=make_password("TestPassword123"),
            display_name="Unverified",
            email="unverified@example.com",
            is_verified=False  # Email not verified
        )
        
        response = self.client.post(
            reverse('authentication:login'),
            data=json.dumps({
                "username": "unverified",
                "password": "TestPassword123"
            }),
            content_type='application/json'
        )
        
        # Should return 403 with email not verified message
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data["error"], "Email not verified")

    def test_login_account_locked_after_failed_attempts(self):
        """Test login when account gets locked after failed attempts - covers line 162"""
        # Create verified user with 4 failed attempts (one before lock)
        user = User.objects.create(
            username="almostlocked",
            password=make_password("TestPassword123"),
            display_name="Almost Locked",
            email="almostlocked@example.com",
            is_verified=True,
            failed_login_attempts=4
        )
        
        # Try login with wrong password (should lock account)
        response = self.client.post(
            reverse('authentication:login'),
            data=json.dumps({
                "username": "almostlocked",
                "password": "WrongPassword"
            }),
            content_type='application/json'
        )
        
        # Should return 423 for newly locked account
        self.assertEqual(response.status_code, 423)
        data = response.json()
        self.assertIn("Account is temporarily locked", data["error"])