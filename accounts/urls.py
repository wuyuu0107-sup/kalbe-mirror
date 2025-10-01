from django.urls import path
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie

# NOTE: your file name is views_otp_email.py (singular) in the screenshot.
# Keep this import matching your file name.
from . import views_otp_email as v_email

@method_decorator(ensure_csrf_cookie, name="dispatch")
class EmailOTPTestPage(TemplateView):
    template_name = "accounts/otp_email_test.html"

urlpatterns = [
    # Email OTP API
    path(
        "password-reset/otp/request/",
        v_email.password_reset_otp_request,
        name="password-reset-otp-request",
    ),
    path(
        "password-reset/otp/confirm/",
        v_email.password_reset_otp_confirm,
        name="password-reset-otp-confirm",
    ),

    # Simple test page that sets the CSRF cookie for manual testing
    path(
        "password-reset/otp/test/",
        EmailOTPTestPage.as_view(),
        name="password-reset-otp-test",
    ),
]