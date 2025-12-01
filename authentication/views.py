from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction, IntegrityError
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
# Removed HTML template imports since we only need API functionality
from .forms import LoginForm, RegistrationForm
from authentication.models import User
from authentication.helpers import parse_json_body, get_user_or_none, handle_failed_login, set_user_session, build_success_response

import time
import json
import logging

# Constants for error messages
INVALID_PAYLOAD_MSG = "invalid payload"

# Set up logging
logger = logging.getLogger(__name__)


def send_otp_email(user):
    """Send OTP verification email to user"""
    try:
        # Generate OTP
        otp_code = user.generate_otp()
        
        subject = "Verify Your Email - OTP Code"
        message = f"""
        Hello {user.display_name},
        
        Your OTP verification code is: {otp_code}
        
        This code will expire in 10 minutes.
        
        Please enter this code on the website to verify your email address.
        
        If you didn't create this account, please ignore this email.
        
        Best regards,
        Kalbe Platform Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"OTP verification email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email to {user.email}: {str(e)}")
        return False


def send_welcome_email(user):
    """Send welcome email to newly verified user"""
    try:
        subject = "Welcome to Kalbe Platform!"
        message = f"""
        Hello {user.display_name},
        
        Welcome to Kalbe Platform! Your email has been successfully verified.
        
        Username: {user.username}
        Email: {user.email}
        
        You can now log in to your account and start using our services.
        
        Best regards,
        Kalbe Platform Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Welcome email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
        return False


@csrf_exempt  
@require_POST
def logout(request):
    request.session.flush()
    return JsonResponse({'message': 'Logged out'}, status=200)


@csrf_exempt
@require_POST
def register_profile(request):
    try: 
        data = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": INVALID_PAYLOAD_MSG}, status=400)
    
    # Create form instance with data
    form = RegistrationForm(data)
    
    if not form.is_valid():
        # Return validation errors
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = error_list[0] if isinstance(error_list, list) else str(error_list)
        return JsonResponse({"errors": errors}, status=400)

    # Get cleaned data
    username = form.cleaned_data['username']
    password = form.cleaned_data['password']
    display_name = form.cleaned_data['display_name']
    email = form.cleaned_data['email']
    roles = form.cleaned_data.get('roles', [])

    # Hash password
    encoded = make_password(password)

    # attempt insert (unique: username, email)
    try:
        with transaction.atomic():
            u = User.objects.create(
                username=username,
                password=encoded,
                display_name=display_name,
                email=email,
                roles=roles or [],
                is_verified=False,  # Not verified until OTP is confirmed
            )
            
            # Send OTP email instead of verification link
            otp_sent = send_otp_email(u)
            
    except IntegrityError:
        return JsonResponse({"error": "user already exists"}, status=409)

    return JsonResponse(
        {
            "user_id": f"user {u.user_id}",
            "message": "Registration successful! Please check your email for OTP verification code.",
            "otp_sent": otp_sent,
            "instructions": "Enter the 6-digit code from your email to verify your account."
        },
        status=201
    )


@csrf_exempt
@require_POST
def verify_otp(request):
    """Verify OTP code sent to user's email"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        username = data.get('username')
        otp_code = data.get('otp_code')
        
        if not username or not otp_code:
            return JsonResponse({"error": "Username and OTP code are required"}, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        user = User.objects.get(username=username)
        
        if user.is_verified:
            return JsonResponse({"message": "Account already verified"}, status=200)
        
        # Verify OTP
        if user.verify_otp(otp_code):
            # Send welcome email after successful verification
            welcome_sent = send_welcome_email(user)
            
            return JsonResponse({
                "success": True,
                "message": "Email verified successfully! Welcome email sent.",
                "details": "You can now log in to your account",
                "welcome_email_sent": welcome_sent
            }, status=200)
        else:
            # Check if OTP has expired
            if user.is_otp_expired():
                return JsonResponse({
                    "error": "OTP code has expired. Please request a new one."
                }, status=400)
            else:
                return JsonResponse({
                    "error": "Invalid OTP code. Please check and try again."
                }, status=400)
                
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)


@csrf_exempt
@require_POST
def resend_otp(request):
    """Resend OTP code to user's email"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        username = data.get('username')
        
        if not username:
            return JsonResponse({"error": "Username is required"}, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        user = User.objects.get(username=username)
        
        if user.is_verified:
            return JsonResponse({"message": "Account already verified"}, status=200)
        
        # Send new OTP email
        otp_sent = send_otp_email(user)
        
        if otp_sent:
            return JsonResponse({
                "success": True,
                "message": "New OTP code sent to your email",
                "instructions": "Please check your email for the 6-digit verification code"
            }, status=200)
        else:
            return JsonResponse({
                "error": "Failed to send OTP email. Please try again later."
            }, status=500)
                
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)


@csrf_exempt
@require_POST
def verify_email(request, token):
    try:
        user = User.objects.get(verification_token=token)
    except User.DoesNotExist:
        return JsonResponse({"error": "Invalid token"}, status=400)

    if user.is_verified:
        return JsonResponse({"message": "Already verified"}, status=200)

    user.is_verified = True 
    user.save(update_fields=["is_verified"])
    
    # Send welcome email after verification
    send_welcome_email(user)
    
    logger.info(f"Email verified for user: {user.username}")
    
    return JsonResponse({
        "success": True,
        "message": "Email verified successfully! Welcome email sent.",
        "details": "You can now log in to your account"
    }, status=200)


def protected_endpoint(request):
    user_id_from_session = request.session.get('user_id')
    username_from_session = request.session.get('username')

    if user_id_from_session and username_from_session:

        return JsonResponse({
            "ok": True,
            "user_id": user_id_from_session,
            "username": username_from_session
        }, status=200)
    else:
        return JsonResponse({"error": "unauthorized"}, status=401)
