from django.test import TestCase
from django.core.exceptions import ValidationError
from UserRegistration.models import User

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

    def test_email_verification_fields(self):
        # By default, user should not be verified
        self.assertFalse(self.user.is_verified)
        self.assertIsNotNone(self.user.verification_token)

        # Simulate verifying the user
        self.user.is_verified = True
        self.user.save()

        # Reload from DB to confirm
        refreshed = User.objects.get(pk=self.user.user_id)
        self.assertTrue(refreshed.is_verified)