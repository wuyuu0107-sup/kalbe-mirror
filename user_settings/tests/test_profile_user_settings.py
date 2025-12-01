"""
Tests for user_settings profiling script.

This test module ensures that the profiling functionality works correctly
and covers all profiling methods.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
from django.test import TestCase
from pathlib import Path
import sys
import os

from authentication.models import User
from user_settings.services.passwords import (
    PasswordChangeService,
    DjangoPasswordEncoder,
    DjangoUserRepository,
)
from django.contrib.auth.hashers import make_password


class UserSettingsProfilerTestCase(TestCase):
    """Test cases for UserSettingsProfiler"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Import here to ensure Django is setup
        from user_settings.profile_user_settings import UserSettingsProfiler
        self.profiler = UserSettingsProfiler()
        
        # Create test user with secure password generation
        # Using make_password ensures proper hashing for test environment
        test_password = 'TestPass' + str(hash('test_user_2024'))[:8] + '!'
        self.test_user = User.objects.create(
            username='test_profiling_user',
            email='test_profiling@example.com',
            display_name='Test Profiling User',
            password=make_password(test_password),
            roles=['user'],
        )
    
    def tearDown(self):
        """Clean up test data"""
        User.objects.filter(username__startswith='test_').delete()
    
    def test_profiler_initialization(self):
        """Test that profiler initializes correctly"""
        self.assertEqual(self.profiler.module_name, 'user_settings')
        self.assertIsInstance(self.profiler.password_encoder, DjangoPasswordEncoder)
        self.assertIsInstance(self.profiler.user_repository, DjangoUserRepository)
        self.assertIsInstance(self.profiler.password_service, PasswordChangeService)
    
    def test_get_test_passwords(self):
        """Test that test passwords are properly generated"""
        passwords = self.profiler._get_test_passwords()
        self.assertIsInstance(passwords, list)
        self.assertGreater(len(passwords), 0)
        self.assertTrue(all(isinstance(p, str) for p in passwords))
        self.assertTrue(all(len(p) > 0 for p in passwords))
    
    def test_get_test_user_data(self):
        """Test that test user data is properly structured"""
        user_data = self.profiler._get_test_user_data()
        self.assertIsInstance(user_data, dict)
        self.assertIn('username', user_data)
        self.assertIn('email', user_data)
        self.assertIn('display_name', user_data)
        self.assertIn('password', user_data)
        self.assertIn('roles', user_data)
    
    def test_get_test_serializer_data(self):
        """Test that serializer test data is properly structured"""
        serializer_data = self.profiler._get_test_serializer_data()
        self.assertIsInstance(serializer_data, list)
        self.assertGreater(len(serializer_data), 0)
        
        for data in serializer_data:
            self.assertIn('current_password', data)
            self.assertIn('new_password', data)
            self.assertIn('confirm_password', data)
    
    def test_create_test_user(self):
        """Test creating test user for profiling"""
        # Clean up first
        User.objects.filter(username='test_profiling_user').delete()
        
        user = self.profiler._create_test_user()
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'test_profiling_user')
        self.assertEqual(user.email, 'test_profiling@example.com')
        
        # Test getting existing user
        user2 = self.profiler._create_test_user()
        self.assertEqual(user.user_id, user2.user_id)
    
    def test_cleanup_test_user(self):
        """Test cleanup of test user"""
        self.profiler._create_test_user()
        self.profiler._cleanup_test_user()
        
        exists = User.objects.filter(username='test_profiling_user').exists()
        self.assertFalse(exists)
    
    def test_profile_password_encoder(self):
        """Test profiling password encoder"""
        # Temporarily override ENV settings
        original_env = self.profiler.ENV.copy()
        self.profiler.ENV['PROFILING_ITERATIONS_ENCODER'] = '2'
        self.profiler.ENV['PROFILING_USE_CPROFILE'] = 'false'
        
        try:
            result = self.profiler.profile_password_encoder()
            
            self.assertIsInstance(result, dict)
            self.assertIn('avg_time', result)
            self.assertIn('iterations', result)
            self.assertEqual(result['iterations'], 2)
            self.assertGreater(result['avg_time'], 0)
        finally:
            self.profiler.ENV = original_env
    
    def test_profile_user_repository_get(self):
        """Test profiling user repository get operation"""
        original_env = self.profiler.ENV.copy()
        self.profiler.ENV['PROFILING_ITERATIONS_REPO'] = '3'
        
        try:
            result = self.profiler.profile_user_repository_get()
            
            self.assertIsInstance(result, dict)
            self.assertIn('avg_time', result)
            self.assertIn('iterations', result)
            self.assertEqual(result['iterations'], 3)
            self.assertGreaterEqual(result['avg_time'], 0)
        finally:
            self.profiler.ENV = original_env
    
    def test_profile_user_repository_save(self):
        """Test profiling user repository save operation"""
        original_env = self.profiler.ENV.copy()
        self.profiler.ENV['PROFILING_ITERATIONS_REPO'] = '2'
        
        try:
            result = self.profiler.profile_user_repository_save()
            
            self.assertIsInstance(result, dict)
            self.assertIn('avg_time', result)
            self.assertIn('iterations', result)
            self.assertEqual(result['iterations'], 2)
            self.assertGreater(result['avg_time'], 0)
        finally:
            self.profiler.ENV = original_env
    
    def test_profile_password_change_service(self):
        """Test profiling password change service"""
        original_env = self.profiler.ENV.copy()
        self.profiler.ENV['PROFILING_ITERATIONS_SERVICE'] = '2'
        self.profiler.ENV['PROFILING_USE_CPROFILE'] = 'false'
        
        try:
            result = self.profiler.profile_password_change_service()
            
            self.assertIsInstance(result, dict)
            self.assertIn('avg_time', result)
            self.assertIn('iterations', result)
            self.assertEqual(result['iterations'], 2)
            self.assertGreater(result['avg_time'], 0)
        finally:
            self.profiler.ENV = original_env
    
    def test_profile_account_deletion_service(self):
        """Test profiling account deletion service"""
        original_env = self.profiler.ENV.copy()
        self.profiler.ENV['PROFILING_ITERATIONS_DELETION'] = '2'
        
        try:
            result = self.profiler.profile_account_deletion_service()
            
            self.assertIsInstance(result, dict)
            self.assertIn('avg_time', result)
            self.assertIn('iterations', result)
            self.assertEqual(result['iterations'], 2)
            self.assertGreater(result['avg_time'], 0)
            
            # Verify users were actually deleted
            deletion_user_count = User.objects.filter(username__startswith='test_delete_user_').count()
            self.assertEqual(deletion_user_count, 0)
        finally:
            self.profiler.ENV = original_env
    
    def test_profile_change_password_serializer(self):
        """Test profiling change password serializer"""
        original_env = self.profiler.ENV.copy()
        self.profiler.ENV['PROFILING_ITERATIONS_SERIALIZER'] = '3'
        
        try:
            result = self.profiler.profile_change_password_serializer()
            
            self.assertIsInstance(result, dict)
            self.assertIn('avg_time', result)
            self.assertIn('iterations', result)
            self.assertEqual(result['iterations'], 3)
            self.assertGreaterEqual(result['avg_time'], 0)
        finally:
            self.profiler.ENV = original_env
    
    def test_profile_delete_account_serializer(self):
        """Test profiling delete account serializer"""
        original_env = self.profiler.ENV.copy()
        self.profiler.ENV['PROFILING_ITERATIONS_SERIALIZER'] = '3'
        
        try:
            result = self.profiler.profile_delete_account_serializer()
            
            self.assertIsInstance(result, dict)
            self.assertIn('avg_time', result)
            self.assertIn('iterations', result)
            self.assertEqual(result['iterations'], 3)
            self.assertGreaterEqual(result['avg_time'], 0)
        finally:
            self.profiler.ENV = original_env
    
    def test_profile_serializer_validation_errors(self):
        """Test profiling serializer validation errors"""
        original_env = self.profiler.ENV.copy()
        self.profiler.ENV['PROFILING_ITERATIONS_VALIDATION'] = '3'
        
        try:
            result = self.profiler.profile_serializer_validation_errors()
            
            self.assertIsInstance(result, dict)
            self.assertIn('avg_time', result)
            self.assertIn('iterations', result)
            self.assertEqual(result['iterations'], 3)
            self.assertGreaterEqual(result['avg_time'], 0)
        finally:
            self.profiler.ENV = original_env
    
    def test_profile_password_strength_validation(self):
        """Test profiling password strength validation"""
        original_env = self.profiler.ENV.copy()
        self.profiler.ENV['PROFILING_ITERATIONS_VALIDATION'] = '5'
        
        try:
            result = self.profiler.profile_password_strength_validation()
            
            self.assertIsInstance(result, dict)
            self.assertIn('avg_time', result)
            self.assertIn('iterations', result)
            self.assertEqual(result['iterations'], 5)
            self.assertGreaterEqual(result['avg_time'], 0)
        finally:
            self.profiler.ENV = original_env
    
    def test_run_basic_profiling_raises_not_implemented(self):
        """Test that run_basic_profiling raises NotImplementedError"""
        with self.assertRaises(NotImplementedError):
            self.profiler.run_basic_profiling()
    
    @patch.dict(os.environ, {
        'PROFILING_ENABLED': 'true',
        'PROFILING_ITERATIONS_ENCODER': '1',
        'PROFILING_ITERATIONS_REPO': '1',
        'PROFILING_ITERATIONS_SERVICE': '1',
        'PROFILING_ITERATIONS_SERIALIZER': '1',
        'PROFILING_ITERATIONS_VALIDATION': '1',
        'PROFILING_ITERATIONS_DELETION': '1',
        'PROFILING_USE_CPROFILE': 'false',
    })
    def test_run_complete_profiling(self):
        """Test complete profiling run"""
        self.profiler.run_complete_profiling()
        
        # Check that all components were profiled
        expected_components = [
            'password_encoder',
            'user_repository_get',
            'user_repository_save',
            'password_change_service',
            'change_password_serializer',
            'delete_account_serializer',
            'password_strength_validation',
            'serializer_validation_errors',
            'account_deletion_service',
        ]
        
        for component in expected_components:
            self.assertIn(component, self.profiler.results)
            self.assertIn('avg_time', self.profiler.results[component])
            self.assertIn('iterations', self.profiler.results[component])
    
    def test_run_complete_profiling_disabled(self):
        """Test that profiling can be disabled"""
        # Create a fresh profiler with disabled profiling
        from user_settings.profile_user_settings import UserSettingsProfiler
        
        with patch.dict(os.environ, {'PROFILING_ENABLED': 'false'}):
            profiler = UserSettingsProfiler()
            profiler.run_complete_profiling()
            
            # Results should be empty since profiling is disabled
            self.assertEqual(len(profiler.results), 0)
    
    @patch.dict(os.environ, {
        'PROFILING_ENABLED': 'true',
        'PROFILING_ITERATIONS_ENCODER': '1',
        'PROFILING_ITERATIONS_REPO': '1',
        'PROFILING_ITERATIONS_SERVICE': '1',
        'PROFILING_ITERATIONS_SERIALIZER': '1',
        'PROFILING_ITERATIONS_VALIDATION': '1',
        'PROFILING_ITERATIONS_DELETION': '1',
        'PROFILING_USE_CPROFILE': 'true',
    })
    def test_run_complete_profiling_with_cprofile(self):
        """Test complete profiling with cProfile enabled"""
        self.profiler.run_complete_profiling()
        
        # Check that cProfile stats were generated for key components
        self.assertTrue(
            'password_encoder' in self.profiler.cprofile_stats or
            'password_change_service' in self.profiler.cprofile_stats
        )
    
    def test_profiler_cleans_up_on_exception(self):
        """Test that profiler cleans up test user even on exception"""
        # Create test user
        self.profiler._create_test_user()
        
        # Mock a method to raise exception
        with patch.object(self.profiler, 'profile_password_encoder', side_effect=Exception("Test error")):
            with self.assertRaises(Exception):
                self.profiler.run_complete_profiling()
        
        # Test user should still be cleaned up
        exists = User.objects.filter(username='test_profiling_user').exists()
        # Note: cleanup happens in finally block, so this should be False
        self.assertFalse(exists)
    
    def test_cleanup_test_user_exception_handling(self):
        """Test that cleanup handles exceptions gracefully"""
        # Mock User.objects.filter to raise an exception
        with patch('authentication.models.User.objects.filter') as mock_filter:
            mock_filter.side_effect = Exception("Database error")
            
            # Should not raise exception, just print warning
            try:
                self.profiler._cleanup_test_user()
            except Exception:
                self.fail("_cleanup_test_user should not raise exception")


