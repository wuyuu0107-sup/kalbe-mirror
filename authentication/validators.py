from django import forms
import re

def validate_username(username: str):
    if not username or not username.strip():
        raise forms.ValidationError("Username cannot be empty.")
    
    username = username.strip()
    if len(username) <= 3:
        raise forms.ValidationError("Username must be at least 3 characters long.")
    if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
        raise forms.ValidationError("Username can only contain letters, numbers, dots, hyphens, and underscores.")
    if username.isdigit():
        raise forms.ValidationError("Username cannot be entirely numeric.")
    if username.startswith(('.', '_')) or username.endswith(('.', '_')):
        raise forms.ValidationError("Username cannot start or end with a dot or underscore.")
    
    return username


def validate_password(password: str):

    if not password:
        raise forms.ValidationError("Password cannot be empty.")
    if len(password) < 8:
        raise forms.ValidationError("Password must be at least 8 characters long.")
    if not re.search(r'[A-Z]', password):
        raise forms.ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r'[a-z]', password):
        raise forms.ValidationError("Password must contain at least one lowercase letter.")
    if not re.search(r'\d', password):
        raise forms.ValidationError("Password must contain at least one number.")
    
    return password


def validate_display_name(display_name: str):

    if not display_name or not display_name.strip():
        raise forms.ValidationError("A display name is required")
    if re.search(r'[<>"/\\]', display_name):
        raise forms.ValidationError('Display name cannot contain <, >, ", /, or \\ characters.')
    
    return display_name.strip()


def validate_email(email: str, model_cls):
    if not email or not email.strip():
        raise forms.ValidationError("Email is required.")
    
    email = email.lower().strip()
    if model_cls.objects.filter(email=email).exists():
        raise forms.ValidationError("This email is already registered.")
    
    return email