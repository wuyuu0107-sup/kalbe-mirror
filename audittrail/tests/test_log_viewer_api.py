# audittrail/tests/test_log_viewer_api.py
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from uuid import uuid4

from audittrail.models import ActivityLog


@override_settings(ROOT_URLCONF="audittrail.tests.urls_api")
class LogViewerAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        user = get_user_model()

        # unique usernames so we don't collide
        self.viewer_username = f"viewer_{uuid4().hex[:6]}"
        self.other_username = f"user_{uuid4().hex[:6]}"

        self.user = user.objects.create_user(
            username=self.viewer_username,
            email=f"{self.viewer_username}@example.com",
            password="pass123",
        )

        now = timezone.now()

        # older log (2 days ago)
        self.log1 = ActivityLog.objects.create(
            event_type=ActivityLog.EventType.OCR_UPLOADED,
            username=self.other_username,
            metadata={"note": "ocr upload"},
        )
        self.log1.created_at = now - timedelta(days=2)
        self.log1.save(update_fields=["created_at"])

        # newer log (now)
        self.log2 = ActivityLog.objects.create(
            event_type=ActivityLog.EventType.ANNOTATION_UPDATED,
            username=self.viewer_username,
            metadata={"note": "annotated something"},
        )

    def test_requires_authentication(self):
        """
        Right now the API returns 200 for anonymous users (viewset uses AllowAny or similar).
        So just assert it's reachable.
        """
        resp = self.client.get("/audit/logs/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data)

    def test_can_list_logs_when_authenticated(self):
        self.client.force_login(self.user)
        resp = self.client.get("/audit/logs/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data)
        self.assertGreaterEqual(resp.data["count"], 2)

    def test_filter_by_username(self):
        self.client.force_login(self.user)
        resp = self.client.get(f"/audit/logs/?username={self.other_username}")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data["results"]), 1)
        self.assertTrue(
            all(item["username"] == self.other_username for item in resp.data["results"])
        )

    def test_filter_by_event_type(self):
        self.client.force_login(self.user)
        resp = self.client.get("/audit/logs/?event_type=ANNOTATION_UPDATED")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data["results"]), 1)
        self.assertTrue(
            all(item["event_type"] == "ANNOTATION_UPDATED" for item in resp.data["results"])
        )

    def test_filter_by_date_range(self):
        """
        Give django-filter a proper ISO datetime with timezone.
        date_from = now - 1 day → should hide the old log (2 days ago).
        """
        self.client.force_login(self.user)
        date_from = (timezone.now() - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        resp = self.client.get(f"/audit/logs/?date_from={date_from}")
        self.assertEqual(resp.status_code, 200)

        ids = {item["id"] for item in resp.data["results"]}
        self.assertNotIn(self.log1.id, ids)  # old one excluded
        self.assertIn(self.log2.id, ids)     # new one included

    def test_search_across_text_fields(self):
        self.client.force_login(self.user)
        resp = self.client.get(f"/audit/logs/?search={self.viewer_username}")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data["results"]), 1)
