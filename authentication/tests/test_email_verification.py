from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch
from django.contrib.auth.hashers import make_password
from authentication.models import User
from django.utils import timezone
from datetime import timedelta
import uuid


class EmailVerificationTest(TestCase):
    """Test suite for email verification functionality"""
    
    def setUp(self):
        self.client = Client()
        
        # Create test user that is already verified
        self.verified_user = User.objects.create(
            username="verified_user",
            password=make_password("testpass123"),
            display_name="Verified User",
            email="verified@example.com",
            is_verified=True,
            roles=["user"]
        )

    @patch('authentication.views.send_welcome_email')
    def test_verify_email_success(self, mock_email):
        """Test successful email verification"""
        mock_email.return_value = True
        
        # Create an unverified user
        unverified_user = User.objects.create(
            username="unverified",
            password=make_password("testpass123"),
            display_name="Unverified User",
            email="unverified@example.com",
            is_verified=False,
            roles=["user"]
        )
        
        verify_url = reverse('authentication:verify_email', kwargs={'token': unverified_user.verification_token})
        
        response = self.client.post(verify_url)
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data['success'])
        self.assertIn('message', response_data)
        self.assertIn('details', response_data)
        self.assertEqual(response_data['message'], 'Email verified successfully! Welcome email sent.')
        
        # Verify the user is now verified in database
        unverified_user.refresh_from_db()
        self.assertTrue(unverified_user.is_verified)
        
        # Verify welcome email was sent
        mock_email.assert_called_once_with(unverified_user)

    def test_verify_email_invalid_token(self):
        """Test email verification with invalid token"""
        invalid_token = uuid.uuid4()
        verify_url = reverse('authentication:verify_email', kwargs={'token': invalid_token})
        
        response = self.client.post(verify_url)
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('error', response_data)
        self.assertEqual(response_data['error'], 'Invalid token')

    @patch('authentication.views.send_welcome_email')
    def test_verify_email_already_verified(self, mock_email):
        """Test email verification when user is already verified"""
        mock_email.return_value = True
        
        # Use the already verified user from setUp
        verify_url = reverse('authentication:verify_email', kwargs={'token': self.verified_user.verification_token})
        
        response = self.client.post(verify_url)
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertEqual(response_data['message'], 'Already verified')
        
        # Verify welcome email was not sent since user was already verified
        mock_email.assert_not_called()

    @patch('authentication.views.send_welcome_email')
    def test_verify_email_welcome_email_failure(self, mock_email):
        """Test email verification when welcome email fails to send"""
        mock_email.return_value = False  # Simulate email sending failure
        
        # Create an unverified user
        unverified_user = User.objects.create(
            username="unverified2",
            password=make_password("testpass123"),
            display_name="Unverified User 2",
            email="unverified2@example.com",
            is_verified=False,
            roles=["user"]
        )
        
        verify_url = reverse('authentication:verify_email', kwargs={'token': unverified_user.verification_token})
        
        response = self.client.post(verify_url)
        
        # Verification should still succeed even if email fails
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data['success'])
        
        # User should still be verified in database
        unverified_user.refresh_from_db()
        self.assertTrue(unverified_user.is_verified)
        
        # Welcome email was attempted
        mock_email.assert_called_once_with(unverified_user)

    def test_verify_email_get_method_not_allowed(self):
        """Test that GET method is not allowed for email verification"""
        verify_url = reverse('authentication:verify_email', kwargs={'token': self.verified_user.verification_token})
        
        response = self.client.get(verify_url)
        
        # Should return 405 Method Not Allowed since view requires POST
        self.assertEqual(response.status_code, 405)

    def test_email_verification_fields_on_user_model(self):
        """Test that email verification fields exist and work properly on User model"""
        # Create unverified user
        user = User.objects.create(
            username="testverification",
            password="password123",
            display_name="Test Verification",
            email="testverification@example.com",
            is_verified=False
        )
        
        # By default, user should not be verified
        self.assertFalse(user.is_verified)
        self.assertIsNotNone(user.verification_token)
        self.assertFalse(user.is_authenticated)  # Should not be authenticated if unverified

        # Simulate verifying the user
        user.is_verified = True
        user.save()

        # Reload from DB to confirm
        refreshed = User.objects.get(pk=user.user_id)
        self.assertTrue(refreshed.is_verified)
        self.assertTrue(refreshed.is_authenticated)  # Should be authenticated after verification

    def test_verification_token_uniqueness(self):
        """Test that verification tokens are unique across users"""
        user1 = User.objects.create(
            username="user1",
            password="password123",
            email="user1@example.com"
        )
        user2 = User.objects.create(
            username="user2",
            password="password123",
            email="user2@example.com"
        )
        
        # Verification tokens should be different
        self.assertNotEqual(user1.verification_token, user2.verification_token)
        
        # Both should be valid UUIDs
        self.assertIsInstance(user1.verification_token, uuid.UUID)
        self.assertIsInstance(user2.verification_token, uuid.UUID)

    def test_email_verification_fields(self):
        """Test that email verification fields exist and work properly on User model"""
        # Create unverified user
        user = User.objects.create(
            username="testverification",
            password="password123",
            display_name="Test Verification",
            email="testverification@example.com",
            is_verified=False
        )
        
        # By default, user should not be verified
        self.assertFalse(user.is_verified)
        self.assertIsNotNone(user.verification_token)
        self.assertFalse(user.is_authenticated)  # Should not be authenticated if unverified

        # Simulate verifying the user
        user.is_verified = True
        user.save()

        # Reload from DB to confirm
        refreshed = User.objects.get(pk=user.user_id)
        self.assertTrue(refreshed.is_verified)
        self.assertTrue(refreshed.is_authenticated)  # Should be authenticated after verification

    def test_generate_otp(self):
        """Test OTP generation"""
        user = User.objects.create(
            username="otpuser",
            password="password123",
            display_name="OTP User",
            email="otp@example.com",
            is_verified=False
        )
        
        otp_code = user.generate_otp()
        
        # Check OTP code is generated
        self.assertIsNotNone(otp_code)
        self.assertEqual(len(otp_code), 6)
        self.assertTrue(otp_code.isdigit())
        
        # Check OTP fields are set
        user.refresh_from_db()
        self.assertEqual(user.otp_code, otp_code)
        self.assertIsNotNone(user.otp_expires_at)

    def test_verify_otp_success(self):
        """Test successful OTP verification"""
        user = User.objects.create(
            username="otpuser2",
            password="password123",
            display_name="OTP User 2",
            email="otp2@example.com",
            is_verified=False
        )
        
        # Generate OTP
        otp_code = user.generate_otp()
        
        # Verify OTP
        result = user.verify_otp(otp_code)
        
        self.assertTrue(result)
        user.refresh_from_db()
        self.assertTrue(user.is_verified)
        self.assertIsNone(user.otp_code)
        self.assertIsNone(user.otp_expires_at)

    def test_verify_otp_invalid_code(self):
        """Test OTP verification with invalid code"""
        user = User.objects.create(
            username="otpuser3",
            password="password123",
            display_name="OTP User 3",
            email="otp3@example.com",
            is_verified=False
        )
        
        # Generate OTP
        user.generate_otp()
        
        # Try with wrong code
        result = user.verify_otp("wrong_code")
        
        self.assertFalse(result)
        user.refresh_from_db()
        self.assertFalse(user.is_verified)

    def test_verify_otp_expired(self):
        """Test OTP verification with expired code"""
        from django.utils import timezone
        from datetime import timedelta
        
        user = User.objects.create(
            username="otpuser4",
            password="password123",
            display_name="OTP User 4",
            email="otp4@example.com",
            is_verified=False
        )
        
        # Generate OTP and manually set it as expired
        otp_code = user.generate_otp()
        user.otp_expires_at = timezone.now() - timedelta(minutes=1)
        user.save()
        
        # Try to verify expired OTP
        result = user.verify_otp(otp_code)
        
        self.assertFalse(result)
        user.refresh_from_db()
        self.assertFalse(user.is_verified)
        # OTP should be cleared when expired
        self.assertIsNone(user.otp_code)
        self.assertIsNone(user.otp_expires_at)

    def test_is_otp_expired(self):
        """Test OTP expiry check"""
        from django.utils import timezone
        from datetime import timedelta
        
        user = User.objects.create(
            username="otpuser5",
            password="password123",
            display_name="OTP User 5",
            email="otp5@example.com",
            is_verified=False
        )
        
        # No OTP set
        self.assertTrue(user.is_otp_expired())
        
        # Valid OTP
        user.generate_otp()
        self.assertFalse(user.is_otp_expired())
        
        # Expired OTP
        user.otp_expires_at = timezone.now() - timedelta(minutes=1)
        user.save()
        self.assertTrue(user.is_otp_expired())

    def test_user_str_method(self):
        """Test User model __str__ method"""
        user = User.objects.create(
            username="teststr",
            password="password123",
            display_name="Test Str",
            email="teststr@example.com"
        )
        self.assertEqual(str(user), "teststr")

    def test_is_authenticated_property_edge_cases(self):
        """Test is_authenticated property with various edge cases"""
        # Create user without user_id (simulate edge case)
        user = User.objects.create(
            username="authtest",
            password="password123", 
            display_name="Auth Test",
            email="authtest@example.com",
            is_verified=False
        )
        
        # Test unverified user
        self.assertFalse(user.is_authenticated)
        
        # Test verified user
        user.is_verified = True
        user.save()
        self.assertTrue(user.is_authenticated)
        
        # Test simulated missing user_id case by setting it to None
        # Note: We can't actually save this to DB due to constraints
        # but we can test the property logic
        original_user_id = user.user_id
        user.user_id = None  # Simulate missing user_id
        self.assertFalse(user.is_authenticated)
        
        # Restore user_id for further testing
        user.user_id = original_user_id
        user.is_verified = True
        self.assertTrue(user.is_authenticated)
        
        # Test simulated missing created_at case
        original_created_at = user.created_at
        user.created_at = None  # Simulate missing created_at
        self.assertFalse(user.is_authenticated)
        
        # Restore for cleanup
        user.created_at = original_created_at

    def test_generate_otp_custom_validity(self):
        """Test OTP generation with custom validity period"""
        user = User.objects.create(
            username="otpcustom",
            password="password123",
            display_name="OTP Custom",
            email="otpcustom@example.com"
        )
        
        # Test with custom validity (5 minutes)
        otp_code = user.generate_otp(otp_validity_minutes=5)
        
        self.assertIsNotNone(otp_code)
        self.assertEqual(len(otp_code), 6)
        self.assertTrue(otp_code.isdigit())
        
        # Check expiry time is approximately 5 minutes from now
        user.refresh_from_db()
        time_diff = user.otp_expires_at - timezone.now()
        self.assertAlmostEqual(time_diff.total_seconds(), 5 * 60, delta=10)

    def test_verify_otp_no_otp_set(self):
        """Test verify_otp when no OTP is set"""
        user = User.objects.create(
            username="nootp",
            password="password123",
            display_name="No OTP",
            email="nootp@example.com"
        )
        
        # Try to verify OTP when none is set
        result = user.verify_otp("123456")
        self.assertFalse(result)

    def test_verify_otp_no_expiry_set(self):
        """Test verify_otp when OTP code exists but no expiry"""
        user = User.objects.create(
            username="noexpiry",
            password="password123",
            display_name="No Expiry",
            email="noexpiry@example.com"
        )
        
        # Set OTP code but no expiry
        user.otp_code = "123456"
        user.otp_expires_at = None
        user.save()
        
        result = user.verify_otp("123456")
        self.assertFalse(result)

    def test_is_otp_expired_no_expiry(self):
        """Test is_otp_expired when no expiry is set"""
        user = User.objects.create(
            username="noexp",
            password="password123",
            display_name="No Exp",
            email="noexp@example.com"
        )
        
        # No expiry set should be considered expired
        self.assertTrue(user.is_otp_expired())