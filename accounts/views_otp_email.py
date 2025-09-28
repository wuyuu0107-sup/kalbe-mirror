import json
from typing import Any, Dict

from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpRequest
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User

from .utils import generate_otp
from .services import cache_store as cs
from .passwords import is_strong_password


def _read_json(request: HttpRequest) -> Dict[str, Any]:
    """
    Safe JSON loader: selalu balikin dict.
    (Fix E701: jangan pakai one-liner try/except.)
    """
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}


@require_POST
def password_reset_otp_request(request: HttpRequest) -> JsonResponse:
    """
    Kirim OTP via email kalau email terdaftar.
    Anti user-enumeration: tetap balas 200 {"status": "ok"} meski email tidak ada,
    tetapi TIDAK mengirim email pada kasus tersebut.
    """
    data = _read_json(request)
    email = (data.get("email") or "").strip().lower()
    if not email:
        return JsonResponse({"error": "email is required"}, status=400)

    try:
        # Hanya cek keberadaan user; tidak menyimpan ke variabel agar terhindar F841.
        User.objects.get(email=email)
    except User.DoesNotExist:
        # Tetap balas generik.
        return JsonResponse({"status": "ok"})

    otp = generate_otp()
    cs.store_otp(email, otp, ttl=600)  # 10 menit

    send_mail(
        subject="Your OTP Code",
        message=f"Your password reset code is: {otp}\n(valid 10 minutes)",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    return JsonResponse({"status": "ok"})


@require_POST
def password_reset_otp_confirm(request: HttpRequest) -> JsonResponse:
    """
    Verifikasi OTP & update password user.
    Catatan: Endpoint ini saat ini mengembalikan pesan error spesifik (email/otp),
    yang bisa mengindikasikan enumerasi. Lihat komentar di bawah untuk opsi hardening.
    """
    data = _read_json(request)
    email = (data.get("email") or "").strip().lower()
    otp_in = (data.get("otp") or "").strip()
    new_pw = (data.get("password") or "").strip()

    if not email or not otp_in or not new_pw:
        return JsonResponse({"error": "missing fields"}, status=400)

    if not is_strong_password(new_pw):
        return JsonResponse({"error": "weak password"}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Versi saat ini: balikkan error spesifik.
        # Untuk anti-enumeration penuh, ganti jadi return JsonResponse({"status": "ok"}).
        return JsonResponse({"error": "invalid email"}, status=400)

    otp_stored = cs.get_otp(email)
    if (not otp_stored) or (otp_stored != otp_in):
        # Versi saat ini: balikkan error spesifik.
        # Untuk anti-enumeration penuh, ganti jadi return JsonResponse({"status": "ok"}).
        return JsonResponse({"error": "invalid or expired otp"}, status=400)

    user.set_password(new_pw)
    user.save()
    cs.delete_otp(email)

    return JsonResponse({"status": "password-updated"})
