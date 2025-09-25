from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction, IntegrityError
from django.contrib.auth.hashers import check_password, make_password
from UserRegistration.models import User
import json

@csrf_exempt
@require_POST
def register(request):
    try:
        data = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid payload"}, status = 400)

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return JsonResponse({"error": "username and password required"}, status=400)
    
    try:
        with transaction.atomic():
            user = User.objects.create(
                username=username,
                password=make_password(password),  # hash for security
            )
    except IntegrityError:
        # unique username handled here if model enforces it
        return JsonResponse({"error": "user already exists"}, status=409)

    return JsonResponse({
        "user_id" : f"user {user.user_id}",
        "message": "Registration is successful. Please log in"},
        status=201
    )

@csrf_exempt
@require_POST
def login(request):
    try:
        data = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid payload"}, status=400)

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return JsonResponse({"error": "username and password required"}, status=400)

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({"error": "invalid credentials"}, status=401)

    if not check_password(password, user.password):
        return JsonResponse({"error": "invalid credentials"}, status=401)

    return JsonResponse({
        "user_id": f"user {user.user_id}",
        "message": "Login successful"
    }, status=200)