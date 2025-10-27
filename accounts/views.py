# accounts/views.py
import json
from typing import Any, Dict

from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpRequest
from django.core.cache import cache
from django.utils import timezone
from django.apps import apps  # ⬅️ kunci: ambil model eksplisit dari app 'authentication'

from .passwords import is_strong_password  # asumsi sudah ada
from .utils import generate_otp

# Paksa pakai model dari app 'authentication' (→ tabel authentication_user)
AuthUser = apps.get_model("authentication", "User")
assert AuthUser._meta.db_table == "authentication_user", f"Wrong table: {AuthUser._meta.db_table}"


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

    if AuthUser.objects.filter(email=email).exists():
        otp = generate_otp(6)
        cache.set(f"pwdreset:{email}", otp, timeout=10 * 60)  # 10 menit
        # TODO: kirim OTP via email
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
        return JsonResponse({"status": "ok"})  

    try:
        user = AuthUser.objects.get(email=email)
    except AuthUser.DoesNotExist:
        return JsonResponse({"status": "ok"})  

    
    user.password = new_password
    if hasattr(user, "last_accessed"):
        user.last_accessed = timezone.now()
        user.save(update_fields=["password", "last_accessed"])
    else:
        user.save(update_fields=["password"])

    cache.delete(f"pwdreset:{email}")
    return JsonResponse({"status": "ok"})