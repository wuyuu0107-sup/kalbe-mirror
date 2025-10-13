# accounts/tests.py
import json
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core import mail

# ======================
# Helpers
# ======================
def extract_otp_from_mail(body: str) -> str:
    """
    Cari baris yang isinya angka aja (6 digit) dari email body.
    Sesuaikan kalau format email kamu beda.
    """
    for ln in body.splitlines():
        s = ln.strip()
        if s.isdigit() and 4 <= len(s) <= 8:  # fleksibel 4-8 digit
            return s
    # fallback: ambil digit berturut-turut terpanjang
    digits = "".join(ch for ch in body if ch.isdigit())
    if len(digits) >= 4:
        return digits[:6]
    raise AssertionError("OTP not found in email body")


# ======================
# Email OTP Tests
# ======================
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailOTPTests(TestCase):
    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="Old_123456",
        )

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

    # def test_confirm_sets_new_password(self):
    #     # Request OTP
    #     self.c.post(
    #         reverse("password-reset-otp-request"),
    #         data=json.dumps({"email": "alice@example.com"}),
    #         content_type="application/json",
    #     )
    #     # Ambil OTP dari email
    #     self.assertEqual(len(mail.outbox), 1, "Email OTP tidak terkirim")
    #     otp = extract_otp_from_mail(mail.outbox[0].body)

        # # Confirm pakai OTP
        # res = self.c.post(
        #     reverse("password-reset-otp-confirm"),
        #     data=json.dumps(
        #         {"email": "alice@example.com", "otp": otp, "password": "New_456789!"}
        #     ),
        #     content_type="application/json",
        # )
        # self.assertEqual(res.status_code, 200)
        # self.assertEqual(res.json().get("status"), "password-updated")
        # self.assertTrue(self.c.login(username="alice", password="New_456789!"))

    def test_confirm_weak_password(self):
        self.c.post(
            reverse("password-reset-otp-request"),
            data=json.dumps({"email": "alice@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(len(mail.outbox), 1)
        otp = extract_otp_from_mail(mail.outbox[0].body)

        res = self.c.post(
            reverse("password-reset-otp-confirm"),
            data=json.dumps(
                {"email": "alice@example.com", "otp": otp, "password": "short"}
            ),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.json())
