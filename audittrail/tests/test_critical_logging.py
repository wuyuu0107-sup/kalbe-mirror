# audittrail/tests/test_critical_logging.py

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from audittrail.models import ActivityLog


class CriticalLoggingTests(TestCase):
    """
    RED PHASE — tests describe how the logging system should behave,
    even though we haven't implemented it yet.
    """

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="pass123")

    def test_login_should_generate_user_login_log(self):
        """
        When a user logs in successfully, a USER_LOGIN ActivityLog should be created.
        """
        resp = self.client.post("/auth/login/", {"username": "tester", "password": "pass123"})
        self.assertEqual(resp.status_code, 200)

        log = ActivityLog.objects.filter(event_type=ActivityLog.EventType.USER_LOGIN).first()
        self.assertIsNotNone(log, "Expected USER_LOGIN ActivityLog to be created after login")
        self.assertEqual(log.user, self.user)

    def test_dashboard_view_should_generate_dashboard_viewed_log(self):
        """
        Visiting the dashboard endpoint should create a DASHBOARD_VIEWED log.
        """
        self.client.force_login(self.user)
        resp = self.client.get("/dashboard/")
        self.assertEqual(resp.status_code, 200)

        log = ActivityLog.objects.filter(event_type=ActivityLog.EventType.DASHBOARD_VIEWED).first()
        self.assertIsNotNone(log, "Expected DASHBOARD_VIEWED ActivityLog to be created after viewing dashboard")
        self.assertEqual(log.user, self.user)

    def test_ocr_upload_should_generate_ocr_uploaded_log(self):
        """
        Uploading an OCR file should produce an OCR_UPLOADED log entry.
        """
        self.client.force_login(self.user)
        with open("backend/tests/sample.pdf", "rb") as f:
            resp = self.client.post("/ocr/", {"file": f})
        self.assertEqual(resp.status_code, 200)

        log = ActivityLog.objects.filter(event_type=ActivityLog.EventType.OCR_UPLOADED).first()
        self.assertIsNotNone(log, "Expected OCR_UPLOADED ActivityLog after file upload")
        self.assertEqual(log.user, self.user)

    def test_dataset_view_requires_authentication(self):
        """
        Dataset view should require login; if unauthorized, no ActivityLog is created.
        """
        resp = self.client.get("/dataset/csv-files/")
        self.assertIn(resp.status_code, (401, 403))

        logs = ActivityLog.objects.all()
        self.assertEqual(
            logs.count(),
            0,
            "No ActivityLog should be created when access is denied",
        )
