from django.test import TestCase, Client
from django.utils import timezone
from authentication.models import User
from django.contrib.auth.hashers import make_password
import time

class LoginProfilingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            username="protest",
            password=make_password("StrongPass123"),
            email="protest@mail.com",
            display_name="Profiler",
            is_verified=True
        )

    def test_login_stores_latency_upon_success(self):
        before = timezone.now()
        response = self.client.post("/auth/login/", {
            "username": "protest",
            "password": "StrongPass123"
        }, content_type="application/json")

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()

        # new field must exist and store latency value
        self.assertIsNotNone(self.user.auth_latency_ms)
        self.assertGreaterEqual(self.user.auth_latency_ms, 0)

        # last_accessed should be updated
        self.assertGreater(self.user.last_accessed, before)

    def test_latency_not_recorded_on_failed_login(self):
        response = self.client.post("/auth/login/", {
            "username": "protest",
            "password": "WrongPass"
        }, content_type="application/json")

        self.assertEqual(response.status_code, 401)

        self.user.refresh_from_db()
        self.assertIsNone(self.user.auth_latency_ms)