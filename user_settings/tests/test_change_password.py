import json
import uuid
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth.hashers import make_password, check_password
from authentication.models import User
from ..serializers import ChangePasswordSerializer
from ..services.passwords import PasswordChangeResult
from ..views import get_authenticated_user


class ChangePasswordTestCase(TestCase):
    """Test cases for the change password functionality"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.factory = RequestFactory()
        self.test_password = "TestPass123!"
        self.new_password = "NewPass456"
        
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
        
        self.change_password_url = reverse('user_settings:change_password')

    def test_change_password_success(self):
        """Test successful password change"""
        payload = {
            "current_password": self.test_password,
            "new_password": self.new_password,
            "confirm_password": self.new_password
        }
        
        response = self.client.post(
            self.change_password_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['message'], "Password changed successfully")
        
        # Verify password was actually changed in database
        self.user.refresh_from_db()
        self.assertTrue(check_password(self.new_password, self.user.password))
        self.assertFalse(check_password(self.test_password, self.user.password))

    def test_change_password_unauthenticated(self):
        """Test password change without authentication"""
        # Clear session
        self.client.session.flush()
        
        payload = {
            "current_password": self.test_password,
            "new_password": self.new_password,
            "confirm_password": self.new_password
        }
        
        response = self.client.post(
            self.change_password_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Authentication required")

    def test_change_password_wrong_current_password(self):
        """Test password change with incorrect current password"""
        payload = {
            "current_password": "WrongPassword123!",
            "new_password": self.new_password,
            "confirm_password": self.new_password
        }
        
        response = self.client.post(
            self.change_password_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Validation failed")
        self.assertIn('current_password', response_data['validation_errors'])

    def test_change_password_weak_password(self):
        """Test password change with weak new password"""
        weak_passwords = [
            "1234567",  # Too short
            "12345678",  # No letters
            "password",  # No uppercase, no digits
            "Password",  # No digits
            "password123",  # No uppercase
            "PASSWORD123",  # No lowercase
        ]
        
        for weak_password in weak_passwords:
            with self.subTest(password=weak_password):
                payload = {
                    "current_password": self.test_password,
                    "new_password": weak_password,
                    "confirm_password": weak_password
                }
                
                response = self.client.post(
                    self.change_password_url,
                    data=json.dumps(payload),
                    content_type='application/json'
                )
                
                self.assertEqual(response.status_code, 400)
                response_data = json.loads(response.content)
                self.assertEqual(response_data['error'], "Validation failed")

    def test_change_password_mismatched_confirmation(self):
        """Test password change with mismatched password confirmation"""
        payload = {
            "current_password": self.test_password,
            "new_password": self.new_password,
            "confirm_password": "DifferentPass456"
        }
        
        response = self.client.post(
            self.change_password_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Validation failed")

    def test_change_password_same_as_current(self):
        """Test password change with same password as current"""
        payload = {
            "current_password": self.test_password,
            "new_password": self.test_password,
            "confirm_password": self.test_password
        }
        
        response = self.client.post(
            self.change_password_url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Validation failed")
        self.assertIn('new_password', response_data['validation_errors'])

    def test_change_password_missing_fields(self):
        """Test password change with missing required fields"""
        test_cases = [
            {},  # All fields missing
            {"current_password": self.test_password},  # Missing new_password and confirm_password
            {"new_password": self.new_password},  # Missing current_password and confirm_password
            {"current_password": self.test_password, "new_password": self.new_password},  # Missing confirm_password
        ]
        
        for payload in test_cases:
            with self.subTest(payload=payload):
                response = self.client.post(
                    self.change_password_url,
                    data=json.dumps(payload),
                    content_type='application/json'
                )
                
                self.assertEqual(response.status_code, 400)
                response_data = json.loads(response.content)
                self.assertEqual(response_data['error'], "Missing required fields")
                self.assertIn('missing_fields', response_data)

    def test_change_password_invalid_json(self):
        """Test password change with invalid JSON payload"""
        response = self.client.post(
            self.change_password_url,
            data="invalid json",
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "invalid payload")

    def test_change_password_null_payload(self):
        """JSON null payload should return invalid payload error"""
        response = self.client.post(
            self.change_password_url,
            data="null",
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Invalid payload")
        self.assertIn("must contain valid JSON", response_data['message'])

    def test_change_password_non_object_payload(self):
        """Non-dict JSON payload should be rejected"""
        response = self.client.post(
            self.change_password_url,
            data="[1, 2, 3]",
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Invalid payload")
        self.assertIn("must be a JSON object", response_data['message'])

    def test_change_password_service_failure(self):
        """Service failure should return 400 with message"""
        payload = {
            "current_password": self.test_password,
            "new_password": self.new_password,
            "confirm_password": self.new_password,
        }

        failure_result = PasswordChangeResult(success=False, message="Service failure")

        with patch('user_settings.views._password_service.change_password', return_value=failure_result) as mock_change:
            response = self.client.post(
                self.change_password_url,
                data=json.dumps(payload),
                content_type='application/json'
            )

        mock_change.assert_called_once()
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Password change failed")
        self.assertEqual(response_data['message'], failure_result.message)

    def test_change_password_get_method_not_allowed(self):
        """Test that GET method is not allowed for change password endpoint"""
        response = self.client.get(self.change_password_url)
        self.assertEqual(response.status_code, 405)  # Method not allowed

    def test_user_profile_endpoint(self):
        """Test the user profile endpoint"""
        profile_url = reverse('user_settings:user_profile')
        response = self.client.get(profile_url)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        
        self.assertEqual(response_data['username'], self.user.username)
        self.assertEqual(response_data['display_name'], self.user.display_name)
        self.assertEqual(response_data['email'], self.user.email)
        self.assertEqual(response_data['user_id'], str(self.user.user_id))

    def test_user_profile_unauthenticated(self):
        """Test user profile endpoint without authentication"""
        # Clear session
        self.client.session.flush()
        
        profile_url = reverse('user_settings:user_profile')
        response = self.client.get(profile_url)
        
        self.assertEqual(response.status_code, 401)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Authentication required")

    def test_user_profile_method_not_allowed(self):
        """User profile should reject non-GET methods"""
        profile_url = reverse('user_settings:user_profile')
        response = self.client.post(profile_url, data={})

        self.assertEqual(response.status_code, 405)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Method not allowed")

    def test_get_authenticated_user_returns_user(self):
        """Helper should return user when session matches"""
        request = self.factory.get('/test')
        request.session = self.client.session

        user = get_authenticated_user(request)

        self.assertIsNotNone(user)
        self.assertEqual(user.user_id, self.user.user_id)

    def test_get_authenticated_user_missing_session(self):
        """Helper returns None when session lacks credentials"""
        request = self.factory.get('/test')
        request.session = {}

        user = get_authenticated_user(request)

        self.assertIsNone(user)

    def test_get_authenticated_user_missing_user_record(self):
        """Helper returns None when database record is absent"""
        request = self.factory.get('/test')
        request.session = {
            'user_id': str(self.user.user_id),
            'username': self.user.username
        }

        self.user.delete()

        user = get_authenticated_user(request)

        self.assertIsNone(user)

    def test_change_password_unexpected_exception_returns_server_error(self):
        """Unexpected exception should produce 500 response"""
        payload = {
            "current_password": self.test_password,
            "new_password": self.new_password,
            "confirm_password": self.new_password
        }

        with patch('user_settings.views.ChangePasswordSerializer') as mock_serializer:
            serializer_instance = mock_serializer.return_value
            serializer_instance.is_valid.side_effect = Exception("boom")

            response = self.client.post(
                self.change_password_url,
                data=json.dumps(payload),
                content_type='application/json'
            )

        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], "Internal server error")


class ChangePasswordSerializerTestCase(TestCase):
    """Test cases for the ChangePasswordSerializer"""

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
            'new_password': 'NewPass456',
            'confirm_password': 'NewPass456'
        }
        
        serializer = ChangePasswordSerializer(user=self.user, data=data)
        self.assertTrue(serializer.is_valid())

    def test_serializer_wrong_current_password(self):
        """Test serializer with wrong current password"""
        data = {
            'current_password': 'WrongPassword123!',
            'new_password': 'NewPass456',
            'confirm_password': 'NewPass456'
        }
        
        serializer = ChangePasswordSerializer(user=self.user, data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('current_password', serializer.errors)

    def test_serializer_password_mismatch(self):
        """Test serializer with password confirmation mismatch"""
        data = {
            'current_password': self.test_password,
            'new_password': 'NewPass456',
            'confirm_password': 'DifferentPass456'
        }
        
        serializer = ChangePasswordSerializer(user=self.user, data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('__all__', serializer.errors)

    def test_serializer_weak_password(self):
        """Test serializer with weak password"""
        data = {
            'current_password': self.test_password,
            'new_password': '123456',  # Too weak
            'confirm_password': '123456'
        }
        
        serializer = ChangePasswordSerializer(user=self.user, data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('new_password', serializer.errors)

    def test_clean_new_password_requires_value(self):
        """clean_new_password should reject missing new password"""
        serializer = ChangePasswordSerializer(user=self.user)
        serializer.cleaned_data = {
            'current_password': self.test_password,
            'new_password': ''
        }

        with self.assertRaises(ValidationError) as ctx:
            serializer.clean_new_password()

        self.assertIn("New password is required", ctx.exception.messages)

    def test_clean_new_password_returns_valid_password(self):
        """clean_new_password returns the validated password"""
        serializer = ChangePasswordSerializer(user=self.user)
        valid_password = "ValidPass1"
        serializer.cleaned_data = {
            'current_password': self.test_password,
            'new_password': valid_password
        }

        result = serializer.clean_new_password()
        self.assertEqual(result, valid_password)

    def test_clean_new_password_raises_shared_validator_error(self):
        """clean_new_password surfaces errors from shared validator"""
        serializer = ChangePasswordSerializer(user=self.user)
        serializer.cleaned_data = {
            'current_password': self.test_password,
            'new_password': 'lowercase1'
        }

        with self.assertRaises(ValidationError) as ctx:
            serializer.clean_new_password()

        self.assertIn('uppercase', ' '.join(ctx.exception.messages).lower())

    def test_clean_current_password_incorrect(self):
        """clean_current_password raises when hash check fails"""
        serializer = ChangePasswordSerializer(user=self.user)
        serializer.cleaned_data = {
            'current_password': 'WrongPassword123!'
        }

        with self.assertRaises(ValidationError) as ctx:
            serializer.clean_current_password()

        self.assertIn('incorrect', ' '.join(ctx.exception.messages).lower())

    def test_clean_current_password_returns_value(self):
        """clean_current_password returns original value when valid"""
        serializer = ChangePasswordSerializer(user=self.user)
        serializer.cleaned_data = {
            'current_password': self.test_password
        }

        result = serializer.clean_current_password()
        self.assertEqual(result, self.test_password)

    def test_clean_current_password_required(self):
        """clean_current_password enforces required current password"""
        serializer = ChangePasswordSerializer(user=self.user)
        serializer.cleaned_data = {
            'current_password': ''
        }

        with self.assertRaises(ValidationError) as ctx:
            serializer.clean_current_password()

        self.assertIn('required', ' '.join(ctx.exception.messages).lower())

    def test_validate_data_success(self):
        """validate_data returns True with clean payload"""
        serializer = ChangePasswordSerializer(user=self.user)
        payload = {
            'current_password': self.test_password,
            'new_password': 'ValidPass1',
            'confirm_password': 'ValidPass1'
        }

        is_valid, errors = serializer.validate_data(payload)
        self.assertTrue(is_valid)
        self.assertEqual(errors, {})

    def test_validate_data_handles_validation_error(self):
        """validate_data surfaces ValidationError messages"""
        serializer = ChangePasswordSerializer(user=self.user)
        payload = {
            'current_password': self.test_password,
            'new_password': 'ValidPass1',
            'confirm_password': 'ValidPass1'
        }

        with patch.object(ChangePasswordSerializer, 'full_clean', side_effect=ValidationError(["Test error"])):
            is_valid, errors = serializer.validate_data(payload)

        self.assertFalse(is_valid)
        self.assertEqual(errors, {'non_field_errors': ["Test error"]})

    def test_validate_data_handles_generic_exception(self):
        """validate_data returns collected field errors when unexpected exception occurs"""
        serializer = ChangePasswordSerializer(user=self.user)
        payload = {
            'current_password': self.test_password,
            'new_password': 'ValidPass1',
            'confirm_password': 'ValidPass1'
        }

        # Pre-populate errors to ensure they are returned in fallback branch
        serializer._errors = {'new_password': ['error']}

        with patch.object(ChangePasswordSerializer, 'full_clean', side_effect=Exception('boom')):
            is_valid, errors = serializer.validate_data(payload)

        self.assertFalse(is_valid)
        self.assertEqual(errors, {'new_password': ['error']})
