import json
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.shortcuts import resolve_url
from django.conf import settings
from .tokens import password_reset_token as token_gen
from .passwords import is_strong_password

def _read_json(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}

@require_POST
def password_reset_request(request):
    data = _read_json(request)
    email = (data.get("email") or "").strip().lower()
    # anti user-enumeration: selalu 200
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({"status": "ok"})

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_gen.make_token(user)

    backend_link = request.build_absolute_uri(
        resolve_url("password-reset-confirm", uidb64=uid, token=token)
    )
    body = ["Use the link below to reset your password (one-time):", backend_link]

    fe_url = getattr(settings, "FRONTEND_RESET_URL", None)
    if fe_url:
        body.append(f"FE page: {fe_url}?uid={uid}&token={token}")

    send_mail(
        subject="Password Reset",
        message="\n".join(body),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[email],
    )
    return JsonResponse({"status": "ok"})

@require_POST
def password_reset_confirm(request, uidb64, token):
    data = _read_json(request)
    new_password = data.get("password")
    if not is_strong_password(new_password):
        return JsonResponse({"error": "weak password"}, status=400)

    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except Exception:
        return JsonResponse({"error": "invalid link"}, status=400)

    if not token_gen.check_token(user, token):
        return JsonResponse({"error": "invalid or expired token"}, status=400)

    user.set_password(new_password)
    user.save()
    return JsonResponse({"status": "password-updated"})
