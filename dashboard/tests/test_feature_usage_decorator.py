from django.test import TestCase, RequestFactory
from dashboard.models import FeatureUsage
from authentication.models import User
from django.contrib.auth.models import AnonymousUser
from unittest.mock import patch

from dashboard.tracking import track_feature

class TrackFeatureDecoratorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create(
            username="alice",
            password="sTrongpassword!1",
            display_name="Alice",
            email="alice@example.com",
            roles=["researcher"],
            is_verified=True
        )

    def test_decorator_records_usage_for_authenticated_user(self):

        @track_feature("dashboard.test")
        def sample_view(request):
            return 200 # Fask response for simple test
        
        req = self.factory.get("/dummy")
        req.user = self.user

        response = sample_view(req)
        self.assertEqual(response, 200)

        us = FeatureUsage.objects.filter(
            user=self.user,
            feature_key="dashboard.test"
        ).count()
        self.assertEqual(us, 1)
    
    def test_decorator_does_not_crash_for_anonymous(self):

        @track_feature("dashboard.public")
        def sample_view(request):
            return 200 # Fask response for simple test

        req = self.factory.get("/dummy")
        req.user = AnonymousUser()

        resp = sample_view(req)
        self.assertEqual(resp, 200)
    
    def test_decorator_swallows_exceptions_from_record_feature_use(self):
        # Patch record_feature_use to raise an exception intentionally
        with patch("dashboard.tracking.record_feature_use", side_effect=RuntimeError("boom")):
            
            @track_feature("dashboard.public")
            def sample_view(request):
                return 200  # Fake view output

            req = self.factory.get("/dummy")
            req.user = AnonymousUser()

            # The decorator should swallow the RuntimeError and still return the view’s output
            resp = sample_view(req)

            self.assertEqual(resp, 200)