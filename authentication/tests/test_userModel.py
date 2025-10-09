from django.test import TestCase, Client
from django.core.exceptions import ValidationError
from django.urls import reverse
from authentication.models import User
from django.contrib.auth.hashers import make_password
from unittest.mock import patch
import uuid

class UserModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create(
            username="testuser",
            password="strongpassword",
            display_name="Test User",
            email="test@example.com",
            roles=["admin", "researcher"]
        )

    def test_user_creation(self):
        #User should be created successfully with valid data
        self.assertEqual(self.user.username, "testuser")
        self.assertEqual(self.user.display_name, "Test User")
        self.assertEqual(self.user.email, "test@example.com")
        self.assertEqual(self.user.roles, ["admin", "researcher"])
        self.assertIsNotNone(self.user.user_id)

    def test_unique_username(self):
        #Usernames must be unique
        with self.assertRaises(Exception):
            User.objects.create(
                username="testuser",  # same username
                password="anotherpassword",
                display_name="Another",
                email="unique@example.com"
            )

    def test_unique_email(self):
        #Emails must be unique
        with self.assertRaises(Exception):
            User.objects.create(
                username="uniqueuser",
                password="anotherpassword",
                display_name="Another",
                email="test@example.com"  # same email
            )

    def test_password_min_length(self):
        #Password must have at least 8 characters
        user = User(
            username="shortpass",
            password="123",  # too short
            display_name="Short Pass",
            email="short@example.com"
        )
        with self.assertRaises(ValidationError):
            user.full_clean()  # triggers field validation

    def test_str_method(self):
        #__str__ should return username
        self.assertEqual(str(self.user), "testuser")

    def test_last_accessed_auto_update(self):
        #last_accessed should update automatically
        old_timestamp = self.user.last_accessed
        self.user.display_name = "Updated Name"
        self.user.save()
        self.assertGreaterEqual(self.user.last_accessed, old_timestamp)


class VerifyEmailTest(TestCase):
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
