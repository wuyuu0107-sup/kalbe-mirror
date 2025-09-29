from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction, IntegrityError
from django.contrib.auth.hashers import make_password
from authentication.models import User
from .forms import LoginForm, RegistrationForm
import json
import logging

# Set up logging
logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def login(request):
    try:
        # More robust JSON parsing
        if request.body:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except UnicodeDecodeError:
                return JsonResponse({"error": "invalid payload"}, status=400)
        else:
            data = {}
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
            )
    except IntegrityError:
        return JsonResponse({"error": "user already exists"}, status=409)

    return JsonResponse(
        {
            "user_id": f"user {u.user_id}",
            "message": "Registration is successful. Please log in",
            "verification_link": f"/verify-email/{u.verification_token}"  # stub link
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
    
    logger.info(f"Email verified for user: {user.username}")
    
    return JsonResponse({
        "success": True,
        "message": "Email verified successfully",
        "details": "You can now log in to your account"
    }, status=200)


def protected_endpoint(request):
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({"error": "unauthorized"}, status=401)
    return JsonResponse({"ok": True, "user": request.user.username}, status=200)

@csrf_exempt  
@require_POST
def logout(request):
    request.session.flush()
    return JsonResponse({'message': 'Logged out'}, status=200)
