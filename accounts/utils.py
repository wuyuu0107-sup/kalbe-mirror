import random
import string

def generate_otp(length=6):
    """Random 6 digit numeric OTP"""
    return "".join(random.choices(string.digits, k=length))