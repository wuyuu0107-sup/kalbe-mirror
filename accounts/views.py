# accounts/views.py
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpRequest
from django.core.cache import cache
from django.utils import timezone
from django.apps import apps  # kunci: ambil model eksplisit dari app 'authentication'
from django.views.decorators.csrf import csrf_exempt  # TAMBAH INI

from .passwords import is_strong_password  # asumsi sudah ada
from .utils import generate_otp
from .views_otp_email import _read_json

# Paksa pakai model dari app 'authentication' (→ tabel authentication_user)
AuthUser = apps.get_model("authentication", "User")
assert AuthUser._meta.db_table == "authentication_user", f"Wrong table: {AuthUser._meta.db_table}"

@csrf_exempt   # CSRF dimatikan untuk endpoint ini
@require_POST
# basic view function
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
    return JsonResponse({"status": "ok"})

def _parse_reset_payload(request):
    data = _read_json(request)

    email = (data.get("email") or "").strip().lower()
    otp = (data.get("otp") or "").strip()
    new_pw = (
        data.get("new_password")
        or data.get("password")
        or ""
    ).strip()

    return email, otp, new_pw

def _validate_reset_fields(email, otp, new_pw):
    if not email or not otp or not new_pw:
        return False, "missing fields"

    if not is_strong_password(new_pw):
        return False, "weak_password"

    return True, None

def _check_reset_otp(email, otp):
    cached = cache.get(f"pwdreset:{email}")
    if cached and cached == otp:
        return True
    return False

def _get_user_or_none(email):
    try:
        return AuthUser.objects.get(email=email)
    except AuthUser.DoesNotExist:
        return None

def _apply_new_password_reset(user, new_pw):
    user.password = new_pw
    update_fields = ["password"]

    if hasattr(user, "last_accessed"):
        user.last_accessed = timezone.now()
        update_fields.append("last_accessed")

    user.save(update_fields=update_fields)

@csrf_exempt   # CSRF dimatikan untuk endpoint ini
@require_POST
def reset_password_confirm(request: HttpRequest) -> JsonResponse:
    """
    Phase 2: verifikasi OTP + set password baru.
    Tetap balikin {"status":"ok"} pada kegagalan verifikasi demi anti-enumeration.
    """
    email, otp, new_password = _parse_reset_payload(request)

    ok, error = _validate_reset_fields(email, otp, new_password)  
    if not ok:
        return JsonResponse({"error": error}, status=400)
    
    if not _check_reset_otp(email, otp):
        return JsonResponse({"status": "ok"})

    user = _get_user_or_none(email)
    if not user:
        return JsonResponse({"status": "ok"})
    
    _apply_new_password_reset(user, new_password)
    cache.delete(f"pwdreset:{email}")
    
    return JsonResponse({"status": "ok"})
