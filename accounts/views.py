# accounts/views.py
import json
from typing import Any, Dict

from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpRequest
from django.contrib.auth.models import User
from django.core.cache import cache

from .passwords import is_strong_password  # asumsi sudah ada
from .utils import generate_otp


def _read_json(request: HttpRequest) -> Dict[str, Any]:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}


@require_POST
def request_password_reset(request: HttpRequest) -> JsonResponse:
    """
    Phase 1: minta OTP reset password.
    Anti user-enumeration: selalu balikin {"status":"ok"} walau email ga terdaftar.
    """
    data = _read_json(request)
    email = (data.get("email") or "").strip().lower()
    if not email:
        return JsonResponse({"error": "email is required"}, status=400)

    # Hindari F841: jangan assign ke variabel kalau ga dipakai.
    if User.objects.filter(email=email).exists():
        otp = generate_otp(6)
        cache.set(f"pwdreset:{email}", otp, timeout=10 * 60)  # 10 menit
        # TODO: kirim OTP via email/SMS/WhatsApp di sini (asinkron lebih baik)
        # Contoh placeholder (non-aktif):
        # send_password_reset_otp(email=email, otp=otp)

    return JsonResponse({"status": "ok"})


@require_POST
def reset_password_confirm(request: HttpRequest) -> JsonResponse:
    """
    Phase 2: verifikasi OTP + set password baru.
    Tetap balikin {"status":"ok"} pada kegagalan verifikasi demi anti-enumeration.
    """
    data = _read_json(request)
    email = (data.get("email") or "").strip().lower()
    otp = (data.get("otp") or "").strip()
    new_password = (data.get("new_password") or "").strip()

    if not email or not otp or not new_password:
        return JsonResponse({"error": "missing fields"}, status=400)

    if not is_strong_password(new_password):
        return JsonResponse({"error": "weak_password"}, status=400)

    cached = cache.get(f"pwdreset:{email}")
    if not cached or cached != otp:
        # Jawaban generik—jangan bocorin apakah email/OTP valid
        return JsonResponse({"status": "ok"})

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Tetap generik
        return JsonResponse({"status": "ok"})

    user.set_password(new_password)
    user.save()
    cache.delete(f"pwdreset:{email}")

    return JsonResponse({"status": "ok"})