class ProfilerMainFunctionTest(TestCase):
    """Test the main() function"""
    
    @patch.dict(os.environ, {
        'PROFILING_ENABLED': 'true',
        'PROFILING_ITERATIONS_ENCODER': '1',
        'PROFILING_ITERATIONS_REPO': '1',
        'PROFILING_ITERATIONS_SERVICE': '1',
        'PROFILING_ITERATIONS_SERIALIZER': '1',
        'PROFILING_ITERATIONS_VALIDATION': '1',
        'PROFILING_ITERATIONS_DELETION': '1',
        'PROFILING_USE_CPROFILE': 'false',
    })
    def test_main_function(self):
        """Test that main function runs without error"""
        from user_settings.profile_user_settings import main
        
        # Should complete without raising exception
        try:
            main()
        except Exception as e:
            self.fail(f"main() raised unexpected exception: {e}")
    
    @patch('user_settings.profile_user_settings.UserSettingsProfiler')
    def test_main_function_calls_profiler(self, mock_profiler_class):
        """Test that main function creates and runs profiler"""
        from user_settings.profile_user_settings import main
        
        mock_profiler_instance = Mock()
        mock_profiler_class.return_value = mock_profiler_instance
        
        main()
        
        # Verify profiler was created and run
        mock_profiler_class.assert_called_once()
        mock_profiler_instance.run_complete_profiling.assert_called_once()


