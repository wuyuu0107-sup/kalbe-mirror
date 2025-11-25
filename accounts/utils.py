import secrets
import string

def generate_otp(length=6):
    """Random 6 digit numeric OTP"""
    return ''.join(secrets.choice(string.digits) for _ in range(length))