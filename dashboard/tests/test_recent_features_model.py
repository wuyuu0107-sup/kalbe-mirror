from django.test import TestCase
from authentication.models import User
from dashboard.models import FeatureUsage
from django.contrib.auth.hashers import make_password

class FeatureUsageModelTest(TestCase):
    def test_str_representation(self):
        self.user = User.objects.create(
            username="alice",
            password=make_password("sTrongpassword!1"),
            display_name="Alice",
            email="alice@example.com",
            roles=["researcher"],
            is_verified=True
        )
        feature = FeatureUsage.objects.create(
            user=self.user,
            feature_key="dashboard_access",
        )

        # Act
        result = str(feature)

        # Assert
        expected = f"{self.user} used dashboard_access at {feature.used_at}"
        self.assertEqual(result, expected)
