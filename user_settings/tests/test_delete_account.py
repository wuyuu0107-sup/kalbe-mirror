import json
import uuid
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth.hashers import make_password, check_password
from django.http import JsonResponse
from authentication.models import User
from ..serializers import DeleteAccountSerializer
from ..services.passwords import AccountDeletionResult
from ..views import get_authenticated_user


class DeleteAccountTestCase(TestCase):
    """Test cases for the delete account functionality"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.factory = RequestFactory()
        self.test_password = "TestPass123!"
        
        # Create test user
        self.user = User.objects.create(
            username="testuser",
            password=make_password(self.test_password),
            display_name="Test User",
            email="test@example.com",
            is_verified=True
        )
        
        # Set up session for authenticated user
        session = self.client.session
        session['user_id'] = str(self.user.user_id)
        session['username'] = self.user.username
        session.save()
        
        self.delete_account_url = reverse('user_settings:delete_account')

    def test_delete_account_success(self):
        """Test successful account deletion"""
        payload = {
            "current_password": self.test_password,
        }
        
        response = self.client.post(
            self.delete_account_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['message'], "Account deleted successfully")
        
        # Verify user was actually deleted from database
        self.assertFalse(User.objects.filter(user_id=self.user.user_id).exists())

    def test_delete_account_wrong_password(self):
        """Test account deletion with incorrect password"""
        payload = {
            "current_password": "WrongPassword123!",
        }
        
        response = self.client.post(
            self.delete_account_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Validasi gagal")
        self.assertIn('current_password', response_data['validation_errors'])
        
        # Verify user was NOT deleted from database
        self.assertTrue(User.objects.filter(user_id=self.user.user_id).exists())

    def test_delete_account_unauthenticated(self):
        """Test account deletion without authentication"""
        # Clear session
        self.client.session.flush()
        
        payload = {
            "current_password": self.test_password,
        }
        
        response = self.client.post(
            self.delete_account_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Autentikasi diperlukan")

    def test_delete_account_missing_password(self):
        """Test account deletion without providing password"""
        payload = {}
        
        response = self.client.post(
            self.delete_account_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Field yang diperlukan tidak ada")

    def test_delete_account_service_failure(self):
        """Service failure should return 400 with message"""
        payload = {
            "current_password": self.test_password,
        }

        failure_result = AccountDeletionResult(success=False, message="Service failure")

        with patch('user_settings.views._password_service.delete_account', return_value=failure_result) as mock_delete:
            response = self.client.post(
                self.delete_account_url,
                data=json.dumps(payload),
                content_type='application/json'
            )

        mock_delete.assert_called_once()
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Gagal menghapus akun")
        self.assertEqual(response_data['message'], failure_result.message)

    def test_delete_account_invalid_json_none_data(self):
        """Test delete account with None data from parse_json_body"""
        # Mock parse_json_body to return None, None (valid JSON but results in None)
        with patch('user_settings.views.parse_json_body', return_value=(None, None)):
            response = self.client.post(
                self.delete_account_url,
                data='null',  # Valid JSON but represents null/None
                content_type='application/json'
            )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Payload tidak valid")
        self.assertEqual(response_data['message'], "Request body harus berisi JSON yang valid")

    def test_delete_account_non_dict_data(self):
        """Test delete account with non-dict data (like array or string)"""
        # Mock parse_json_body to return a list instead of dict
        with patch('user_settings.views.parse_json_body', return_value=(["not", "a", "dict"], None)):
            response = self.client.post(
                self.delete_account_url,
                data='["not", "a", "dict"]',  # Valid JSON but not a dict
                content_type='application/json'
            )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Payload tidak valid")
        self.assertEqual(response_data['message'], "Request body harus berupa objek JSON")

    def test_delete_account_parse_json_error(self):
        """Test delete account when parse_json_body returns error response"""
        error_response = JsonResponse({"error": "Invalid JSON"}, status=400)
        
        # Mock parse_json_body to return error response
        with patch('user_settings.views.parse_json_body', return_value=(None, error_response)):
            response = self.client.post(
                self.delete_account_url,
                data='invalid json',  # Invalid JSON
                content_type='application/json'
            )
        
        self.assertEqual(response.status_code, 400)

    def test_delete_account_unexpected_exception(self):
        """Test delete account with unexpected exception during processing"""
        payload = {
            "current_password": self.test_password,
        }

        # Mock the service to raise an unexpected exception
        with patch('user_settings.views._password_service.delete_account', side_effect=Exception("Database error")):
            response = self.client.post(
                self.delete_account_url,
                data=json.dumps(payload),
                content_type='application/json'
            )

        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Kesalahan server internal")
        self.assertEqual(response_data['message'], "Terjadi kesalahan yang tidak terduga. Silakan coba lagi nanti.")

    def test_delete_account_wrong_password_service_layer(self):
        """Test service layer returns failure for wrong password"""
        from user_settings.services.passwords import PasswordChangeService
        from user_settings.services.passwords import DjangoUserRepository, DjangoPasswordEncoder
        
        # Create service with real implementations (not mocked)
        user_repo = DjangoUserRepository()
        password_encoder = DjangoPasswordEncoder()
        service = PasswordChangeService(
            user_repository=user_repo,
            password_encoder=password_encoder
        )
        
        # Try to delete account with wrong password
        wrong_password = "WrongPassword123!"
        result = service.delete_account(user=self.user, password=wrong_password)
        
        # Should return failure
        self.assertFalse(result.success)
        self.assertEqual(result.message, "Current password is incorrect")


class DeleteAccountSerializerTestCase(TestCase):
    """Test cases for the DeleteAccountSerializer"""

    def setUp(self):
        """Set up test data"""
        self.test_password = "TestPass123!"
        self.user = User.objects.create(
            username="testuser",
            password=make_password(self.test_password),
            display_name="Test User",
            email="test@example.com"
        )

    def test_serializer_valid_data(self):
        """Test serializer with valid data"""
        data = {
            'current_password': self.test_password,
        }
        
        serializer = DeleteAccountSerializer(user=self.user, data=data)
        self.assertTrue(serializer.is_valid())

    def test_serializer_wrong_current_password(self):
        """Test serializer with wrong current password"""
        data = {
            'current_password': 'WrongPassword123!',
        }
        
        serializer = DeleteAccountSerializer(user=self.user, data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('current_password', serializer.errors)

    def test_serializer_missing_password(self):
        """Test serializer with missing password"""
        data = {
            'current_password': '',
        }
        
        serializer = DeleteAccountSerializer(user=self.user, data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('current_password', serializer.errors)

    def test_serializer_without_user_instance(self):
        """Test serializer validation when user instance is None"""
        
        # Test with user=None - should skip password verification
        serializer = DeleteAccountSerializer(user=None)
        serializer.cleaned_data = {'current_password': 'somepassword'}
        
        # Call clean_current_password directly to test the branch where self.user is None
        result = serializer.clean_current_password()
        self.assertEqual(result, 'somepassword')
        
        # Also test the full validation flow
        data = {'current_password': 'somepassword'}
        serializer2 = DeleteAccountSerializer(user=None, data=data)
        self.assertTrue(serializer2.is_valid())

    def test_serializer_with_falsy_user(self):
        """Test serializer validation when user instance is falsy but not None"""
        
        # Test with user=False (another falsy value)
        serializer = DeleteAccountSerializer(user=False)
        serializer.cleaned_data = {'current_password': 'somepassword'}
        
        # Call clean_current_password directly to test the branch where self.user is falsy
        result = serializer.clean_current_password()
        self.assertEqual(result, 'somepassword')

    def test_delete_account_serializer_correct_password(self):
        """Test DeleteAccountSerializer with correct password"""
        
        # Test with correct password - should pass validation
        serializer = DeleteAccountSerializer(user=self.user)
        serializer.cleaned_data = {'current_password': self.test_password}
        
        # Call clean_current_password directly - should succeed
        result = serializer.clean_current_password()
        self.assertEqual(result, self.test_password)

    def test_serializer_empty_current_password(self):
        """Test serializer clean_current_password with empty password string"""
        serializer = DeleteAccountSerializer(user=self.user)
        serializer.cleaned_data = {'current_password': ''}
        
        # Should raise ValidationError for empty password
        with self.assertRaises(ValidationError) as ctx:
            serializer.clean_current_password()
        
        self.assertIn('Password lama diperlukan', str(ctx.exception))

    def test_serializer_none_current_password(self):
        """Test serializer clean_current_password with None password"""
        serializer = DeleteAccountSerializer(user=self.user)
        serializer.cleaned_data = {'current_password': None}
        
        # Should raise ValidationError for None password
        with self.assertRaises(ValidationError) as ctx:
            serializer.clean_current_password()
        
        self.assertIn('Password lama diperlukan', str(ctx.exception))

    def test_serializer_password_check_path_with_user(self):
        """Test the password check path when user exists"""
        # This specifically tests the branch where self.user exists and password is correct
        serializer = DeleteAccountSerializer(user=self.user)
        serializer.cleaned_data = {'current_password': self.test_password}
        
        # This should exercise the check_password line
        result = serializer.clean_current_password()
        self.assertEqual(result, self.test_password)

    def test_serializer_password_check_path_with_wrong_password(self):
        """Test the password check path when user exists but password is wrong"""
        # This specifically tests the branch where self.user exists and password is incorrect
        serializer = DeleteAccountSerializer(user=self.user)
        serializer.cleaned_data = {'current_password': 'wrongpassword123'}
        
        # This should exercise the check_password line and the if not passwords_match branch
        with self.assertRaises(ValidationError) as ctx:
            serializer.clean_current_password()
        
        self.assertIn('Password lama salah', str(ctx.exception))

    def test_serializer_validate_data_success(self):
        """Test DeleteAccountSerializer validate_data method for success case"""
        serializer = DeleteAccountSerializer(user=self.user)
        data = {'current_password': self.test_password}
        
        # Test the validate_data method directly if it exists
        if hasattr(serializer, 'validate_data'):
            is_valid, errors = serializer.validate_data(data)
            self.assertTrue(is_valid)
            self.assertEqual(errors, {})

    def test_serializer_validation_edge_cases(self):
        """Test serializer with various edge cases to ensure full coverage"""
        # Test with whitespace-only password
        serializer = DeleteAccountSerializer(user=self.user)
        serializer.cleaned_data = {'current_password': '   '}
        
        # Whitespace should be treated as empty
        with self.assertRaises(ValidationError):
            serializer.clean_current_password()