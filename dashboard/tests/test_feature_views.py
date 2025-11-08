from django.test import TestCase, Client, RequestFactory
from authentication.models import User
from unittest.mock import patch, MagicMock
from dashboard import views
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

    def test_chat_suggestion_viewset_get_queryset_anonymous(self):
        req = self.factory.get("/api/chat-suggestions/")
        req.user = MagicMock(is_authenticated=False)
        viewset = views.ChatSuggestionViewSet()
        viewset.request = req
        qs = viewset.get_queryset()
        self.assertEqual(list(qs), [])

    def test_chat_suggestion_viewset_perform_create(self):
        serializer = MagicMock()
        req = self.factory.post("/api/chat-suggestions/")
        req.user = self.user
        viewset = views.ChatSuggestionViewSet()
        viewset.request = req
        viewset.perform_create(serializer)
        serializer.save.assert_called_once_with(user=self.user)