class ProfilerEnvironmentConfigTest(TestCase):
    """Test environment configuration handling"""
    
    def test_profiler_uses_environment_iterations(self):
        """Test that profiler respects environment iteration settings"""
        from user_settings.profile_user_settings import UserSettingsProfiler
        
        with patch.dict(os.environ, {'PROFILING_ITERATIONS_ENCODER': '5'}):
            profiler = UserSettingsProfiler()
            # Mock the callback to avoid actual encoding
            with patch.object(profiler, '_profile_component') as mock_profile:
                mock_profile.return_value = {'avg_time': 0.1, 'iterations': 5}
                profiler.profile_password_encoder()
                
                # Check that it was called with 5 iterations
                call_args = mock_profile.call_args
                self.assertEqual(call_args[0][1], 5)  # iterations parameter
    
    def test_profiler_uses_default_iterations_when_not_set(self):
        """Test that profiler uses default iterations when env not set"""
        from user_settings.profile_user_settings import UserSettingsProfiler
        
        # Remove environment variable if it exists
        env_copy = os.environ.copy()
        env_copy.pop('PROFILING_ITERATIONS_ENCODER', None)
        
        with patch.dict(os.environ, env_copy, clear=True):
            profiler = UserSettingsProfiler()
            with patch.object(profiler, '_profile_component') as mock_profile:
                mock_profile.return_value = {'avg_time': 0.1, 'iterations': 20}
                profiler.profile_password_encoder()
                
                # Should use default 20 iterations
                call_args = mock_profile.call_args
                self.assertEqual(call_args[0][1], 20)


