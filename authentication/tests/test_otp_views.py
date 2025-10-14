from django.test import TestCase, Client
from django.urls import reverse
from authentication.models import User
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
import json


class OTPViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test user with OTP
        self.user = User.objects.create(
            username="testuser",
            password="password123",
            display_name="Test User",
            email="test@example.com",
            is_verified=False,
        )
        
        # Create already verified user
        self.verified_user = User.objects.create(
            username="verifieduser",
            password="password123",
            display_name="Verified User",
            email="verified@example.com",
            is_verified=True,
        )

    def test_verify_otp_missing_fields(self):
        """Test verify OTP with missing required fields"""
        # Missing username
        response = self.client.post(
            reverse('authentication:verify_otp'),
            data=json.dumps({"otp_code": "123456"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Username and OTP code are required", response.json()["error"])
        
        # Missing OTP code
        response = self.client.post(
            reverse('authentication:verify_otp'),
            data=json.dumps({"username": "testuser"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Username and OTP code are required", response.json()["error"])

    def test_verify_otp_invalid_json(self):
        """Test verify OTP with invalid JSON"""
        response = self.client.post(
            reverse('authentication:verify_otp'),
            data="invalid json",
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid JSON", response.json()["error"])

    def test_verify_otp_user_not_found(self):
        """Test verify OTP with non-existent user"""
        response = self.client.post(
            reverse('authentication:verify_otp'),
            data=json.dumps({
                "username": "nonexistent", 
                "otp_code": "123456"
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("User not found", response.json()["error"])

    def test_verify_otp_already_verified(self):
        """Test verify OTP for already verified user"""
        response = self.client.post(
            reverse('authentication:verify_otp'),
            data=json.dumps({
                "username": "verifieduser", 
                "otp_code": "123456"
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Account already verified", response.json()["message"])

    @patch('authentication.views.send_welcome_email')
    def test_verify_otp_success(self, mock_welcome_email):
        """Test successful OTP verification"""
        mock_welcome_email.return_value = True
        
        # Generate OTP for user
        self.user.generate_otp()
        otp_code = self.user.otp_code
        
        response = self.client.post(
            reverse('authentication:verify_otp'),
            data=json.dumps({
                "username": "testuser", 
                "otp_code": otp_code
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("Email verified successfully", data["message"])
        self.assertTrue(data["welcome_email_sent"])
        
        # Check user is now verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)

    def test_verify_otp_expired(self):
        """Test verify OTP with expired code"""
        # Set expired OTP
        self.user.otp_code = "123456"
        self.user.otp_expires_at = timezone.now() - timedelta(minutes=1)
        self.user.save()
        
        response = self.client.post(
            reverse('authentication:verify_otp'),
            data=json.dumps({
                "username": "testuser", 
                "otp_code": "123456"
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("OTP code has expired", response.json()["error"])

    def test_verify_otp_invalid_code(self):
        """Test verify OTP with invalid code"""
        # Generate valid OTP but use wrong code
        self.user.generate_otp()
        
        response = self.client.post(
            reverse('authentication:verify_otp'),
            data=json.dumps({
                "username": "testuser", 
                "otp_code": "wrong_code"
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid OTP code", response.json()["error"])

    # Tests for resend_otp view
    def test_resend_otp_missing_username(self):
        """Test resend OTP without username"""
        response = self.client.post(
            reverse('authentication:resend_otp'),
            data=json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Username is required", response.json()["error"])

    def test_resend_otp_invalid_json(self):
        """Test resend OTP with invalid JSON"""
        response = self.client.post(
            reverse('authentication:resend_otp'),
            data="invalid json",
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid JSON", response.json()["error"])

    def test_resend_otp_user_not_found(self):
        """Test resend OTP for non-existent user"""
        response = self.client.post(
            reverse('authentication:resend_otp'),
            data=json.dumps({"username": "nonexistent"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("User not found", response.json()["error"])

    def test_resend_otp_already_verified(self):
        """Test resend OTP for already verified user"""
        response = self.client.post(
            reverse('authentication:resend_otp'),
            data=json.dumps({"username": "verifieduser"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Account already verified", response.json()["message"])

    @patch('authentication.views.send_otp_email')
    def test_resend_otp_success(self, mock_send_otp):
        """Test successful OTP resend"""
        mock_send_otp.return_value = True
        
        response = self.client.post(
            reverse('authentication:resend_otp'),
            data=json.dumps({"username": "testuser"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("New OTP code sent", data["message"])

    @patch('authentication.views.send_otp_email')
    def test_resend_otp_email_failure(self, mock_send_otp):
        """Test resend OTP when email sending fails"""
        mock_send_otp.return_value = False
        
        response = self.client.post(
            reverse('authentication:resend_otp'),
            data=json.dumps({"username": "testuser"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to send OTP email", response.json()["error"])


class VerifyEmailViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test user with verification token
        self.user = User.objects.create(
            username="testuser",
            password="password123",
            display_name="Test User",
            email="test@example.com",
            is_verified=False,
        )
        
        # Create already verified user
        self.verified_user = User.objects.create(
            username="verifieduser",
            password="password123",
            display_name="Verified User",
            email="verified@example.com",
            is_verified=True,
        )

    def test_verify_email_invalid_token(self):
        """Test verify email with invalid token"""
        invalid_token = "00000000-0000-0000-0000-000000000000"
        response = self.client.post(
            reverse('authentication:verify_email', kwargs={'token': invalid_token})
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid token", response.json()["error"])

    def test_verify_email_already_verified(self):
        """Test verify email for already verified user"""
        response = self.client.post(
            reverse('authentication:verify_email', kwargs={'token': str(self.verified_user.verification_token)})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Already verified", response.json()["message"])

    @patch('authentication.views.send_welcome_email')
    def test_verify_email_success(self, mock_welcome_email):
        """Test successful email verification"""
        mock_welcome_email.return_value = True
        
        response = self.client.post(
            reverse('authentication:verify_email', kwargs={'token': str(self.user.verification_token)})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("Email verified successfully", data["message"])
        
        # Check user is now verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)