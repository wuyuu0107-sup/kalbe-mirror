from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
@require_POST
def register(request):
    try:
        data = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error: invalid payload"}, status = 400)

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return JsonResponse({"error": "username and password required"}, status=400)
    
    user = User.objects.create_user(username=username, password=password)
    return JsonResponse({
        "user_id" : f"user {user.id}",
        "message": "Registration is successful. Please log in"},
        status=201
    )