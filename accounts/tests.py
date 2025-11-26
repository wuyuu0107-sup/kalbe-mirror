# accounts/tests.py
import json
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core import mail
from django.apps import apps
from django.contrib.auth.hashers import make_password
import re

# -----------------------
# Helpers
# -----------------------
def extract_otp_from_mail(body: str) -> str:
    m = re.search(r"\b(\d{4,8})\b", body)
    if not m:
        raise AssertionError("OTP not found in email body")
    return m.group(1)

# Use an in-memory sqlite DB for these tests only,
# and locmem email backend so mail.outbox is populated.
TEST_OVERRIDES = {
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "DEFAULT_FROM_EMAIL": "test@example.local",
    "DATABASES": {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    },
}

@override_settings(**TEST_OVERRIDES)
class EmailOTPTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create user in the SAME table your views use: authentication_user
        auth_user = apps.get_model("authentication", "User")
        auth_user.objects.create(
            username="alice",
            email="alice@example.com",
            display_name="Alice",
            password=make_password("Old_123456"),
            roles=[],
            is_verified=True,
        )

    def setUp(self):
        self.c = Client()
        mail.outbox.clear()

    def test_request_known_email_sends_mail(self):
        res = self.c.post(
            reverse("password-reset-otp-request"),
            data=json.dumps({"email": "alice@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "ok")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Your OTP Code", mail.outbox[0].subject)

    def test_request_unknown_email_also_200_no_mail(self):
        res = self.c.post(
            reverse("password-reset-otp-request"),
            data=json.dumps({"email": "ghost@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "ok")
        self.assertEqual(len(mail.outbox), 0)

    def test_confirm_weak_password(self):
        # Request OTP
        self.c.post(
            reverse("password-reset-otp-request"),
            data=json.dumps({"email": "alice@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(len(mail.outbox), 1, "OTP email not sent")
        otp = extract_otp_from_mail(mail.outbox[0].body)

        # Confirm with weak password
        res = self.c.post(
            reverse("password-reset-otp-confirm"),
            data=json.dumps(
                {"email": "alice@example.com", "otp": otp, "password": "short"}
            ),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.json())
