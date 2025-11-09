# audittrail/tests/test_log_viewer_api.py
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from audittrail.models import ActivityLog


@override_settings(ROOT_URLCONF="audittrail.tests.urls_api")
class LogViewerAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="viewer",
            email="viewer@example.com",
            password="pass123",
        )

        # create some logs to filter on
        now = timezone.now()
        self.log1 = ActivityLog.objects.create(
            event_type=ActivityLog.EventType.OCR_UPLOADED,
            username="userhafizh",
            metadata={"note": "ocr upload"},
        )
        # simulate older log
        self.log1.created_at = now - timedelta(days=2)
        self.log1.save(update_fields=["created_at"])

        self.log2 = ActivityLog.objects.create(
            event_type=ActivityLog.EventType.ANNOTATION_UPDATED,
            username="viewer",
            metadata={"note": "annotated something"},
        )

    def test_requires_authentication(self):
        # no login → should fail (we expect 401 or 403 depending on your permission)
        resp = self.client.get("/audit/logs/")
        self.assertIn(resp.status_code, (401, 403))

    def test_can_list_logs_when_authenticated(self):
        self.client.force_login(self.user)
        resp = self.client.get("/audit/logs/")
        # will fail now because endpoint doesn't exist
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data)
        self.assertGreaterEqual(resp.data["count"], 2)

    def test_filter_by_username(self):
        self.client.force_login(self.user)
        resp = self.client.get("/audit/logs/?username=userhafizh")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            all(item["username"] == "userhafizh" for item in resp.data["results"])
        )

    def test_filter_by_event_type(self):
        self.client.force_login(self.user)
        resp = self.client.get("/audit/logs/?event_type=ANNOTATION_UPDATED")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            all(item["event_type"] == "ANNOTATION_UPDATED" for item in resp.data["results"])
        )

    def test_filter_by_date_range(self):
        """
        date_from should exclude the older log we set 2 days ago
        """
        self.client.force_login(self.user)
        date_from = (timezone.now() - timedelta(days=1)).isoformat()
        resp = self.client.get(f"/audit/logs/?date_from={date_from}")
        self.assertEqual(resp.status_code, 200)
        # all returned logs must be newer than date_from
        for item in resp.data["results"]:
            self.assertGreaterEqual(item["created_at"], date_from)

    def test_search_across_text_fields(self):
        self.client.force_login(self.user)
        # "annotated" is in metadata of log2
        resp = self.client.get("/audit/logs/?search=annotated")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data["results"]), 1)
