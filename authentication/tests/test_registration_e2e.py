import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.hashers import check_password
from authentication.models import User


class RegistrationE2ETests(TestCase):
 
    def setUp(self):
        self.client = Client()
        self.registration_url = reverse("authentication:register")
    
    def test_registration_happy_path_e2e(self):
        """
        Test the complete happy path for user registration:
        1. Send valid registration data via API
        2. Verify successful response (201 Created)
        3. Verify user is created in database
        4. Verify password is properly hashed
        5. Verify all user data is stored correctly
        6. Verify user can login with the registered credentials
        """
        
        # Step 1: Prepare valid registration data
        registration_data = {
            "username": "johndoe123",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!", 
            "email": "john.doe@example.com",
            "display_name": "John Doe",
            "roles": ["user"]  # JSONField expects array/object, not string
        }
        
        # Step 2: Send registration request
        response = self.client.post(
            self.registration_url,
            data=json.dumps(registration_data),
            content_type="application/json"
        )
        
        # Step 3: Verify successful registration response
        self.assertEqual(response.status_code, 201, 
                        f"Expected 201 Created, got {response.status_code}. Response: {response.content}")
        
        response_data = response.json()
        self.assertIn("message", response_data)
        self.assertEqual(response_data["message"], "Registration is successful. Please log in")
        self.assertIn("user_id", response_data)
        
        # Step 4: Verify user exists in database
        user_exists = User.objects.filter(username="johndoe123").exists()
        self.assertTrue(user_exists, "User should be created in database")
        
        # Step 5: Get the created user and verify all data
        created_user = User.objects.get(username="johndoe123")
        
        # Verify basic user data
        self.assertEqual(created_user.username, "johndoe123")
        self.assertEqual(created_user.email, "john.doe@example.com")
        self.assertEqual(created_user.display_name, "John Doe")
        self.assertEqual(created_user.roles, ["user"])  # Should be an array
        
        # Step 6: Verify password is properly hashed (not stored in plain text)
        self.assertNotEqual(created_user.password, "SecurePass123!")  # Should be hashed
        self.assertTrue(check_password("SecurePass123!", created_user.password), 
                       "Password should be properly hashed and verifiable")
        
        # Step 7: Verify user defaults
        self.assertFalse(created_user.is_verified, "New user should not be verified by default")
        self.assertIsNotNone(created_user.verification_token, "Verification token should be generated")
        self.assertIsNotNone(created_user.user_id, "User ID should be generated")
        self.assertIsNotNone(created_user.last_accessed, "Last accessed should be set")
        
        # Step 8: Verify email before attempting login
        verify_url = reverse("authentication:verify_email", kwargs={"token": created_user.verification_token})
        verify_response = self.client.post(verify_url)  # POST instead of GET
        
        self.assertEqual(verify_response.status_code, 200,
                        f"Email verification should succeed. Response: {verify_response.content}")
        
        # Refresh user from database to get updated is_verified status
        created_user.refresh_from_db()
        self.assertTrue(created_user.is_verified, "User should be verified after email verification")
        
        # Step 9: Test that user can login after email verification
        login_url = reverse("authentication:login")
        login_data = {
            "username": "johndoe123",
            "password": "SecurePass123!"
        }
        
        login_response = self.client.post(
            login_url,
            data=json.dumps(login_data),
            content_type="application/json"
        )
        
        self.assertEqual(login_response.status_code, 200,
                        f"User should be able to login after registration and verification. Response: {login_response.content}")
        
        login_response_data = login_response.json()
        self.assertIn("message", login_response_data)
        self.assertEqual(login_response_data["message"], "Login successful")
        self.assertIn("user_id", login_response_data)
        
        # Step 10: Verify login response contains correct user info
        self.assertEqual(login_response_data["user_id"], f"user {created_user.user_id}")
    
    def test_registration_with_minimal_required_data(self):
        """
        Test registration with only the minimum required fields.
        """
        
        minimal_data = {
            "username": "minimaluser",
            "password": "MinPass123!",
            "confirm_password": "MinPass123!",
            "email": "minimal@example.com", 
            "display_name": "Minimal User"
            # No roles provided - should use default
        }
        
        response = self.client.post(
            self.registration_url,
            data=json.dumps(minimal_data),
            content_type="application/json"
        )
        
        # Should succeed with minimal data
        self.assertEqual(response.status_code, 201)
        
        # Verify user created
        created_user = User.objects.get(username="minimaluser")
        self.assertEqual(created_user.username, "minimaluser")
        self.assertEqual(created_user.email, "minimal@example.com")
        self.assertEqual(created_user.display_name, "Minimal User")
        
        # Verify defaults are applied
        self.assertEqual(created_user.roles, [])  # Default is empty list
        self.assertFalse(created_user.is_verified)
        self.assertIsNotNone(created_user.verification_token)
    
    def test_registration_generates_unique_identifiers(self):
        """
        Test that each registration generates unique user_id and verification_token.
        """
        
        # Register first user
        user1_data = {
            "username": "user1",
            "password": "Pass123!",
            "confirm_password": "Pass123!",
            "email": "user1@example.com",
            "display_name": "User One"
        }
        
        response1 = self.client.post(
            self.registration_url,
            data=json.dumps(user1_data),
            content_type="application/json"
        )
        self.assertEqual(response1.status_code, 201)
        
        # Register second user
        user2_data = {
            "username": "user2", 
            "password": "Pass123!",
            "confirm_password": "Pass123!",
            "email": "user2@example.com",
            "display_name": "User Two"
        }
        
        response2 = self.client.post(
            self.registration_url,
            data=json.dumps(user2_data),
            content_type="application/json"
        )
        self.assertEqual(response2.status_code, 201)
        
        # Get both users
        user1 = User.objects.get(username="user1")
        user2 = User.objects.get(username="user2")
        
        # Verify unique identifiers
        self.assertNotEqual(user1.user_id, user2.user_id, "User IDs should be unique")
        self.assertNotEqual(user1.verification_token, user2.verification_token, 
                           "Verification tokens should be unique")
        
        # Verify both can login independently (after email verification)
        for username, password in [("user1", "Pass123!"), ("user2", "Pass123!")]:
            # Verify email first
            user = User.objects.get(username=username)
            verify_url = reverse("authentication:verify_email", kwargs={"token": user.verification_token})
            verify_response = self.client.post(verify_url)  # POST instead of GET
            self.assertEqual(verify_response.status_code, 200)
            
            # Then login
            login_data = {"username": username, "password": password}
            login_response = self.client.post(
                reverse("authentication:login"),
                data=json.dumps(login_data),
                content_type="application/json"
            )
            self.assertEqual(login_response.status_code, 200, 
                           f"User {username} should be able to login after email verification")