from django.core.mail import send_mail
from django.conf import settings

def send_otp_email(to_email: str, otp: str):
    body = (
        "Your password reset code (valid 10 minutes):\n\n"
        f"{otp}\n\nIf you didn't request this, ignore."
    )
    send_mail(
        subject="Your OTP Code",
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[to_email],
        fail_silently=False,  
    )
