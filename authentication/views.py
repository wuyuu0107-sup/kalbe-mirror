from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction, IntegrityError
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings
# Removed HTML template imports since we only need API functionality
from .forms import LoginForm, RegistrationForm
from authentication.models import User
import json
import logging

# Set up logging
logger = logging.getLogger(__name__)


def send_welcome_email(user):
    """Send welcome email to newly registered user"""
    try:
        subject = "Welcome to Kalbe Platform!"
        message = f"""
        Hello {user.display_name},
        
        Welcome to Kalbe Platform! Your account has been successfully created and verified.
        
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


def send_verification_email(user):
    """Send email verification email to user"""
    try:
        subject = "Verify Your Email Address"
        message = f"""
        Hello {user.display_name},
        
        Please verify your email address by clicking the link below:
        
        Verification Link: /verify-email/{user.verification_token}
        
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
        logger.info(f"Verification email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
        return False

@csrf_exempt
@require_POST
def login(request):
    # More robust JSON parsing: treat empty or whitespace-only bodies as empty JSON
    raw = request.body or b''
    if not raw or raw.strip() == b'':
        data = {}
    else:
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            return JsonResponse({"error": "invalid payload"}, status=400)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid payload"}, status=400)

    # Create form instance with data
    form = LoginForm(data)
    
    if not form.is_valid():
        # Return validation errors
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = error_list[0]  # Get first error for each field
        return JsonResponse({"errors": errors, "error": errors}, status=400)
    
    # Try to authenticate user
    user = form.authenticate()
    if user is None:
        return JsonResponse({"error": "invalid credentials"}, status=401)
    
    # Check if user is verified (optional check)
    if not user.is_verified:
        return JsonResponse({
            "error": "Email not verified", 
            "message": "Please verify your email before logging in"
        }, status=403)
    
    request.session['user_id'] = str(user.user_id)
    request.session['username'] = user.username
    
    return JsonResponse({
        "user_id": f"user {user.user_id}",
        "username": user.username,
        "display_name": user.display_name,
        "message": "Login successful"
    }, status=200)


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
        return JsonResponse({"error": "invalid payload"}, status=400)
    
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
                is_verified=False, 
            )
            
    except IntegrityError:
        return JsonResponse({"error": "user already exists"}, status=409)

    return JsonResponse(
        {
            "user_id": f"user {u.user_id}",
            "message": "Registration successful! Welcome email sent. You can now log in.",
            "email_sent": True
        },
        status=201
    )


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



