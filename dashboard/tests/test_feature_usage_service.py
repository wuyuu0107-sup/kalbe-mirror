import datetime as dt
from unittest import mock
from django.test import TestCase
from authentication.models import User
from django.utils import timezone
from django.test import RequestFactory

# features / service imports
from dashboard.services.feature_usage import record_feature_use, get_recent_features
from dashboard.models import FeatureUsage

class FeatureUsageServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username="testuser",
            password="sTrongpassword!1",
            display_name="Test User",
            email="test@example.com",
            roles=["researcher"],
            is_verified=True
        )
    
    def make_request_for_user(self, user):
        req = RequestFactory().get("/dummy")
        req.session = {"user_id": str(user.user_id)}
        req.user = user  # optional, but helpful if your decorator uses it
        return req

    def test_record_feature_use_handles_exception_in_is_authenticated(self):
        class BadUser:
            def is_authenticated(self):
                raise Exception("Boom")

        # make a valid request that has a session with user_id
        req = self.make_request_for_user(self.user)
        req.user = BadUser()  # still trigger the exception in is_authenticated

        # should not crash
        record_feature_use(req, "Some Feature")

        # should still record usage for the session-based user
        usage = FeatureUsage.objects.filter(
            feature_key="Some Feature",
            user=self.user
        )
        self.assertIsNotNone(usage)
    
    def test_record_and_get_recent_distinct(self):
        req = self.make_request_for_user(self.user)

        t0 = timezone.make_aware(dt.datetime(2025, 10, 7, 10, 0, 0))
        with mock.patch("django.utils.timezone.now", return_value=t0):
            record_feature_use(req, "Scan ke CSV")

        t1 = timezone.make_aware(dt.datetime(2025, 10, 7, 11, 0, 0))
        with mock.patch("django.utils.timezone.now", return_value=t1):
            record_feature_use(req, "Scan ke CSV")

        t2 = timezone.make_aware(dt.datetime(2025, 10, 7, 11, 1, 0))
        with mock.patch("django.utils.timezone.now", return_value=t2):
            record_feature_use(req, "Import File")

        recent = get_recent_features(self.user)
        names = [r["feature_key"] for r in recent]
        self.assertEqual(names, ["Import File", "Scan ke CSV"])
        self.assertIn("last_used_at", recent[0])
        self.assertIn("count", recent[0])

    def test_get_recent_is_user_based(self):
        # Different user
        alice = User.objects.create(
            username="alice",
            password="sTrongpassword!1",
            display_name="Alice",
            email="alice@example.com",
            roles=["researcher"],
            is_verified=True
        )

        req_user = self.make_request_for_user(self.user)
        req_alice = self.make_request_for_user(alice)

        record_feature_use(req_alice, "Scan ke CSV")
        record_feature_use(req_user, "Import File")

        recent_alice = get_recent_features(alice)
        self.assertEqual([r["feature_key"] for r in recent_alice], ["Scan ke CSV"])

        recent_user = get_recent_features(self.user)
        self.assertEqual([r["feature_key"] for r in recent_user], ["Import File"])

