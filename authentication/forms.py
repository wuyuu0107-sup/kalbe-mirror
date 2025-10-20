# authentication/forms.py
from django import forms
from django.contrib.auth.hashers import check_password
from authentication.models import User
from authentication.validators import (validate_username, validate_password, validate_display_name, validate_email)

class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        strip=True,
        required=True,
        error_messages={
            'required': 'Username is required.',
            'max_length': 'Username must be 150 characters or less.'
        }
    )
    password = forms.CharField(
        max_length=255,
        strip=True,
        required=True,
        error_messages={
            'required': 'Password is required.',
            'max_length': 'Password must be 255 characters or less.'
        }
    )

    def clean_username(self):
        username = (self.cleaned_data.get('username') if self.cleaned_data else None)
        return validate_username(username)

    def clean_password(self):
        # For login, just return the password without validation
        # We only need to check if it matches, not if it meets requirements
        password = self.cleaned_data.get('password')
        if not password:
            raise forms.ValidationError('Password is required.')
        return password

    def authenticate(self):
        if not self.is_valid():
            return None
        username = self.cleaned_data['username']
        password = self.cleaned_data['password']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None
        if check_password(password, user.password):
            return user
        return None


class RegistrationForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        strip=True,
        required=True,
        error_messages={
            'required': 'Username is required.',
            'max_length': 'Username must be 150 characters or less.'
        }
    )
    password = forms.CharField(
        max_length=255,
        strip=True,
        required=True,
        error_messages={
            'required': 'Password is required.',
            'max_length': 'Password must be 255 characters or less.'
        }
    )
    confirm_password = forms.CharField(
        max_length=255,
        strip=True,
        required=True,
        error_messages={
            'required': 'Password confirmation is required.',
            'max_length': 'Password must be 255 characters or less.'
        }
    )
    display_name = forms.CharField(
        max_length=150,
        strip=True,
        required=True,
        error_messages={
            'required': 'Display name is required.',
            'max_length': 'Display name must be 150 characters or less.'
        }
    )
    email = forms.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required.',
            'invalid': 'Please enter a valid email address.'
        }
    )

    roles = forms.JSONField(required=False, initial=list)

    def clean_username(self):
        username = self.cleaned_data.get('username') if self.cleaned_data else None
        username = validate_username(username)
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_password(self):
        return validate_password(self.cleaned_data.get('password'))

    def clean_display_name(self):
        return validate_display_name(self.cleaned_data.get('display_name'))

    def clean_email(self):
        email = self.cleaned_data.get('email')
        return validate_email(email, User)

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data