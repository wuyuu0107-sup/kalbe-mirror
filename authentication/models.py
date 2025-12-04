from django.db import models
import uuid
from django.core.validators import MinLengthValidator
from django.utils import timezone
from datetime import timedelta

class User(models.Model):
    user_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    username = models.CharField(
        max_length=150,
        unique=True
    )
    password = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(8)]
    )
    display_name = models.CharField(
        max_length=150
    )
    email = models.EmailField(
        unique=True
    )
    last_accessed = models.DateTimeField(
        auto_now=True
    )
    roles = models.JSONField(  
        default=list
    )

    auth_latency_ms = models.FloatField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    otp_code = models.CharField(max_length=6, blank=True, default='')
    otp_expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Security fields for failed login attempts
    failed_login_attempts = models.IntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'username'  
    REQUIRED_FIELDS = ['email']  

    def __str__(self):
        return self.username

    @property
    def is_authenticated(self):
        """
        Secure authentication check that validates multiple security criteria.
        
        A user is considered authenticated if ALL of the following are true:
        1. User has a valid user_id (exists in database)
        2. User email is verified
        3. User account is active
        4. User account is not locked due to failed login attempts
        5. User was created (not a temporary/invalid account)
        
        Returns:
            bool: True if user meets all security requirements, False otherwise
        """
        # Check if user has valid ID (basic existence check)
        if not getattr(self, 'user_id', None):
            return False
            
        # Check if email is verified (security requirement)
        if not getattr(self, 'is_verified', False):
            return False
            
        # Check if account is active
        if not getattr(self, 'is_active', True):
            return False
            
        # Check if account is locked due to failed login attempts
        if self.is_account_locked():
            return False
            
        # Check if user has a creation timestamp (prevents temporary accounts)
        if not getattr(self, 'created_at', None):
            return False
            
        return True

    def is_account_locked(self):
        """Check if account is currently locked due to failed login attempts"""
        if not self.account_locked_until:
            return False
            
        # Check if lock period has expired
        if timezone.now() >= self.account_locked_until:
            # Auto-unlock: clear lock time and reset failed attempts
            self.account_locked_until = None
            self.failed_login_attempts = 0
            self.save(update_fields=['account_locked_until', 'failed_login_attempts'])
            return False
            
        return True  # Still locked

    def increment_failed_login(self):
        """Increment failed login attempts and lock account if limit reached"""
        self.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts for 30 minutes
        if self.failed_login_attempts >= 5:
            self.account_locked_until = timezone.now() + timedelta(minutes=30)
            self.save(update_fields=['failed_login_attempts', 'account_locked_until'])
            return True  # Account is now locked
        else:
            self.save(update_fields=['failed_login_attempts'])
            return False  # Account not locked yet

    def reset_failed_login_attempts(self):
        """Reset failed login attempts and unlock account on successful login"""
        self.failed_login_attempts = 0
        self.account_locked_until = None
        self.save(update_fields=['failed_login_attempts', 'account_locked_until'])

    def get_remaining_login_attempts(self):
        """Get number of remaining login attempts before account lock"""
        return max(0, 5 - self.failed_login_attempts)

    def generate_otp(self, otp_validity_minutes=10):
        """Generate OTP code and set expiry time"""
        import random
        
        # Generate 6-digit OTP
        self.otp_code = str(random.randint(100000, 999999))
        
        # Set expiry time
        self.otp_expires_at = timezone.now() + timedelta(minutes=otp_validity_minutes)
        
        self.save(update_fields=['otp_code', 'otp_expires_at'])
        return self.otp_code

    def verify_otp(self, provided_otp):
        """Verify OTP code and return True if valid"""
        if not self.otp_code or not self.otp_expires_at:
            return False
            
        # Check if OTP has expired
        if timezone.now() > self.otp_expires_at:
            # Clear expired OTP
            self.otp_code = ''
            self.otp_expires_at = None
            self.save(update_fields=['otp_code', 'otp_expires_at'])
            return False
            
        # Check if OTP matches
        if self.otp_code == provided_otp:
            # Mark as verified and clear OTP
            self.is_verified = True
            self.otp_code = ''
            self.otp_expires_at = None
            self.save(update_fields=['is_verified', 'otp_code', 'otp_expires_at'])
            return True
            
        return False

    def is_otp_expired(self):
        """Check if OTP has expired"""
        if not self.otp_expires_at:
            return True
        return timezone.now() > self.otp_expires_at