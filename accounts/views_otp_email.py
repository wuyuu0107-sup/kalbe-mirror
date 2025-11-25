# accounts/views_otp_email.py
import json
from typing import Any, Dict

from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt  # ⬅️ tambahin ini
from django.http import JsonResponse, HttpRequest
from django.core.mail import send_mail
from django.conf import settings
from django.apps import apps
from django.contrib.auth.hashers import make_password  # simpan password sbg hash
from django.core.cache import cache

from .utils import generate_otp
from .services import cache_store as cs
from .passwords import is_strong_password

# Pakai model milik app authentication → tabel authentication_user
AuthUser = apps.get_model("authentication", "User")


def _read_json(request: HttpRequest) -> Dict[str, Any]:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}


@csrf_exempt     # ⬅️ CSRF DIMATIKAN DI SINI
@require_POST
def password_reset_otp_request(request: HttpRequest) -> JsonResponse:
    """
    Kirim OTP via email kalau email terdaftar (anti user-enumeration: tetap 200).
    """
    data = _read_json(request)
    email = (data.get("email") or "").strip().lower()
    if not email:
        return JsonResponse({"error": "email is required"}, status=400)

    rate_key = f"pwdreset:otp:req:{email}"
    max_requests = 5
    rate_window = 10 * 60  # 10 menit
    attempts = cache.get(rate_key, 0)
    if attempts >= max_requests:
        return JsonResponse(
            {
                "error": "too_many_requests",
                "message": "You have requested OTP too many times. Please try again later.",
            },
            status=429,
        )

    # Cek ada user dengan email tsb; kalau tidak ada, tetap balas ok (anti-enum)
    try:
        AuthUser.objects.get(email=email)
    except AuthUser.DoesNotExist:
        return JsonResponse({"status": "ok"})
    
    cache.set(rate_key, attempts + 1, timeout=rate_window)

    otp = generate_otp()
    cs.store_otp(email, otp, ttl=600)  # berlaku 10 menit

    send_mail(
        subject="Your OTP Code",
        message=f"Your password reset code is: {otp}\n(valid 10 minutes)",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    return JsonResponse({"status": "ok"})

def _parse_payload(request):
    data = _read_json(request)

    email = (data.get("email") or "").strip().lower()
    otp_in = (data.get("otp") or "").strip()
    new_pw = (
        data.get("password")
        or data.get("new_password")
        or ""
    ).strip()

    return email, otp_in, new_pw

def _validate_payload(email, otp_in, new_pw):
    if not email or not otp_in or not new_pw:
        return False, "missing fields"

    if not is_strong_password(new_pw):
        return False, "weak password"

    return True, None

def _parse_and_validate_payload(request):
    email, otp_in, new_pw = _parse_payload(request)

    ok, error = _validate_payload(email, otp_in, new_pw)
    if not ok:
        return False, error

    return True, (email, otp_in, new_pw)

def _load_user(email):
    try:
        user = AuthUser.objects.get(email=email)
        return True, user
    except AuthUser.DoesNotExist:
        return False, "invalid email"
    
def _validate_otp(email, otp_in):
    otp_stored = cs.get_otp(email)
    if otp_stored and otp_stored == otp_in:
        return True, None
    return False, "invalid or expired otp"

def _update_user_password(user, new_pw):
    user.password = make_password(new_pw)

    # Bersihkan jejak OTP jika field tersedia
    update_fields = ["password"]
    if hasattr(user, "otp_code"):
        user.otp_code = ""
        update_fields.append("otp_code")

    if hasattr(user, "otp_expires_at"):
        user.otp_expires_at = None
        update_fields.append("otp_expires_at")

    user.save(update_fields=update_fields)

@csrf_exempt     # ⬅️ CSRF DIMATIKAN JUGA DI SINI
@require_POST
def password_reset_otp_confirm(request: HttpRequest) -> JsonResponse:
    """
    Verifikasi OTP & update password (HASH) di authentication_user.
    FE cukup kirim: { email, otp, password }
    """
    # Parse & validate
    ok, result = _parse_and_validate_payload(request)
    if not ok:
        return JsonResponse({"error": result}, status=400)
    email, otp_in, new_pw = result

    # Load user
    ok, user_or_error = _load_user(email)
    if not ok:
        return JsonResponse({"error": user_or_error}, status=400)
    user = user_or_error

    # Cocokkan OTP dari cache
    ok, otp_error = _validate_otp(email, otp_in)
    if not ok:
        return JsonResponse({"error": otp_error}, status=400)

    # Update Passowrd
    _update_user_password(user, new_pw)
    cs.delete_otp(email)

    # FE bisa redirect ke /authentication/login
    return JsonResponse(
        {
            "status": "success",
            "message": "Password updated successfully.",
            "redirect": "/authentication/login",
        }
    )
