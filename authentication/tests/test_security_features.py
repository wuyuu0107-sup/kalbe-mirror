from django.test import TestCase
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from datetime import timedelta
from authentication.models import User
import os

# Test constants to avoid hardcoded sensitive data
TEST_PASSWORD = os.environ.get('TEST_PASSWORD', 'TestSec@123#Pass')


class SecurityFeaturesTest(TestCase):
    """Test suite for security features like account locking and failed login tracking"""
    
    def setUp(self):
        self.user = User.objects.create(
            username="securitytest",
            password=make_password(TEST_PASSWORD),
            display_name="Security Test",
            email="security@example.com",
            is_verified=True
        )

    def test_is_authenticated_inactive_user(self):
        """Test is_authenticated property with inactive user - covers line 77"""
        # Set user as inactive
        self.user.is_active = False
        self.user.save()
        
        # Should not be authenticated
        self.assertFalse(self.user.is_authenticated)

    def test_is_account_locked_no_lock_time(self):
        """Test is_account_locked when account_locked_until is None - covers line 81"""
        # Make sure account_locked_until is None
        self.user.account_locked_until = None
        self.user.save()
        
        # Should not be locked
        self.assertFalse(self.user.is_account_locked())

    def test_increment_failed_login_before_limit(self):
        """Test increment_failed_login when below 5 attempts - covers line 93"""
        # Set to 3 failed attempts (below limit)
        self.user.failed_login_attempts = 3
        self.user.save()
        
        # Increment should not lock account yet
        result = self.user.increment_failed_login()
        
        self.assertFalse(result)  # Should return False (not locked)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 4)
        self.assertIsNone(self.user.account_locked_until)

    def test_increment_failed_login_at_limit(self):
        """Test increment_failed_login when reaching 5 attempts - covers lines 101-103"""
        # Set to 4 failed attempts (one before limit)
        self.user.failed_login_attempts = 4
        self.user.save()
        
        # Increment should lock account
        result = self.user.increment_failed_login()
        
        self.assertTrue(result)  # Should return True (account locked)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 5)
        self.assertIsNotNone(self.user.account_locked_until)
        
        # Should be locked for approximately 30 minutes
        time_diff = self.user.account_locked_until - timezone.now()
        self.assertAlmostEqual(time_diff.total_seconds(), 30 * 60, delta=60)

    def test_get_remaining_login_attempts_edge_cases(self):
        """Test get_remaining_login_attempts with various scenarios - covers line 116"""
        # Test with 0 failed attempts
        self.user.failed_login_attempts = 0
        self.user.save()
        self.assertEqual(self.user.get_remaining_login_attempts(), 5)
        
        # Test with 3 failed attempts
        self.user.failed_login_attempts = 3
        self.user.save()
        self.assertEqual(self.user.get_remaining_login_attempts(), 2)
        
        # Test with 5 or more failed attempts (should return 0)
        self.user.failed_login_attempts = 5
        self.user.save()
        self.assertEqual(self.user.get_remaining_login_attempts(), 0)
        
        # Test with more than 5 failed attempts (edge case)
        self.user.failed_login_attempts = 10
        self.user.save()
        self.assertEqual(self.user.get_remaining_login_attempts(), 0)

    def test_account_locking_workflow_complete(self):
        """Test complete account locking workflow"""
        # Start with clean user
        self.assertEqual(self.user.failed_login_attempts, 0)
        self.assertFalse(self.user.is_account_locked())
        
        # Increment 4 times (should not lock)
        for _ in range(4):  # Use underscore for unused loop variable
            result = self.user.increment_failed_login()
            self.assertFalse(result)
            self.assertFalse(self.user.is_account_locked())
        
        # 5th attempt should lock account
        result = self.user.increment_failed_login()
        self.assertTrue(result)
        self.assertTrue(self.user.is_account_locked())
        
        # Reset should unlock
        self.user.reset_failed_login_attempts()
        self.assertFalse(self.user.is_account_locked())
        self.assertEqual(self.user.failed_login_attempts, 0)

    def test_account_unlock_after_time_expires(self):
        """Test that account unlocks after lock time expires"""
        # Set account as locked with expired time
        self.user.account_locked_until = timezone.now() - timedelta(minutes=5)
        self.user.save()
        
        # Should not be locked anymore
        self.assertFalse(self.user.is_account_locked())
        
        # Set account as locked with future time
        self.user.account_locked_until = timezone.now() + timedelta(minutes=5)
        self.user.save()
        
        # Should still be locked
        self.assertTrue(self.user.is_account_locked())

    def test_is_authenticated_with_locked_account(self):
        """Test is_authenticated returns False when account is locked - covers line 81"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Set user as verified and active
        self.user.is_verified = True
        self.user.is_active = True
        
        # Lock the account
        self.user.account_locked_until = timezone.now() + timedelta(minutes=30)
        self.user.save()
        
        # Should not be authenticated due to account lock
        self.assertFalse(self.user.is_authenticated)