from django.test import TestCase
from django.core.exceptions import ValidationError
from authentication.models import User

class UserModelTest(TestCase):

    def setUp(self):
        # Unverfied user
        self.user = User.objects.create(
            username="testuser",
            password="password123",
            display_name="Test User",
            email="test@example.com",
            is_verified=False,
            roles=["admin", "researcher"],
        )

        # Verified user
        self.verified_user = User.objects.create(
            username="verifieduser",
            password="password123",
            display_name="Verified User",
            email="verified@example.com",
            is_verified=True,
            roles=["admin", "researcher"],
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

    def test_user_str_method(self):
        """Test __str__ method returns username"""
        self.assertEqual(str(self.user), "testuser")
        self.assertEqual(str(self.verified_user), "verifieduser")

    def test_is_authenticated_property_comprehensive(self):
        """Test is_authenticated property thoroughly"""
        # Unverified user should not be authenticated
        self.assertFalse(self.user.is_authenticated)
        
        # Verified user should be authenticated
        self.assertTrue(self.verified_user.is_authenticated)
        
        # Test edge case: user without user_id
        temp_user = User(
            username="temp",
            password="password123",
            email="temp@example.com"
        )
        # Before saving (no user_id)
        self.assertFalse(temp_user.is_authenticated)
        
        # Save and test again
        temp_user.save()
        # Still not authenticated because not verified
        self.assertFalse(temp_user.is_authenticated)
        
        # Verify user
        temp_user.is_verified = True
        temp_user.save()
        self.assertTrue(temp_user.is_authenticated)