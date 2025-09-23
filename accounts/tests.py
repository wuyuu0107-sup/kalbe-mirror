from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core import mail
import json
from urllib.parse import urlparse

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password="OldPass_123"
        )

    def test_request_always_200_and_sends_mail_for_existing_email(self):
        res = self.client.post(
            reverse("password-reset-request"),
            data=json.dumps({"email": "alice@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/password-reset/confirm/", mail.outbox[0].body)

    def test_request_unknown_email_still_200(self):
        res = self.client.post(
            reverse("password-reset-request"),
            data=json.dumps({"email": "ghost@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")
        self.assertEqual(len(mail.outbox), 0)

    def test_confirm_with_token_sets_new_password(self):
        self.client.post(
            reverse("password-reset-request"),
            data=json.dumps({"email": "alice@example.com"}),
            content_type="application/json",
        )
        body = mail.outbox[0].body
        path = urlparse([ln for ln in body.splitlines() if "/accounts/password-reset/confirm/" in ln][0]).path

        res = self.client.post(
            path, data=json.dumps({"password": "NewPass_456!"}), content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "password-updated")
        self.assertTrue(self.client.login(username="alice", password="NewPass_456!"))

    def test_confirm_with_bad_token_fails(self):
        res = self.client.post(
            "/accounts/password-reset/confirm/invalid/invalid/",
            data=json.dumps({"password": "Whatever_123!"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)

    def test_confirm_requires_strong_password(self):
        self.client.post(
            reverse("password-reset-request"),
            data=json.dumps({"email": "alice@example.com"}),
            content_type="application/json",
        )
        body = mail.outbox[0].body
        path = urlparse([ln for ln in body.splitlines() if "/accounts/password-reset/confirm/" in ln][0]).path

        res = self.client.post(
            path, data=json.dumps({"password": "short"}), content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
