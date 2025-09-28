from django.test import TestCase, Client
from authentication.models import User
from django.urls import reverse
from django.contrib.auth import get_user_model
import json

User = get_user_model()

class AuthMiddlewareTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.protected_url = '/api/protected-endpoint/'  # Replace with your protected endpoint
        
    def test_unauthenticated_user_denied_access(self):
        """Test that unauthenticated users are denied access to protected endpoints"""
        response = self.client.get(self.protected_url)
        self.assertEqual(response.status_code, 401)  # Or 403 depending on your implementation
        
    def test_authenticated_user_allowed_access(self):
        """Test that authenticated users can access protected endpoints"""
        # Log in the user
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(self.protected_url)
        self.assertNotEqual(response.status_code, 401)
        self.assertNotEqual(response.status_code, 403)
        
    def test_invalid_session_denied_access(self):
        """Test that invalid/expired sessions are denied access"""
        # Login first
        self.client.login(username='testuser', password='testpass123')
        
        # Clear session to simulate expired/invalid session
        self.client.logout()
        
        response = self.client.get(self.protected_url)
        self.assertEqual(response.status_code, 401)  # Or 403
        
    def test_middleware_sets_user_context(self):
        """Test that middleware properly sets user context"""
        self.client.login(username='testuser', password='testpass123')
        
        # This would depend on your specific middleware implementation
        # You might check if request.user is properly set in your views
        response = self.client.get(self.protected_url)
        
        # Check if user context is available (implementation specific)
        # self.assertContains(response, 'testuser')  # Example