import datetime as dt
from unittest import mock
from django.test import TestCase
from authentication.models import User
from django.utils import timezone

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

    def test_record_feature_use_handles_exception_in_is_authenticated(self):
        class BrokenUser:
            @property
            def is_authenticated(self):
                raise RuntimeError("Simulated error")

        user = BrokenUser()

        # Ensure no FeatureUsage exists before
        self.assertEqual(FeatureUsage.objects.count(), 0)

        # Call the function — should hit the except branch
        record_feature_use(user, "feature_x")

        # Ensure a FeatureUsage was created with user=None
        usage = FeatureUsage.objects.first()
        self.assertIsNotNone(usage)
        self.assertIsNone(usage.user)
        self.assertEqual(usage.feature_key, "feature_x")
    
    def test_record_and_get_recent_distinct(self):
        t0 = timezone.make_aware(dt.datetime(2025, 10, 7, 10, 0, 0))
        with mock.patch("django.utils.timezone.now", return_value=t0):
            record_feature_use(self.user, "Scan ke CSV")

        t1 = timezone.make_aware(dt.datetime(2025, 10, 7, 11, 0, 0))
        with mock.patch("django.utils.timezone.now", return_value=t1):
            record_feature_use(self.user, "Scan ke CSV")

        t2 = timezone.make_aware(dt.datetime(2025, 10, 7, 11, 1, 0))  # strictly later
        with mock.patch("django.utils.timezone.now", return_value=t2):
            record_feature_use(self.user, "Import File")
        
        # Export distinct by feature, ordered by most recent use
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

        record_feature_use(self.user, "Scan ke CSV")
        record_feature_use(alice, "Import File")

        recent_alice = get_recent_features(alice)
        self.assertEqual([r["feature_key"] for r in recent_alice], ["Import File"])

