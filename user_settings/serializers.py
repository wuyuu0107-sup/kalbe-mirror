from django import forms
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from authentication.validators import validate_password


class ChangePasswordSerializer(forms.Form):
    """
    Serializer for password change request.
    Validates current password and new password strength.
    """
    current_password = forms.CharField(
        max_length=255,
        widget=forms.PasswordInput(),
        help_text="Current password for verification"
    )
    new_password = forms.CharField(
        max_length=255,
        min_length=8,
        widget=forms.PasswordInput(),
        help_text="New password (minimum 8 characters)"
    )
    confirm_password = forms.CharField(
        max_length=255,
        widget=forms.PasswordInput(),
        help_text="Confirm new password"
    )

    def __init__(self, user=None, *args, **kwargs):
        """Initialize with user instance for password verification"""
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        """Validate that the current password is correct"""
        current_password = self.cleaned_data.get('current_password')
        
        if not current_password:
            raise ValidationError("Current password is required")
        
        if self.user:
            passwords_match = check_password(current_password, self.user.password)
            if not passwords_match:
                raise ValidationError("Current password is incorrect")
        
        return current_password

    def clean_new_password(self):
        """Validate new password strength"""
        new_password = self.cleaned_data.get('new_password')
        current_password = self.cleaned_data.get('current_password')
        
        if not new_password:
            raise ValidationError("New password is required")
        
        # Check if new password is different from current password
        if current_password and new_password == current_password:
            raise ValidationError("New password must be different from current password")
        
        # Password strength validation – reuse authentication validator
        try:
            validate_password(new_password)
        except forms.ValidationError as exc:
            raise ValidationError(exc.messages)

        return new_password

    def clean(self):
        """Additional validation for password confirmation"""
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError("New password and confirmation password do not match")

        return cleaned_data

    def validate_data(self, data):
        """
        Alternative validation method for JSON data
        Returns tuple of (is_valid, errors_dict)
        """
        self.data = data
        self.is_bound = True
        
        try:
            self.full_clean()
            return True, {}
        except ValidationError as e:
            return False, {'non_field_errors': e.messages}
        except Exception as e:
            errors = {}
            if hasattr(self, 'errors'):
                errors = dict(self.errors)
            return False, errors