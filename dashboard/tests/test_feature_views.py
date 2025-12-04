from django.test import TestCase, Client, RequestFactory
from authentication.models import User
from unittest.mock import patch, MagicMock
from dashboard import views
from dashboard.views import CsrfExemptSessionAuthentication
from django.http import JsonResponse

class ViewsMissingCoverageTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.user = User.objects.create(
            username="alice",
            password="pass",
            display_name="Alice",
            email="alice@example.com",
            is_verified=True
        )

    def test_whoami_returns_session_info(self):
        session = self.client.session
        session["user_id"] = str(self.user.user_id)
        session["username"] = self.user.username
        session.save()
        res = self.client.get("/dashboard/whoami/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["username"], "alice")

    def test_recent_files_json_handles_exception(self):
        with patch("dashboard.views.get_recent_files", side_effect=Exception("boom")):
            res = self.client.get("/dashboard/recent-files-json/5/")
            self.assertEqual(res.status_code, 500)
            self.assertIn("error", res.json())

    def test_recent_features_json_no_session_user(self):
        res = self.client.get("/dashboard/recent-features-json/")
        self.assertEqual(res.status_code, 401)

    def test_recent_features_json_user_not_found(self):
        session = self.client.session
        session["user_id"] = "nonexistent"
        session.save()
        res = self.client.get("/dashboard/recent-features-json/")
        self.assertEqual(res.status_code, 404)

    def test_recent_features_json_happy_path(self):
        session = self.client.session
        session["user_id"] = str(self.user.user_id)
        session.save()

        with patch("dashboard.views.get_recent_features", return_value=[{"last_used_at": MagicMock(isoformat=lambda: "2025-01-01T00:00:00")}]):
            res = self.client.get("/dashboard/recent-features-json/")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIsInstance(data, list)
            self.assertIn("last_used_at", data[0])
            
class CsrfExemptSessionAuthenticationTests(TestCase):
    def setUp(self):
        self.auth = CsrfExemptSessionAuthentication()
        self.factory = RequestFactory()

    def test_enforce_csrf_does_nothing(self):
        """Ensure enforce_csrf() does not raise any exception (CSRF disabled)."""
        request = self.factory.get("/")
        try:
            self.auth.enforce_csrf(request)
        except Exception as e:
            self.fail(f"enforce_csrf() raised {e} unexpectedly")

class RecentEndpointsMockAndStubTests(TestCase):
    class StubDate:
        def isoformat(self):
            return "2024-12-31T12:00:00"
        
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.user = User.objects.create(
            username="bob",
            password="pass",
            display_name="Bob",
            email="bob@example.com",
            is_verified=True,
        )
        
    @patch("dashboard.views.get_recent_files")
    def test_recent_files_json_calls_service_with_mock(self, mock_recent_files):
        mock_recent_files.return_value = []

        res = self.client.get("/dashboard/recent-files-json/2/")

        mock_recent_files.assert_called_once_with(2)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    @patch("dashboard.views.get_recent_features")
    def test_recent_features_json_uses_stub_value(self, mock_recent_features):
        session = self.client.session
        session["user_id"] = str(self.user.user_id)
        session.save()

        stub_date = self.StubDate()
        mock_recent_features.return_value = [
            {"name": "Feature A", "last_used_at": stub_date}
        ]

        res = self.client.get("/dashboard/recent-features-json/")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()[0]["last_used_at"], "2024-12-31T12:00:00")