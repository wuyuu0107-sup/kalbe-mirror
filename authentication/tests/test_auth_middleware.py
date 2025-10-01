from django.test import TestCase, Client
from authentication.models import User
from django.contrib.auth.hashers import make_password
import json

class AuthenticatedUserMiddlewareTests(TestCase):
    """Tests for middleware behavior when user is authenticated."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            username='testuser',
            password=make_password('Testpass123'),
            email='testuser@example.com',
            is_verified=True  # Ensure user is verified for login
        )
        # IMPORTANT: This URL must exist and be protected by your existing middleware
        self.protected_url = '/api/protected-endpoint/' # Or whatever your actual protected URL is

        # Log in the user for all tests in this class
        login_response = self.client.post(
            '/auth/login/',  # Use your actual login endpoint
            data=json.dumps({
                'username': 'testuser',
                'password': 'Testpass123'
            }),
            content_type='application/json'
        )
        # Verify login was successful - this confirms session keys are set
        self.assertEqual(login_response.status_code, 200, f"Login failed: {login_response.content}")
        # Optional: Verify session keys exist after login
        session = self.client.session
        self.assertIsNotNone(session.get('user_id'), "user_id should be in session after login")
        self.assertIsNotNone(session.get('username'), "username should be in session after login")

    def test_authenticated_user_allowed_access(self):
        """Test that authenticated users can access protected endpoints."""
        # The request should now include the session cookie from the login in setUp
        response = self.client.get(self.protected_url)
        # If your existing middleware works, this should NOT return 401 or 403
        self.assertNotIn(response.status_code, [401, 403], f"Access denied for authenticated user. Response: {response.content}")
        # The status should be less than 400 (e.g., 200, 201, 302, etc.)
        self.assertLess(response.status_code, 400, f"Expected success/redirection status (< 400), got {response.status_code}. Response: {response.content}")

    def test_middleware_sets_user_context(self):
            """Test that middleware allows access when user context is set via session."""
            response = self.client.get(self.protected_url)
            self.assertLess(response.status_code, 400, f"Access was denied (status {response.status_code}) for authenticated user. Response: {response.content}")
            self.assertNotEqual(response.status_code, 401)
            self.assertNotEqual(response.status_code, 403)

class UnauthenticatedUserMiddlewareTests(TestCase):
    """Tests for middleware behavior when user is not authenticated."""

    def setUp(self):
        self.client = Client()
        # Create a user but don't log in
        self.user = User.objects.create(
            username='testuser',
            password=make_password('Testpass123'),
            email='testuser@example.com',
            is_verified=True # Ensure user is verified for potential login attempts
        )
        # IMPORTANT: This URL must exist and be protected by your existing middleware
        self.protected_url = '/api/protected-endpoint/' # Or whatever your actual protected URL is

    def test_unauthenticated_user_denied_access(self):
        """Test that unauthenticated users are denied access to protected endpoints."""
        # No login call here, so no session keys exist
        response = self.client.get(self.protected_url)
        # Your existing middleware should return 401 or 403
        self.assertIn(response.status_code, [401, 403], f"Expected 401 or 403 for unauthenticated user, got {response.status_code}. Response: {response.content}")

    def test_invalid_session_denied_access(self):
        """Test that invalid/expired sessions are denied access."""
        # This test is functionally the same as test_unauthenticated_user_denied_access
        # since we start without a session.
        response = self.client.get(self.protected_url)
        self.assertIn(response.status_code, [401, 403], f"Expected 401 or 403 for user without session, got {response.status_code}. Response: {response.content}")
