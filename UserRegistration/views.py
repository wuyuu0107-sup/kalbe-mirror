from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError, transaction
from django.contrib.auth.hashers import make_password
from UserRegistration.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import json

# Create your views here.

@csrf_exempt
@require_POST
def register_profile(request):
    try: 
        data = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid payload"}, status=400)
    
    # Fields from data
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    display_name = (data.get("display_name") or "").strip()
    email = (data.get("email") or "").strip()
    roles = data.get("roles", [])

    # required fields
    if not username or not password or not display_name or not email:
        return JsonResponse({"error": "missing required fields"}, status=400)
    
    try:
        validate_password(password)
    except ValidationError as e:
        return JsonResponse({"error": e.messages}, status=400)

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
            "user_id": str(u.user_id),
            "message": "Registration successful. Please log in.",
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
    return JsonResponse({"message": "Email verified successfully"}, status=200)
