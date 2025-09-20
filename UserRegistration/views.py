from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError, transaction
from django.contrib.auth.hashers import make_password
from UserRegistration.models import User
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
        {"user_id": str(u.user_id), "message": "Registration successful. Please log in."},
        status=201
    )
