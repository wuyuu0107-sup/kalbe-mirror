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

    is_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    otp_code = models.CharField(max_length=6, null=True, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
        3. User was created (not a temporary/invalid account)
        
        Returns:
            bool: True if user meets all security requirements, False otherwise
        """
        # Check if user has valid ID (basic existence check)
        if not getattr(self, 'user_id', None):
            return False
            
        # Check if email is verified (security requirement)
        if not getattr(self, 'is_verified', False):
            return False
            
        # Check if user has a creation timestamp (prevents temporary accounts)
        if not getattr(self, 'created_at', None):
            return False
            
        return True


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
            self.otp_code = None
            self.otp_expires_at = None
            self.save(update_fields=['otp_code', 'otp_expires_at'])
            return False
            
        # Check if OTP matches
        if self.otp_code == provided_otp:
            # Mark as verified and clear OTP
            self.is_verified = True
            self.otp_code = None
            self.otp_expires_at = None
            self.save(update_fields=['is_verified', 'otp_code', 'otp_expires_at'])
            return True
            
        return False

    def is_otp_expired(self):
        """Check if OTP has expired"""
        if not self.otp_expires_at:
            return True
        return timezone.now() > self.otp_expires_at