from django import forms
from django.contrib.auth.hashers import check_password
from django.core.validators import EmailValidator, MinLengthValidator
from authentication.models import User
import re


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
            'required': 'Password is required.'
        }
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise forms.ValidationError("Username cannot be empty.")
        
        # Check if username contains only valid characters
        if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
            raise forms.ValidationError("Username can only contain letters, numbers, dots, hyphens, and underscores.")
        
        return username

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password:
            raise forms.ValidationError("Password cannot be empty.")
        if len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long.")
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
        validators=[
            MinLengthValidator(3, message="Username must be at least 3 characters long.")
        ],
        error_messages={
            'required': 'Username is required.',
            'max_length': 'Username must be 150 characters or less.'
        }
    )
    password = forms.CharField(
        max_length=255,
        strip=True,
        required=True,
        validators=[
            MinLengthValidator(8, message="Password must be at least 8 characters long.")
        ],
        error_messages={
            'required': 'Password is required.'
        }
    )
    confirm_password = forms.CharField(
        max_length=255,
        strip=True,
        required=True,
        error_messages={
            'required': 'Password confirmation is required.'
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
        validators=[EmailValidator()],
        error_messages={
            'required': 'Email is required.',
            'invalid': 'Please enter a valid email address.'
        }
    )
    roles = forms.JSONField(
        required=False,
        initial=list
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise forms.ValidationError("Username cannot be empty.")
        
        username = username.strip()
        
        if len(username) <= 3:
            raise forms.ValidationError("Username must be at least 3 characters long.")

        # Check if username contains only valid characters
        if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
            raise forms.ValidationError("Username can only contain letters, numbers, dots, hyphens, and underscores.")
        
        if username.isdigit():
            raise forms.ValidationError("Username cannot be entirely numeric.")
        
        if username.startswith(('.', '_')) or username.endswith(('.', '_')):
            raise forms.ValidationError("Username cannot start or end with a dot or underscore.")

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise forms.ValidationError("Email is required.")
        email = email.lower()
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password:
            raise forms.ValidationError("Password cannot be empty.")
        
        # Password strength validation
        if len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long.")
        
        if not re.search(r'[A-Z]', password):
            raise forms.ValidationError("Password must contain at least one uppercase letter.")
        
        if not re.search(r'[a-z]', password):
            raise forms.ValidationError("Password must contain at least one lowercase letter.")
        
        if not re.search(r'\d', password):
            raise forms.ValidationError("Password must contain at least one number.")
        
        return password
    
    def clean_display_name(self):
        display_name = self.cleaned_data.get('display_name')
        if not display_name or not display_name.strip():
            raise forms.ValidationError("A display name is required")
        
        if re.search(r'[<>"/\\]', display_name):
            raise forms.ValidationError("Display name cannot contain <, >, \", /, or \\ characters.")
        
        return display_name.strip()
    

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                raise forms.ValidationError("Passwords do not match.")
        
        return cleaned_data