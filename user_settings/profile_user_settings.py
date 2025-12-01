"""
User Settings Performance Profiler

This module profiles the user_settings application components including:
- Password change service
- Account deletion service
- Password serializers
- View endpoints
- Password encoding
- User repository operations

Usage:
    python -m user_settings.profile_user_settings
    
    Or with Django:
    python manage.py shell < user_settings/profile_user_settings.py
"""

import sys
import os
import django
from pathlib import Path
from typing import Dict, Any, List

# Setup Django environment
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kalbe_be.settings')
django.setup()

from utils.base_profiler import BaseProfiler
from user_settings.services.passwords import (
    PasswordChangeService,
    DjangoPasswordEncoder,
    DjangoUserRepository,
    PasswordChangeResult,
    AccountDeletionResult,
)
from user_settings.serializers import (
    ChangePasswordSerializer,
    DeleteAccountSerializer,
)
from authentication.models import User
from django.contrib.auth.hashers import make_password


class UserSettingsProfiler(BaseProfiler):
    """Profiler for user_settings module components"""
    
    def __init__(self):
        super().__init__('user_settings')
    
    def _setup_vendor_specific(self):
        """Setup user_settings-specific components and test data"""
        self.password_encoder = DjangoPasswordEncoder()
        self.user_repository = DjangoUserRepository()
        self.password_service = PasswordChangeService(
            user_repository=self.user_repository,
            password_encoder=self.password_encoder,
        )
        
        # Test data
        self.test_passwords = self._get_test_passwords()
        self.test_user_data = self._get_test_user_data()
        self.test_serializer_data = self._get_test_serializer_data()
    
    def _get_test_passwords(self) -> List[str]:
        """Return test passwords with various strengths"""
        return [
            "SecurePass123!",
            "AnotherP@ssw0rd",
            "MyStr0ng!Pass",
            "Complex$Pass99",
            "TestP@ssword2024",
            "Secure#123Pass",
            "Valid$Pass789",
            "Strong&Pass456",
            "Test!Password11",
            "MyP@ssw0rd999",
        ]
    
    def _get_test_user_data(self) -> Dict[str, Any]:
        """Return test user data for creating mock users"""
        return {
            'username': 'test_profiling_user',
            'email': 'test_profiling@example.com',
            'display_name': 'Test Profiling User',
            'password': make_password('OldPassword123!'),
            'roles': ['user'],
        }
    
    def _get_test_serializer_data(self) -> List[Dict[str, Any]]:
        """Return test data for serializer validation"""
        return [
            {
                'current_password': 'OldPassword123!',
                'new_password': 'NewPassword123!',
                'confirm_password': 'NewPassword123!',
            },
            {
                'current_password': 'OldPassword123!',
                'new_password': 'AnotherP@ss456',
                'confirm_password': 'AnotherP@ss456',
            },
            {
                'current_password': 'OldPassword123!',
                'new_password': 'Str0ng#Pass789',
                'confirm_password': 'Str0ng#Pass789',
            },
            {
                'current_password': 'OldPassword123!',
                'new_password': 'Valid$Pass2024',
                'confirm_password': 'Valid$Pass2024',
            },
            {
                'current_password': 'OldPassword123!',
                'new_password': 'Complex&Pass99',
                'confirm_password': 'Complex&Pass99',
            },
        ]
    
    def _create_test_user(self) -> User:
        """Create a test user for profiling (or get existing)"""
        try:
            user = User.objects.get(username=self.test_user_data['username'])
            # Update password to known value
            user.password = self.test_user_data['password']
            user.save(update_fields=['password'])
            return user
        except User.DoesNotExist:
            # Create new test user - exclude user_id to let it auto-generate
            user = User.objects.create(
                username=self.test_user_data['username'],
                email=self.test_user_data['email'],
                display_name=self.test_user_data['display_name'],
                password=self.test_user_data['password'],
                roles=self.test_user_data['roles'],
            )
            return user
    
    def _cleanup_test_user(self):
        """Clean up test user after profiling"""
        try:
            User.objects.filter(username=self.test_user_data['username']).delete()
        except Exception as e:
            print(f"Warning: Could not cleanup test user: {e}")
    
    def profile_password_encoder(self) -> Dict[str, Any]:
        """Profile the password encoding performance"""
        iterations = int(self.ENV.get('PROFILING_ITERATIONS_ENCODER', '20'))
        use_cprofile = self.ENV.get('PROFILING_USE_CPROFILE', 'true').lower() == 'true'
        
        print(f"Profiling password encoder ({iterations} iterations)...")
        
        def encoder_callback(i):
            password = self.test_passwords[i % len(self.test_passwords)]
            encoded = self.password_encoder.encode(password)
            return encoded
        
        result = self._profile_component(
            'password_encoder',
            iterations,
            encoder_callback,
            use_cprofile=use_cprofile
        )
        return result
    
    def profile_user_repository_get(self) -> Dict[str, Any]:
        """Profile user repository get operation"""
        iterations = int(self.ENV.get('PROFILING_ITERATIONS_REPO', '50'))
        
        print(f"Profiling user repository get ({iterations} iterations)...")
        
        # Create test user and get its actual UUID
        test_user = self._create_test_user()
        test_user_id = str(test_user.user_id)
        test_username = test_user.username
        
        def repo_callback(i):
            user = self.user_repository.get_by_credentials(
                user_id=test_user_id,
                username=test_username
            )
            return user
        
        result = self._profile_component('user_repository_get', iterations, repo_callback)
        return result
    
    def profile_user_repository_save(self) -> Dict[str, Any]:
        """Profile user repository save password operation"""
        iterations = int(self.ENV.get('PROFILING_ITERATIONS_REPO', '30'))
        
        print(f"Profiling user repository save password ({iterations} iterations)...")
        
        # Create test user
        test_user = self._create_test_user()
        
        def repo_callback(i):
            password = self.test_passwords[i % len(self.test_passwords)]
            encoded = make_password(password)
            self.user_repository.save_password(test_user, encoded)
        
        result = self._profile_component('user_repository_save', iterations, repo_callback)
        return result
    
    def profile_password_change_service(self) -> Dict[str, Any]:
        """Profile the complete password change service"""
        iterations = int(self.ENV.get('PROFILING_ITERATIONS_SERVICE', '20'))
        use_cprofile = self.ENV.get('PROFILING_USE_CPROFILE', 'true').lower() == 'true'
        
        print(f"Profiling password change service ({iterations} iterations)...")
        
        # Create test user
        test_user = self._create_test_user()
        
        def service_callback(i):
            password = self.test_passwords[i % len(self.test_passwords)]
            result = self.password_service.change_password(
                user=test_user,
                new_password=password
            )
            return result
        
        result = self._profile_component(
            'password_change_service',
            iterations,
            service_callback,
            use_cprofile=use_cprofile
        )
        return result
    
    def profile_account_deletion_service(self) -> Dict[str, Any]:
        """Profile the account deletion service"""
        iterations = int(self.ENV.get('PROFILING_ITERATIONS_DELETION', '10'))
        
        print(f"Profiling account deletion service ({iterations} iterations)...")
        
        def service_callback(i):
            # Create a new user for each deletion test
            test_user = User.objects.create(
                username=f'test_delete_user_{i}',
                email=f'test_delete_{i}@example.com',
                display_name=f'Test Delete User {i}',
                password=make_password('OldPassword123!'),
                roles=['user'],
            )
            
            # Test deletion with correct password
            result = self.password_service.delete_account(
                user=test_user,
                password='OldPassword123!'
            )
            return result
        
        result = self._profile_component(
            'account_deletion_service',
            iterations,
            service_callback,
            warmup=False  # No warmup for deletion tests
        )
        return result
    
    def profile_change_password_serializer(self) -> Dict[str, Any]:
        """Profile password change serializer validation"""
        iterations = int(self.ENV.get('PROFILING_ITERATIONS_SERIALIZER', '50'))
        
        print(f"Profiling change password serializer ({iterations} iterations)...")
        
        # Create test user
        test_user = self._create_test_user()
        
        def serializer_callback(i):
            data = self.test_serializer_data[i % len(self.test_serializer_data)]
            serializer = ChangePasswordSerializer(user=test_user, data=data)
            is_valid = serializer.is_valid()
            return is_valid
        
        result = self._profile_component('change_password_serializer', iterations, serializer_callback)
        return result
    
    def profile_delete_account_serializer(self) -> Dict[str, Any]:
        """Profile delete account serializer validation"""
        iterations = int(self.ENV.get('PROFILING_ITERATIONS_SERIALIZER', '50'))
        
        print(f"Profiling delete account serializer ({iterations} iterations)...")
        
        # Create test user
        test_user = self._create_test_user()
        
        def serializer_callback(i):
            data = {'current_password': 'OldPassword123!'}
            serializer = DeleteAccountSerializer(user=test_user, data=data)
            is_valid = serializer.is_valid()
            return is_valid
        
        result = self._profile_component('delete_account_serializer', iterations, serializer_callback)
        return result
    
    def profile_serializer_validation_errors(self) -> Dict[str, Any]:
        """Profile serializer with invalid data to test error handling"""
        iterations = int(self.ENV.get('PROFILING_ITERATIONS_VALIDATION', '30'))
        
        print(f"Profiling serializer validation errors ({iterations} iterations)...")
        
        # Create test user
        test_user = self._create_test_user()
        
        # Invalid test data
        invalid_data_sets = [
            {'current_password': 'WrongPass!', 'new_password': 'NewPass123!', 'confirm_password': 'NewPass123!'},
            {'current_password': 'OldPassword123!', 'new_password': 'short', 'confirm_password': 'short'},
            {'current_password': 'OldPassword123!', 'new_password': 'NoNumber!', 'confirm_password': 'NoNumber!'},
            {'current_password': 'OldPassword123!', 'new_password': 'NewPass123!', 'confirm_password': 'Mismatch!'},
            {'current_password': '', 'new_password': 'NewPass123!', 'confirm_password': 'NewPass123!'},
        ]
        
        def validation_callback(i):
            data = invalid_data_sets[i % len(invalid_data_sets)]
            serializer = ChangePasswordSerializer(user=test_user, data=data)
            is_valid = serializer.is_valid()
            errors = serializer.errors if not is_valid else {}
            return errors
        
        result = self._profile_component('serializer_validation_errors', iterations, validation_callback)
        return result
    
    def profile_password_strength_validation(self) -> Dict[str, Any]:
        """Profile password strength validation"""
        iterations = int(self.ENV.get('PROFILING_ITERATIONS_VALIDATION', '50'))
        
        print(f"Profiling password strength validation ({iterations} iterations)...")
        
        from authentication.validators import validate_password
        from django.core.exceptions import ValidationError
        
        passwords_to_test = [
            "SecurePass123!",  # Valid
            "weak",  # Too short
            "NoNumbersHere!",  # No numbers
            "nonumbersorspecial",  # No numbers or special chars
            "12345678",  # Only numbers
            "ValidP@ssw0rd",  # Valid
            "short1!",  # Too short
            "LongEnoughButNoNumbers!",  # No numbers
            "1234567890!@#$",  # No letters
            "Another$ecureP@ss99",  # Valid
        ]
        
        def validation_callback(i):
            password = passwords_to_test[i % len(passwords_to_test)]
            try:
                validate_password(password)
                return True
            except ValidationError:
                return False
        
        result = self._profile_component('password_strength_validation', iterations, validation_callback)
        return result
    
    def run_basic_profiling(self):
        """Run basic profiling tests for user_settings"""
        raise NotImplementedError("Use run_complete_profiling() instead")
    
    def run_complete_profiling(self):
        """Run complete profiling of all user_settings components"""
        if self.ENV.get('PROFILING_ENABLED', 'true').lower() != 'true':
            print("Profiling is disabled in environment configuration")
            return
        
        try:
            print("\n" + "=" * 60)
            print("USER SETTINGS PROFILING")
            print("=" * 60)
            
            # 1. Password encoder
            self.profile_password_encoder()
            print(f"✓ Password Encoder: {self.results['password_encoder']['avg_time']:.4f}s")
            
            # 2. User repository operations
            self.profile_user_repository_get()
            print(f"✓ User Repository Get: {self.results['user_repository_get']['avg_time']:.4f}s")
            
            self.profile_user_repository_save()
            print(f"✓ User Repository Save: {self.results['user_repository_save']['avg_time']:.4f}s")
            
            # 3. Password change service
            self.profile_password_change_service()
            print(f"✓ Password Change Service: {self.results['password_change_service']['avg_time']:.4f}s")
            
            # 4. Serializers
            self.profile_change_password_serializer()
            print(f"✓ Change Password Serializer: {self.results['change_password_serializer']['avg_time']:.4f}s")
            
            self.profile_delete_account_serializer()
            print(f"✓ Delete Account Serializer: {self.results['delete_account_serializer']['avg_time']:.4f}s")
            
            # 5. Validation
            self.profile_password_strength_validation()
            print(f"✓ Password Strength Validation: {self.results['password_strength_validation']['avg_time']:.4f}s")
            
            self.profile_serializer_validation_errors()
            print(f"✓ Serializer Validation Errors: {self.results['serializer_validation_errors']['avg_time']:.4f}s")
            
            # 6. Account deletion (runs last as it deletes users)
            self.profile_account_deletion_service()
            print(f"✓ Account Deletion Service: {self.results['account_deletion_service']['avg_time']:.4f}s")
            
            # Generate report
            print("\n" + "=" * 60)
            report_file = self.generate_performance_report()
            print(f"Report saved to: {report_file}")
            
            # Print cProfile summaries if enabled
            if self.ENV.get('PROFILING_USE_CPROFILE', 'true').lower() == 'true':
                print("\n" + "=" * 60)
                print("cProfile DETAILED ANALYSIS")
                print("=" * 60)
                
                # Show detailed profile for key components
                if 'password_encoder' in self.cprofile_stats:
                    self.print_cprofile_summary('password_encoder', top_n=10)
                
                if 'password_change_service' in self.cprofile_stats:
                    self.print_cprofile_summary('password_change_service', top_n=10)
            
            # Print summary
            self.print_performance_summary()
            
        except Exception as e:
            print(f"Profiling failed: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            # Cleanup test user
            self._cleanup_test_user()


def main():
    """Main entry point for running user_settings profiler"""
    print("=" * 60)
    print("USER SETTINGS PERFORMANCE PROFILER")
    print("=" * 60)
    
    profiler = UserSettingsProfiler()
    profiler.run_complete_profiling()
    
    print("\n" + "=" * 60)
    print("PROFILING COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()