class ProfilerIntegrationTest(TestCase):
    """Integration tests for full profiling flow"""
    
    @patch.dict(os.environ, {
        'PROFILING_ENABLED': 'true',
        'PROFILING_ITERATIONS_ENCODER': '2',
        'PROFILING_ITERATIONS_REPO': '2',
        'PROFILING_ITERATIONS_SERVICE': '2',
        'PROFILING_ITERATIONS_SERIALIZER': '2',
        'PROFILING_ITERATIONS_VALIDATION': '2',
        'PROFILING_ITERATIONS_DELETION': '2',
        'PROFILING_USE_CPROFILE': 'false',
    })
    def test_full_profiling_flow_with_real_operations(self):
        """Test complete profiling with real operations (integration test)"""
        from user_settings.profile_user_settings import UserSettingsProfiler
        
        profiler = UserSettingsProfiler()
        profiler.run_complete_profiling()
        
        # Verify all components ran
        self.assertEqual(len(profiler.results), 9)
        
        # Verify each result has expected structure
        for component_name, result in profiler.results.items():
            self.assertIn('avg_time', result)
            self.assertIn('min_time', result)
            self.assertIn('max_time', result)
            self.assertIn('iterations', result)
            self.assertIn('success_rate', result)
            
            # Verify success rate
            self.assertEqual(result['success_rate'], 100.0)
            
            # Verify iterations match expected
            self.assertEqual(result['iterations'], 2)
