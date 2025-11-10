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

    # Cek ada user dengan email tsb; kalau tidak ada, tetap balas ok (anti-enum)
    try:
        AuthUser.objects.get(email=email)
    except AuthUser.DoesNotExist:
        return JsonResponse({"status": "ok"})

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


@csrf_exempt     # ⬅️ CSRF DIMATIKAN JUGA DI SINI
@require_POST
def password_reset_otp_confirm(request: HttpRequest) -> JsonResponse:
    """
    Verifikasi OTP & update password (HASH) di authentication_user.
    FE cukup kirim: { email, otp, password }
    """
    data = _read_json(request)
    email = (data.get("email") or "").strip().lower()
    otp_in = (data.get("otp") or "").strip()
    new_pw = (
        data.get("password")       # FE kamu kirim `password`
        or data.get("new_password")  # jaga-jaga kalau nanti ganti nama field
        or ""
    ).strip()

    if not email or not otp_in or not new_pw:
        return JsonResponse({"error": "missing fields"}, status=400)

    # Validasi kekuatan password
    if not is_strong_password(new_pw):
        return JsonResponse({"error": "weak password"}, status=400)

    try:
        user = AuthUser.objects.get(email=email)
    except AuthUser.DoesNotExist:
        # Up to you: mau generic atau spesifik.
        return JsonResponse({"error": "invalid email"}, status=400)

    # Cocokkan OTP dari cache
    otp_stored = cs.get_otp(email)
    if (not otp_stored) or (otp_stored != otp_in):
        return JsonResponse({"error": "invalid or expired otp"}, status=400)

    # ✅ Simpan password sebagai HASH yang kompatibel dengan check_password
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
    cs.delete_otp(email)

    # FE bisa redirect ke /authentication/login
    return JsonResponse(
        {
            "status": "success",
            "message": "Password updated successfully.",
            "redirect": "/authentication/login",
        }
    )
