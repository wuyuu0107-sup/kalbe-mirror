import json
from django.http import JsonResponse
from authentication.models import User

def parse_json_body(request):
    raw = request.body or b''
    if not raw.strip():
        return {}, None
    try:
        text = raw.decode('utf-8')
        return json.loads(text), None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, JsonResponse({"error": "invalid payload"}, status=400)


def get_user_or_none(username):
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return None


def handle_failed_login(user):
    account_locked = user.increment_failed_login()
    if account_locked:
        return JsonResponse({
            "error": "Account temporarily locked. Please try again later."
        }, status=423)
    return JsonResponse({"error": "Invalid credentials"}, status=401)


def set_user_session(request, user):
    request.session['user_id'] = str(user.user_id)
    request.session['username'] = user.username


def build_success_response(user):
    return {
        "user_id": f"user {user.user_id}",
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "message": "Login successful"
    }