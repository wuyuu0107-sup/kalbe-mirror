import datetime as dt
from unittest import mock
from django.test import TestCase, Client
from authentication.models import User
from django.urls import reverse
from django.contrib.auth.hashers import make_password


class RecentFeaturesViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            username="alice",
            password=make_password("sTrongpassword!1"),
            display_name="Alice",
            email="alice@example.com",
            roles=["researcher"],
            is_verified=True
        )
        session = self.client.session
        session["user_id"] = str(self.user.user_id)
        session.save()

    @mock.patch("dashboard.views.get_recent_features")
    def test_recent_features_json_returns_iso(self, mock_service):
        mock_service.return_value = [
            {"feature_key": "Scan ke CSV", "last_used_at": dt.datetime(2025,10,7,12,0), "count": 3},
            {"feature_key": "Import File", "last_used_at": dt.datetime(2025,10,7,11,0), "count": 1},
        ]

        url = reverse("dashboard:recent-features-json")
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual([d["feature_key"] for d in data], ["Scan ke CSV", "Import File"])
        self.assertIn("T", data[0]["last_used_at"])
        self.assertEqual(data[0]["count"], 3)